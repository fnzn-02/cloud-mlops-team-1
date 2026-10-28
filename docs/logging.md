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

```sh
# Windows PowerShell
$env:CLOUDWATCH_LOG_GROUP = "/mlops/bike-api"
$env:CLOUDWATCH_LOG_STREAM = "bike-api-local"   # 생략하면 bike-api-<컴퓨터 이름>
$env:AWS_REGION = "ap-northeast-2"
.\.venv\Scripts\python.exe -m uvicorn src.api:app
```

- AWS 자격 증명(`aws configure` 또는 EC2 IAM 역할)이 필요하다. 필요한 권한: `logs:DescribeLogGroups`, `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`.
- 로그는 10초마다 모아서 보내고, 서버를 끌 때 남은 로그를 보낸다.
- 연결에 실패하면 콘솔에 `cloudwatch_failed`를 남기고 서버는 콘솔 로그만으로 계속 동작한다.

## Log Stream → S3 내보내기 (AWS 콘솔)

1. S3 버킷을 만든다 (CloudWatch Logs와 같은 리전, 예: ap-northeast-2).
2. 버킷 정책에서 `logs.ap-northeast-2.amazonaws.com`에 `s3:GetBucketAcl`, `s3:PutObject`를 허용한다.
3. CloudWatch → 로그 그룹 `/mlops/bike-api` → 작업 → **Amazon S3로 데이터 내보내기**.
4. 기간, 스트림 접두사(예: `bike-api-local`), 버킷, 접두사(예: `bike-logs/`)를 지정해 내보낸다.
5. S3에 `.gz` 파일이 생기면 받아서 압축을 풀면 위의 JSON 줄이 들어 있다 (각 줄 앞에 CloudWatch 수신 시각이 붙는다).
