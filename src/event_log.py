"""예측·피드백 이벤트를 JSON 한 줄로 남긴다. 재학습·강화학습 데이터로 쓴다.

- 항상 콘솔(표준 출력)에 쓴다.
- CLOUDWATCH_LOG_GROUP 환경 변수가 있으면 CloudWatch Logs에도 보낸다 (boto3 + watchtower).
  CloudWatch 연결에 실패해도 서버는 계속 동작하고, 실패 이유를 콘솔에 남긴다.

환경 변수
- CLOUDWATCH_LOG_GROUP  : 로그 그룹 이름 (예: /mlops/bike-api). 없으면 콘솔만 쓴다.
- CLOUDWATCH_LOG_STREAM : 로그 스트림 이름 (기본: bike-api-<컴퓨터 이름>)
- AWS_REGION            : 리전 (기본: ap-northeast-2, 서울)
"""
import datetime
import json
import logging
import os
import socket
import sys

logger = logging.getLogger('bike_events')
logger.setLevel(logging.INFO)
logger.propagate = False  # uvicorn 로그와 섞여 두 번 찍히지 않게 한다

_cloudwatch_handler = None


def setup():
    """콘솔 핸들러를 붙이고, 설정돼 있으면 CloudWatch 핸들러도 붙인다. 여러 번 불러도 한 번만 붙인다."""
    global _cloudwatch_handler
    if not logger.handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(console)

    group = os.environ.get('CLOUDWATCH_LOG_GROUP')
    if not group or _cloudwatch_handler is not None:
        return
    stream = os.environ.get('CLOUDWATCH_LOG_STREAM', f'bike-api-{socket.gethostname()}')
    region = os.environ.get('AWS_REGION', 'ap-northeast-2')
    try:
        import boto3
        import watchtower
        handler = watchtower.CloudWatchLogHandler(
            log_group_name=group,
            log_stream_name=stream,
            boto3_client=boto3.client('logs', region_name=region),
            send_interval=10,  # 10초마다 모아서 보낸다 (기본 60초)
        )
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        _cloudwatch_handler = handler
        log('cloudwatch_ready', log_group=group, log_stream=stream, region=region)
    except Exception as e:  # 자격 증명 없음, 권한 없음, 라이브러리 없음 등
        log('cloudwatch_failed', log_group=group, error=f'{type(e).__name__}: {e}')


def close():
    """서버가 꺼질 때 CloudWatch로 남은 로그를 보낸다."""
    global _cloudwatch_handler
    if _cloudwatch_handler is None:
        return
    try:
        _cloudwatch_handler.close()  # 남은 로그 전송 후 닫는다
    except Exception as e:
        print(json.dumps({'event': 'cloudwatch_close_failed', 'error': str(e)}), file=sys.stderr)
    logger.removeHandler(_cloudwatch_handler)
    _cloudwatch_handler = None


def log(event, **fields):
    """이벤트 하나를 JSON 한 줄로 남긴다. ts는 UTC ISO 시각이다."""
    record = {'event': event, 'ts': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds'), **fields}
    try:
        logger.info(json.dumps(record, ensure_ascii=False, default=str))
    except Exception:  # 로그 때문에 예측 응답이 실패하면 안 된다
        pass
