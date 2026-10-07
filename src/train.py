#!/usr/bin/env python3
"""정제 데이터로 시간당 자전거 대여 수 예측 모델을 학습한다.
학습/검증/평가 3분할: 검증용으로 입력·모델을 고르고, 평가용은 고른 모델에 마지막 한 번만 쓴다.
모든 실험은 MLflow에 기록한다.
"""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

BASE = ['Hour', 'Temperature(°C)', 'Humidity(%)', 'Rainfall(mm)', 'Holiday']
FEATURE_SETS = {  # 입력 비교 실험 (README '개선 과정'과 같은 순서)
    'base5': BASE,
    'base5+weekend': BASE + ['is_weekend'],
    'base5+weekend+month': BASE + ['is_weekend', 'month'],
}
TARGET = 'Rented Bike Count'
SEED = 42  # 누가 실행해도 같은 분할·모델이 나오도록 고정


def digest(path):  # 입력·모델 파일 동일성 확인용 SHA-256
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    df = pd.read_csv(path, encoding='utf-8')
    date = pd.to_datetime(df['Date'], format='%d/%m/%Y')
    df['is_weekend'] = (date.dt.dayofweek >= 5).astype(int)  # 토·일=1
    df['month'] = date.dt.month  # 1~12
    df['Holiday'] = (df['Holiday'] == 'Holiday').astype(int)  # Holiday=1, No Holiday=0
    return df


def make_models():  # 입력 조합마다 새 모델로 학습한다
    return {
        'linear_regression': LinearRegression(),
        # min_samples_leaf=5: 모델 파일을 GitHub 100MB 제한보다 충분히 작게 유지
        'random_forest': RandomForestRegressor(n_estimators=100, min_samples_leaf=5, random_state=SEED, n_jobs=-1),
        'gradient_boosting': HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05, random_state=SEED),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='data/processed/bike-clean.csv')
    parser.add_argument('--model', default='models/model.joblib')
    parser.add_argument('--metrics', default='results/metrics.json')
    args = parser.parse_args()

    df = load(args.input)
    # 1차: 평가용 20%를 먼저 떼어 둔다 → 2차: 나머지 80%를 학습 75% / 검증 25%로 나눈다
    # 결과: 학습 60% / 검증 20% / 평가 20%
    rest, test = train_test_split(df, test_size=0.2, random_state=SEED)
    train, val = train_test_split(rest, test_size=0.25, random_state=SEED)

    # 기준선: 모든 행에 학습용 평균을 답한다
    baseline_val_mae = mean_absolute_error(val[TARGET], [train[TARGET].mean()] * len(val))

    mlflow.set_experiment('bike-rental')
    runs = []
    for set_name, features in FEATURE_SETS.items():
        for model_name, model in make_models().items():
            with mlflow.start_run(run_name=f'{set_name} | {model_name}') as run:
                model.fit(train[features], train[TARGET])  # 검증·평가용은 학습에 쓰지 않는다
                pred = model.predict(val[features])
                val_mae = mean_absolute_error(val[TARGET], pred)
                mlflow.log_params({
                    'feature_set': set_name,
                    'features': ', '.join(features),
                    'model': model_name,
                    'random_state': SEED,
                    'train_rows': len(train),
                    'val_rows': len(val),
                })
                mlflow.log_metrics({
                    'val_mae': val_mae,
                    'val_r2': r2_score(val[TARGET], pred),
                    'val_improvement_pct': (1 - val_mae / baseline_val_mae) * 100,
                })
                runs.append({'run_id': run.info.run_id, 'set_name': set_name, 'features': features,
                             'model_name': model_name, 'model': model, 'val_mae': val_mae})

    # 검증 MAE가 가장 낮은 조합을 고른다. 평가용은 여기까지 한 번도 보지 않았다.
    best = min(runs, key=lambda r: r['val_mae'])
    test_pred = best['model'].predict(test[best['features']])
    test_mae = mean_absolute_error(test[TARGET], test_pred)
    baseline_test_mae = mean_absolute_error(test[TARGET], [train[TARGET].mean()] * len(test))

    model_path = Path(args.model)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best['model'], model_path, compress=3)

    with mlflow.start_run(run_id=best['run_id']):  # 고른 Run에만 평가 결과와 모델 파일을 추가한다
        mlflow.set_tag('selected', 'true')
        mlflow.log_metrics({
            'test_mae': test_mae,
            'test_r2': r2_score(test[TARGET], test_pred),
            'test_improvement_pct': (1 - test_mae / baseline_test_mae) * 100,
        })
        mlflow.log_artifact(str(model_path))

    metrics = {
        'input': args.input,
        'input_sha256': digest(args.input),
        'target': TARGET,
        'split': {'method': 'random', 'train/val/test': '60/20/20', 'random_state': SEED,
                  'train_rows': len(train), 'val_rows': len(val), 'test_rows': len(test)},
        'metric': 'MAE (평균 절대 오차, 단위: 대)',
        'validation': {
            'baseline_mae': round(baseline_val_mae, 2),
            'mae': {f"{r['set_name']} | {r['model_name']}": round(r['val_mae'], 2) for r in runs},
        },
        'selected': {
            'feature_set': best['set_name'],
            'features': best['features'],
            'model': best['model_name'],
            'mlflow_run_id': best['run_id'],
        },
        'test': {
            'baseline_mae': round(baseline_test_mae, 2),
            'mae': round(test_mae, 2),
            'improvement_vs_baseline_pct': round((1 - test_mae / baseline_test_mae) * 100, 1),
            'r2': round(r2_score(test[TARGET], test_pred), 3),
        },
        'model_path': str(model_path),
        'limitation': '시간 순서가 아닌 랜덤 분할이며 데이터가 1년치라 같은 달이 학습·검증·평가에 섞인다. 실제 서비스(미래 예측)보다 점수가 좋게 나올 수 있다.',
    }
    metrics_path = Path(args.metrics)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
