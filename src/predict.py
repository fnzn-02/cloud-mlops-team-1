"""저장된 모델로 시간당 자전거 대여 수를 예측한다.

입력 검사 범위는 docs/column-roles.json의 규칙과 같다.
"""
import datetime
import os
from pathlib import Path

import joblib
import pandas as pd

# 서버 실행 시 MODEL_PATH 환경 변수로 다른 모델 경로를 줄 수 있다 (모델 준비 실패 테스트용)
MODEL_PATH = Path(os.environ.get('MODEL_PATH', 'models/model.joblib'))
FEATURES = ['Hour', 'Temperature(°C)', 'Humidity(%)', 'Rainfall(mm)', 'Holiday', 'is_weekend', 'month']

# 입력 이름: (설명, 최소, 최대). None은 제한 없음
NUMBER_RULES = {
    'hour': ('시간(0~23 정수)', 0, 23),
    'temperature': ('기온(°C)', -30, 45),
    'humidity': ('습도(%)', 1, 100),
    'rainfall': ('강수량(mm)', 0, None),
}
REQUIRED = ['date', *NUMBER_RULES, 'holiday']


def load_model():
    return joblib.load(MODEL_PATH)


def validate(payload):
    """입력을 검사해 오류 목록을 돌려준다. 빈 목록이면 정상이다."""
    errors = []
    for field in REQUIRED:
        if field not in payload or payload[field] is None:
            errors.append({'field': field, 'reason': '필수 항목이 없습니다'})

    date = payload.get('date')
    if date is not None:
        try:
            datetime.date.fromisoformat(date)
        except (TypeError, ValueError):
            errors.append({'field': 'date', 'reason': 'YYYY-MM-DD 형식의 날짜여야 합니다'})

    for field, (label, low, high) in NUMBER_RULES.items():
        value = payload.get(field)
        if value is None:
            continue
        # bool은 숫자로 취급하지 않고, "25"처럼 숫자처럼 생긴 문자열도 거부한다
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append({'field': field, 'reason': f'{label}은(는) 숫자여야 합니다'})
        elif field == 'hour' and value != int(value):
            errors.append({'field': field, 'reason': f'{label}은(는) 정수여야 합니다'})
        elif (low is not None and value < low) or (high is not None and value > high):
            limit = f'{low} 이상' if high is None else f'{low}~{high}'
            errors.append({'field': field, 'reason': f'{label}은(는) {limit}이어야 합니다'})

    holiday = payload.get('holiday')
    if holiday is not None and not isinstance(holiday, bool):
        errors.append({'field': 'holiday', 'reason': 'true 또는 false여야 합니다'})
    return errors


def predict(model, payload):
    """검사를 통과한 입력으로 예측한다. 날짜로 주말 여부와 월을 계산한다."""
    date = datetime.date.fromisoformat(payload['date'])
    row = [[
        int(payload['hour']),
        payload['temperature'],
        payload['humidity'],
        payload['rainfall'],
        int(payload['holiday']),        # 공휴일=1, 평일=0
        int(date.weekday() >= 5),       # 토·일=1
        date.month,                     # 1~12
    ]]
    value = model.predict(pd.DataFrame(row, columns=FEATURES))[0]
    return {'predicted_rentals': max(0, round(float(value))), 'unit': '대'}
