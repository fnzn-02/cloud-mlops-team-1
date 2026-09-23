# 학습용 데이터 설명

## 1. 데이터 개요

이 데이터는 시간과 날씨 등의 정보를 이용하여 자전거 대여량을 예측하기 위한 데이터이다.

주요 데이터는 날짜, 시간, 기온, 습도, 강수량, 적설량, 계절, 공휴일 여부, 운영 여부 등으로 구성되어 있다.

- 원본: `data/raw/SeoulBikeData.csv` (8,760행, 14열, 결측치 없음, 인코딩 latin1)
- 기간: 2017-12-01 ~ 2018-11-30 (1년, 1시간 단위)
- 한 행의 의미: 하루 중 한 시간 동안의 자전거 대여 수와 그 시간의 날씨·계절·공휴일·운영 여부
- 출처: [UCI Seoul Bike Sharing Demand](https://archive.ics.uci.edu/dataset/560/seoul+bike+sharing+demand) (CC BY 4.0). 다운로드한 파일을 바꾸지 않고 그대로 보관한다.
- 이전에는 Date 등 5개 열이 빠진 9열 버전을 썼다. 주말 여부를 만들기 위해 Date가 있는 UCI 원본으로 바꿨으며, 두 파일의 공통 9개 열은 8,760행 모두 순서까지 같다.

## 2. Feature와 Label

### Feature

Feature는 머신러닝 모델이 예측을 수행할 때 사용하는 입력 데이터이다.

### Label

Label은 머신러닝 모델이 예측하고자 하는 값이다.

이 데이터에서는 `Rented Bike Count`(시간당 대여된 자전거 수, 정수, 회귀 목표)가 Label이다.

즉, 시간과 날씨 등의 Feature를 이용하여 자전거 대여량인 Label을 예측하는 것이 이 데이터의 목적이다.

## 3. 데이터 컬럼 설명

| 컬럼 | 설명 | 역할 |
|---|---|---|
| Date | 날짜(일/월/연) | 식별자 → 학습 단계에서 주말 여부(`is_weekend`, 토·일=1) 계산 |
| Rented Bike Count | 해당 시간의 자전거 대여 수 | Label |
| Hour | 시간(0~23) | Feature |
| Temperature(°C) | 기온(°C) | Feature |
| Humidity(%) | 습도(%) | Feature |
| Rainfall(mm) | 강수량(mm) | Feature |
| Holiday | 공휴일 여부 | Feature |
| Snowfall (cm) | 적설량(cm) | 정제 데이터에 남기지만 모델 입력에서 뺌 (눈 온 시간이 5%뿐이고 기온과 겹침) |
| Seasons | 계절 | 정제 데이터에 남기지만 모델 입력에서 뺌 (기온과 정보가 겹침) |
| Wind speed (m/s) | 풍속 | 제외 (열 삭제) |
| Visibility (10m) | 가시거리 | 제외 (열 삭제) |
| Dew point temperature(°C) | 이슬점 온도 | 제외 (열 삭제, 기온·습도와 겹침) |
| Solar Radiation (MJ/m2) | 일사량 | 제외 (열 삭제) |
| Functioning Day | 대여소 운영 여부 | 제외 (No 행 격리 후 열 삭제) |

모델 입력은 Hour, Temperature(°C), Humidity(%), Rainfall(mm), Holiday, is_weekend 6개이다.

열별 역할·허용 범위·판단 이유는 [`docs/column-roles.json`](../docs/column-roles.json)에 있다.

## 4. 예시

다음 데이터가 있다고 가정한다.

- Hour: 8
- Temperature: -7.6℃
- Humidity: 37%
- Rainfall: 0mm
- Snowfall: 0cm
- Seasons: Winter
- Holiday: No Holiday
- Functioning Day: Yes

이러한 Feature를 바탕으로 해당 시간의 `Rented Bike Count`를 예측할 수 있다.

실제 데이터에서는 위 조건에서 자전거 대여량이 930이었다.

## 5. 전처리

### 폴더 구조

```
data/
├── raw/SeoulBikeData.csv        # 원본 (수정하지 않음)
└── processed/
    ├── bike-clean.csv           # 학습에 사용할 정제 데이터
    ├── quarantine.csv           # 제외한 행 (원본 레코드 번호 + 제외 이유)
    └── preprocessing.json       # 행 수·제외 이유별 개수·파일 해시
docs/column-roles.json           # 열 역할과 처리 규칙
src/preprocess.py                # 전처리 코드
```

### 실행 방법

저장소 최상위 폴더에서 실행한다. Python 3 표준 라이브러리만 사용한다.

```sh
python3 src/preprocess.py
```

### 처리 규칙

| 규칙 | 해당 행 | 이유 |
|---|---:|---|
| Functioning Day=No 행 제외 | 295 | 운영하지 않은 날이라 대여량이 항상 0이며 예측 의미가 없다 |
| Humidity(%)=0 행 제외 | 17 | 서울에서 습도 0%는 사실상 불가능해 센서 오류로 판단했다 |

- Date를 포함한 모든 열이 같은 후속 행은 중복으로 제외한다. 현재 해당 행은 없다. 9열 버전에서 중복 후보였던 두 행(레코드 7329, 8241)은 날짜가 2018-10-02와 2018-11-09로 서로 다른 관측이었다.
- Functioning Day=No 행을 제외하면 남은 값이 모두 Yes이므로 `bike-clean.csv`에서는 Functioning Day 열을 뺐다. 역할이 `exclude`인 다른 열도 뺀다.
- 제외한 행은 삭제하지 않고 `quarantine.csv`에 원본 레코드 번호(헤더를 1번으로 센 번호)와 이유를 함께 남긴다.

### 결과

| 구분 | 행 수 |
|---|---:|
| 원본 | 8,760 |
| 정제 (`bike-clean.csv`) | 8,448 |
| 제외 (`quarantine.csv`) | 312 |

8,760 = 8,448 + 312로 입력 행 수와 처리 결과 행 수가 일치한다.

## 6. 확인된 이슈

- 날씨 값은 해당 시간의 관측값이다. 실제 서비스에서는 예보값을 입력하게 되므로 학습 입력과 차이가 날 수 있다.
- Seasons, Holiday 범주형 인코딩은 모델 학습 단계에서 처리한다.
