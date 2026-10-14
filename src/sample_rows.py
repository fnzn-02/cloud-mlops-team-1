"""평가용 데이터(학습에 안 쓴 20%)에서 사람이 웹페이지로 확인할 샘플 10행을 뽑는다."""
import pandas as pd
from sklearn.model_selection import train_test_split

df = pd.read_csv('data/processed/bike-clean.csv', encoding='utf-8')
rest, test = train_test_split(df, test_size=0.2, random_state=42)  # train.py와 같은 평가용 20%
date = pd.to_datetime(test['Date'], format='%d/%m/%Y')
peak = test[(test['Hour'].isin([8, 18])) & (date.dt.dayofweek < 5)].sample(3, random_state=7)  # 평일 출퇴근 3행
other = test.drop(peak.index).sample(7, random_state=7)  # 나머지 7행
sample = pd.concat([other, peak])

d = pd.to_datetime(sample['Date'], format='%d/%m/%Y')
out = pd.DataFrame({
    'date': d.dt.strftime('%Y-%m-%d'),
    'hour': sample['Hour'],
    'temperature': sample['Temperature(°C)'],
    'humidity': sample['Humidity(%)'],
    'rainfall': sample['Rainfall(mm)'],
    'holiday': sample['Holiday'] == 'Holiday',
    'actual': sample['Rented Bike Count'],
})
print(out.to_string(index=False))