# cloud-mlops-team-1

날씨와 시간 정보로 서울 따릉이의 **시간당 자전거 대여 수**를 예측한다. 대여소 운영자가 시간대별 자전거 배치를 미리 정하는 데 사용하는 것을 목표로 한다.

- 데이터 설명·전처리 규칙: [`data/README.md`](data/README.md)
- 입력(5개): Hour, Temperature(°C), Humidity(%), Rainfall(mm), Holiday
- 정답: Rented Bike Count (시간당 대여 수, 단위: 대)

## 폴더 구조

```
data/raw/            # 원본 CSV (수정하지 않음)
data/processed/      # 전처리 결과 (정제·격리·기록)
docs/                # 열 역할과 처리 규칙
src/preprocess.py    # 전처리
src/train.py         # 학습·평가·모델 저장
models/model.joblib  # 학습된 모델
results/metrics.json # 평가 결과
```

## 실행 방법

저장소 최상위 폴더에서 실행한다.

```sh
# 1. 가상환경과 라이브러리 설치 (처음 한 번)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 전처리: data/raw → data/processed
python3 src/preprocess.py

# 3. 학습·평가: models/model.joblib, results/metrics.json 생성
.venv/bin/python src/train.py
```

## 학습 방법

- 입력: `data/processed/bike-clean.csv` (8,448행)
- Holiday는 숫자로 바꾼다 (Holiday=1, No Holiday=0).
- 학습용 80% / 시험용 20%로 랜덤 분할한다 (`random_state=42` 고정). 시험용은 학습에 사용하지 않는다.
- 기준선(학습용 평균값으로 예측), 선형회귀, 랜덤포레스트를 비교하고, MAE가 가장 낮은 모델을 저장한다.

## 결과

시험용 1,690행 기준. MAE는 평균적으로 몇 대 틀렸는지를 뜻한다.

| 모델 | MAE (대) |
|---|---:|
| 기준선 (학습용 평균) | 519.57 |
| 선형회귀 | 339.19 |
| **랜덤포레스트 (채택)** | **168.02** |

### 한계

- Date 열이 없어 시간 순서가 아닌 랜덤 분할을 사용했다. 실제 서비스(미래 예측)보다 점수가 좋게 나올 수 있다.
- 학습에 쓴 날씨는 관측값이다. 실제 서비스에서는 예보값을 입력하게 되므로 오차가 더 커질 수 있다.

## 모델 직접 테스트

```sh
.venv/bin/python -c "
import joblib, pandas as pd
model = joblib.load('models/model.joblib')
cols = ['Hour', 'Temperature(°C)', 'Humidity(%)', 'Rainfall(mm)', 'Holiday']
x = [18, 25, 50, 0, 0]  # [시간, 기온, 습도, 강수량, 공휴일(1/0)]
print('예측 대여 수:', round(model.predict(pd.DataFrame([x], columns=cols))[0]), '대')
"
```
