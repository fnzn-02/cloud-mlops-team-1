#!/usr/bin/env python3
"""실행 중인 API에 정상·오류 요청을 보내고 응답을 JSON 파일로 저장한다."""
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

NORMAL = {'date': '2018-06-15', 'hour': 18, 'temperature': 25.0, 'humidity': 50, 'rainfall': 0.0, 'holiday': False}
CASES = {
    'normal': [
        ('health', 'GET', '/health', None),
        ('정상 입력', 'POST', '/predict', NORMAL),
        ('시간 25', 'POST', '/predict', {**NORMAL, 'hour': 25}),
        ('습도에 문자', 'POST', '/predict', {**NORMAL, 'humidity': '많음'}),
        ('강수량 누락', 'POST', '/predict', {k: v for k, v in NORMAL.items() if k != 'rainfall'}),
    ],
    'model-missing': [  # 서버를 없는 모델 경로로 켠 상태에서 실행한다
        ('health', 'GET', '/health', None),
        ('정상 입력', 'POST', '/predict', NORMAL),
    ],
}


def send(base_url, method, path, body):
    data = None if body is None else json.dumps(body).encode('utf-8')
    request = urllib.request.Request(base_url + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:  # 4xx·5xx도 응답 본문을 그대로 기록한다
        return e.code, json.loads(e.read())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--cases', choices=list(CASES), default='normal')
    parser.add_argument('--out', default='results/api-check.json')
    args = parser.parse_args()

    results = []
    for name, method, path, body in CASES[args.cases]:
        status, response = send(args.url, method, path, body)
        results.append({'name': name, 'request': {'method': method, 'path': path, 'body': body},
                        'status': status, 'response': response})
        print(f'{status}  {method} {path}  ({name})')

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'saved: {out}')


if __name__ == '__main__':
    main()
