# 예측·피드백 로그 (재학습·강화학습용)

API는 이벤트마다 **JSON 한 줄**을 콘솔에 남긴다. `CLOUDWATCH_LOG_GROUP`을 설정하면 같은 내용이 CloudWatch Logs에도 간다. 코드: `src/event_log.py`

## 이벤트 종류

| event | 언제 | 주요 필드 |
|---|---|---|
| `model_loaded` | 서버 시작, 모델 읽기 성공 | `model_path`, `model_version` |
| `model_load_failed` | 모델 읽기 실패 (API는 503) | `model_path`, `error` |
| `prediction` | `/predict` 성공 | `request_id`, `model_version`, `input`, `state`, `action`, `latency_ms` |
| `invalid_input` | `/predict`·`/feedback` 입력 오류 (422) | `endpoint`, `payload`, `errors` |
| `feedback` | `/feedback` 성공 | `request_id`, `actual_rentals`, `matched`, `state`, `action`, `error`, `reward` |
| `cloudwatch_ready` / `cloudwatch_failed` | CloudWatch 연결 결과 | `log_group`, `error` |

- `ts`: UTC 시각 (ISO 8601)
- `model_version`: 모델 파일 SHA-256 앞 12자리. 재학습 후 모델이 바뀌면 값이 달라져 어떤 모델의 예측인지 구분된다.

## state / action / reward

강화학습 용어로 한 번의 예측을 다음처럼 기록한다.

| 용어 | 이 서비스에서 | 로그 필드 |
|---|---|---|
| state (상황) | 모델 입력 7개: 시간, 기온, 습도, 강수량, 쉬는 날, 월, 요일 | `state` (학습 때와 같은 열 이름) |
| action (행동) | 모델이 낸 예측 대여 수 | `action.predicted_rentals` |
| reward (보상) | 실제 대여 수가 들어오면 `-|예측 - 실제|` (0에 가까울수록 좋음) | `feedback` 이벤트의 `reward` |

- `error = 예측 - 실제`: +면 과대 예측(자전거를 너무 많이 배치), -면 과소 예측(자전거 부족).
- 예시: 예측 3,266대, 실제 3,000대 → `error = 266`, `reward = -266`.

### 피드백 흐름

1. `POST /predict` → 응답에 `request_id`가 붙는다.
2. 그 시간이 지나 실제 대여 수를 알면 `POST /feedback`:
   ```json
   {"request_id": "63ceff91-...", "actual_rentals": 3000}
   ```
3. 서버가 최근 예측(메모리, 최대 10,000건)에서 `request_id`를 찾으면 `matched: true`와 함께 `reward`를 계산해 남긴다.
   - 서버 재시작 등으로 못 찾으면 `matched: false`, `reward: null`로 실제값만 남긴다. 이때는 `prediction` 로그와 `request_id`로 이어 붙여 계산한다.

### 로그 예시

```json
{"event": "prediction", "ts": "2026-10-28T07:10:50.503+00:00", "request_id": "63ceff91-1496-4750-b469-dfe7965e6847", "model_version": "d7a782f5853d", "input": {"date": "2018-06-15", "hour": 18, "temperature": 25.0, "humidity": 50, "rainfall": 0.0, "holiday": false}, "state": {"Hour": 18, "Temperature(°C)": 25.0, "Humidity(%)": 50, "Rainfall(mm)": 0.0, "is_offday": 0, "month": 6, "dow": 4}, "action": {"predicted_rentals": 3266}, "latency_ms": 197.28}
{"event": "feedback", "ts": "2026-10-28T07:10:50.522+00:00", "request_id": "63ceff91-1496-4750-b469-dfe7965e6847", "model_version": "d7a782f5853d", "actual_rentals": 3000, "matched": true, "state": {"Hour": 18, "Temperature(°C)": 25.0, "Humidity(%)": 50, "Rainfall(mm)": 0.0, "is_offday": 0, "month": 6, "dow": 4}, "action": {"predicted_rentals": 3266}, "error": 266, "reward": -266}
```

### 재학습에 쓰는 방법

