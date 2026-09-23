#!/usr/bin/env python3
"""정제 데이터로 시간당 자전거 대여 수 예측 모델을 학습·평가하고 가장 좋은 모델을 저장한다."""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

FEATURES = ['Hour', 'Temperature(°C)', 'Humidity(%)', 'Rainfall(mm)', 'Holiday', 'is_weekend']
TARGET = 'Rented Bike Count'
SEED = 42  # 누가 실행해도 같은 분할·모델이 나오도록 고정


def digest(path):  # 입력·모델 파일 동일성 확인용 SHA-256
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_xy(path):
    df = pd.read_csv(path, encoding='utf-8')
    df['is_weekend'] = (pd.to_datetime(df['Date'], format='%d/%m/%Y').dt.dayofweek >= 5).astype(int)  # 토·일=1
    x = df[FEATURES].copy()
    x['Holiday'] = (x['Holiday'] == 'Holiday').astype(int)  # Holiday=1, No Holiday=0
    return x, df[TARGET]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='data/processed/bike-clean.csv')
    parser.add_argument('--model', default='models/model.joblib')
    parser.add_argument('--metrics', default='results/metrics.json')
    args = parser.parse_args()

    x, y = load_xy(args.input)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=SEED)

    # 기준선: 모든 시험 행에 학습용 평균을 답한다
    baseline_mae = mean_absolute_error(y_test, [y_train.mean()] * len(y_test))

    candidates = {
        'linear_regression': LinearRegression(),
        # min_samples_leaf=5: 모델 파일을 GitHub 100MB 제한보다 충분히 작게 유지 (MAE 차이 거의 없음)
        'random_forest': RandomForestRegressor(n_estimators=100, min_samples_leaf=5, random_state=SEED, n_jobs=-1),
    }
    scores = {}
    for name, model in candidates.items():
        model.fit(x_train, y_train)  # 시험용은 학습에 쓰지 않는다
        scores[name] = mean_absolute_error(y_test, model.predict(x_test))

    best = min(scores, key=scores.get)
    model_path = Path(args.model)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(candidates[best], model_path, compress=3)

    metrics = {
        'input': args.input,
        'input_sha256': digest(args.input),
        'features': FEATURES,
        'target': TARGET,
        'split': {'method': 'random', 'test_size': 0.2, 'random_state': SEED,
                  'train_rows': len(x_train), 'test_rows': len(x_test)},
        'metric': 'MAE (평균 절대 오차, 단위: 대)',
        'baseline_mae': round(baseline_mae, 2),
        'mae': {name: round(score, 2) for name, score in scores.items()},
        'best_model': best,
        'model_path': str(model_path),
        'limitation': 'Date 열이 없어 시간 순서가 아닌 랜덤 분할이며, 실제 서비스(미래 예측)보다 점수가 좋게 나올 수 있다.',
    }
    metrics_path = Path(args.metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
