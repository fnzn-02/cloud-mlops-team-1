# CloudWatch Logs 전송·S3 내보내기 확인 (2026-10-28)

학생 계정(MFA 로그인)으로 연 CloudShell(ap-northeast-2)에서 `feat/cloudwatch-logs` 브랜치를 받아 실행했다.

## 5단계: CloudWatch Logs 전송

| 항목 | 값 |
|---|---|
| 로그 그룹 | `/mlops/team1-bike-rental` |
| 로그 스트림 | `bike-api-20261028` |
| 모델 버전 | `d7a782f5853d` |
| 보낸 요청 | `src/check_api.py` 9건 (정상 1, 입력 오류 3, 피드백 정상 1·모르는 id 1, 피드백 오류 2, health 1) |
| CloudWatch에 도착한 이벤트 | 10건 (`cloudwatch_ready` 1, `model_loaded` 1, `prediction` 1, `invalid_input` 5, `feedback` 2) |

예측과 피드백이 같은 `request_id`로 연결됐다.

| event | request_id | 값 |
|---|---|---|
| prediction | `870c5ba8-107e-464f-aa66-82822a0b9c3e` | 예측 3,266대 |
| feedback | `870c5ba8-107e-464f-aa66-82822a0b9c3e` | 실제 3,000대, error 266, reward -266 |
| feedback | `unknown-id` | matched false, reward null |

## 6단계: Log Stream → S3 내보내기

| 항목 | 값 |
|---|---|
| 버킷 | `team1-bike-rental-logs-093356173512` (서울, 퍼블릭 액세스 차단) |
| 내보내기 작업 ID | `e6b9ffb4-b8e1-4d53-8580-968252bfd6a4` (COMPLETED) |
| 조회 기간 | 내보내기 시점 기준 최근 1시간 (2026-10-28 07:29~08:29 UTC) |
| 저장 경로 | `bike-logs/run-20261028/e6b9ffb4-b8e1-4d53-8580-968252bfd6a4/bike-api-20261028/000000.gz` (877 bytes) |
| SHA-256 (앞 16자리) | `b9eb33d734066210` |
| 다시 읽은 결과 | 압축 해제 후 10줄 = CloudWatch 원본 10건과 일치 |

S3 파일의 각 줄은 `CloudWatch 수신 시각 + 원래 JSON` 형식이다.

```
2026-10-28T08:27:10.515Z {"event": "prediction", "ts": "2026-10-28T08:27:10.515+00:00", "request_id": "870c5ba8-107e-464f-aa66-82822a0b9c3e", "model_version": "d7a782f5853d", ...}
2026-10-28T08:27:10.523Z {"event": "feedback", "ts": "2026-10-28T08:27:10.523+00:00", "request_id": "870c5ba8-107e-464f-aa66-82822a0b9c3e", ...}
```

## 학습 후보 판단

- 실제값이 연결된 기록(`feedback`, `matched: true`)은 1건이지만, 시험용 실제값(3,000대)이라 학습 후보 0건으로 둔다.
- 입력 오류 5건은 원인 분석용으로 보관하고 학습 후보에서 제외한다.

## 다시 확인하는 방법 (CloudShell)

```sh
aws logs get-log-events --log-group-name /mlops/team1-bike-rental --log-stream-name bike-api-20261028 --start-from-head --query 'events[].message'
aws s3 ls s3://team1-bike-rental-logs-093356173512/bike-logs/ --recursive
```