- `feedback` 중 `matched: true`인 줄의 `state` + `actual_rentals`가 새 학습 데이터 한 행이다 (열 이름이 학습 데이터와 같다).
- `reward` 평균(= -MAE)을 `model_version`별로 비교하면 실제 운영 성능을 볼 수 있다. 평가 MAE(85대)보다 크게 나빠지면 재학습 신호로 쓴다.
- `invalid_input`은 사용자가 자주 틀리는 입력을 찾아 화면·입력 규칙을 고치는 데 쓴다.

## CloudWatch 설정

### 수업 계정에서 실행 (실제로 확인한 방법)

- 학생 계정은 **MFA를 등록하고 MFA 코드로 다시 로그인해야** CloudShell 등을 쓸 수 있다 (그 전에는 `StudentSelfManagement` 정책이 거부). 액세스 키 생성은 막혀 있으므로 CloudShell에서 실행한다.
- 우리 팀 이름: 로그 그룹 `/mlops/team1-bike-rental`, 스트림 `bike-api-<날짜>`, 버킷 `team1-bike-rental-logs-093356173512`. (`/mlops/bike-rental`은 다른 팀 그룹이므로 쓰지 않는다)
- 실행 결과: [`results/cloudwatch-s3-check.md`](../results/cloudwatch-s3-check.md)

```sh
# CloudShell (서울 리전)
git clone -b feat/cloudwatch-logs https://github.com/fnzn-02/cloud-mlops-team-1.git && cd cloud-mlops-team-1
python3 -m venv /tmp/venv
/tmp/venv/bin/pip install pandas==3.0.6 scikit-learn==1.9.1 joblib==1.6.0 fastapi==0.142.2 uvicorn==0.54.0 boto3==1.43.120 watchtower==3.4.0
export CLOUDWATCH_LOG_GROUP=/mlops/team1-bike-rental CLOUDWATCH_LOG_STREAM=bike-api-20261028 AWS_REGION=ap-northeast-2
nohup /tmp/venv/bin/python -m uvicorn src.api:app --port 8000 > /tmp/server.log 2>&1 &
/tmp/venv/bin/python src/check_api.py --out /tmp/api-check-cloud.json
kill -INT %1   # 서버를 끄면 남은 로그를 CloudWatch로 보낸다
```

### 내 PC에서 실행 (AWS 자격 증명이 있을 때)

```sh
# Windows PowerShell
$env:CLOUDWATCH_LOG_GROUP = "/mlops/team1-bike-rental"
$env:CLOUDWATCH_LOG_STREAM = "bike-api-local"   # 생략하면 bike-api-<컴퓨터 이름>
$env:AWS_REGION = "ap-northeast-2"
.\.venv\Scripts\python.exe -m uvicorn src.api:app
```

- AWS 자격 증명(`aws configure` 또는 EC2 IAM 역할)이 필요하다. 필요한 권한: `logs:DescribeLogGroups`, `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`.
- 로그는 10초마다 모아서 보내고, 서버를 끌 때 남은 로그를 보낸다.
- 연결에 실패하면 콘솔에 `cloudwatch_failed`를 남기고 서버는 콘솔 로그만으로 계속 동작한다.

## Log Stream → S3 내보내기

1. S3 버킷 `team1-bike-rental-logs-093356173512`를 만든다 (서울 리전, 퍼블릭 액세스 차단).
2. 버킷 정책에서 `logs.ap-northeast-2.amazonaws.com`에 `s3:GetBucketAcl`(버킷), `s3:PutObject`(버킷/*)를 허용한다. 조건으로 우리 계정(`aws:SourceAccount`)만 허용한다.
3. 내보내기 작업 (콘솔: CloudWatch → 로그 그룹 → 작업 → **Amazon S3로 데이터 내보내기**와 같다):
   ```sh
   aws logs create-export-task --log-group-name /mlops/team1-bike-rental \
     --log-stream-name-prefix bike-api-20261028 --from <시작 ms> --to <끝 ms> \
     --destination team1-bike-rental-logs-093356173512 --destination-prefix bike-logs/run-20261028
   aws logs describe-export-tasks --task-id <작업 ID>   # COMPLETED까지 기다린다
   ```
4. 다시 읽기: `000000.gz`를 받아 압축을 풀고 줄 수와 SHA-256을 원본(CloudWatch 조회 건수)과 대조한다. 각 줄 앞에 CloudWatch 수신 시각이 붙는다.
5. 매번 새 `run-<날짜>` 접두사를 써서 이전 파일을 덮어쓰지 않는다.
