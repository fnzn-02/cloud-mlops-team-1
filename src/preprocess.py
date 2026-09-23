#!/usr/bin/env python3
"""docs/column-roles.json 규칙으로 원본 CSV를 처리·격리 결과로 나눈다. 원본은 수정하지 않는다."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path


def digest(path):  # 파일 동일성 확인용 SHA-256
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path, encoding):
    with Path(path).open(encoding=encoding, newline='') as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []
    if not columns or len(set(columns)) != len(columns):
        raise ValueError('첫 행에 서로 다른 열 이름이 필요합니다.')
    if any(None in row or None in row.values() for row in rows):
        raise ValueError('열 개수가 다른 행이 있습니다.')
    return columns, rows


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def load_roles(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check_roles(config, columns):
    if set(config['columns']) != set(columns):  # 모든 열에 사람이 정한 역할이 있어야 한다
        raise ValueError('CSV 열과 column-roles.json의 columns가 다릅니다.')
    for name, rule in config['columns'].items():
        if rule.get('role') not in ['feature', 'target', 'identifier', 'exclude', 'split'] or not rule.get('reason'):
            raise ValueError(f'{name}: 역할과 선택 이유를 작성하세요.')


def check_row(row, config):  # 한 행이 규칙을 어긴 이유 목록을 반환한다
    reasons = []
    for name, rule in config['columns'].items():
        value = row[name]
        if not value:
            if rule.get('required', False):
                reasons.append(f'{name}:missing')
            continue
        if rule.get('type') == 'number':
            try:
                number = float(value)
            except ValueError:
                reasons.append(f'{name}:type')
                continue
            if not math.isfinite(number):
                reasons.append(f'{name}:not_finite')
            elif number < rule.get('min', -math.inf) or number > rule.get('max', math.inf):
                reasons.append(f'{name}:range')
        elif rule.get('type') == 'date':
            try:
                datetime.datetime.strptime(value, '%d/%m/%Y')  # 원본 날짜 형식: 일/월/연
            except ValueError:
                reasons.append(f'{name}:type')
        if rule.get('allowed') and value not in rule['allowed']:
            reasons.append(f'{name}:category')
    return reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='data/raw/SeoulBikeData.csv')
    parser.add_argument('--roles', default='docs/column-roles.json')
    parser.add_argument('--out', default='data/processed')
    args = parser.parse_args()

    config = load_roles(args.roles)
    columns, rows = read_csv(args.input, config.get('encoding', 'utf-8-sig'))
    check_roles(config, columns)
    kept_columns = [name for name in columns if config['columns'][name]['role'] != 'exclude']

    clean, quarantine, seen = [], [], set()
    counts = collections.Counter()
    for record_number, row in enumerate(rows, 2):  # 헤더를 1번으로 센 레코드 번호
        normalized = {name: value.strip() for name, value in row.items()}
        reasons = []
        key = tuple(normalized[name] for name in columns)
        if key in seen:  # 첫 행은 두고 후속 중복만 격리
            reasons.append('duplicate')
        seen.add(key)
        reasons += check_row(normalized, config)
        if reasons:
            quarantine.append({'record_number': record_number, **row, 'reason': '|'.join(reasons)})
            counts.update(reasons)
        else:
            clean.append({name: normalized[name] for name in kept_columns})

    out = Path(args.out)
    write_csv(out / 'bike-clean.csv', kept_columns, clean)
    write_csv(out / 'quarantine.csv', ['record_number', *columns, 'reason'], quarantine)
    if len(rows) != len(clean) + len(quarantine):
        raise RuntimeError('입력 행 수와 처리+격리 행 수가 다릅니다.')
    summary = {
        'input': args.input,
        'input_sha256': digest(args.input),
        'roles_sha256': digest(args.roles),
        'input_rows': len(rows),
        'clean_rows': len(clean),
        'quarantine_rows': len(quarantine),
        'quarantine_reasons': dict(counts),
        'clean_columns': kept_columns,
        'clean_sha256': digest(out / 'bike-clean.csv'),
        'quarantine_sha256': digest(out / 'quarantine.csv'),
    }
    (out / 'preprocessing.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
