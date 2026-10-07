"""시간당 자전거 대여 수 예측 API.

실행 (저장소 최상위 폴더): uvicorn src.api:app
- GET  /health  : 서버·모델 상태 (정상 200, 모델 준비 실패 503)
- POST /predict : 예측 (정상 200, 입력 오류 422, 모델 준비 실패 503)
"""
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse

from src import predict

state = {'model': None, 'error': None}


@asynccontextmanager
async def lifespan(app):
    try:  # 서버가 시작될 때 모델을 한 번만 읽는다
        state['model'] = predict.load_model()
    except Exception as e:  # 모델이 없거나 손상돼도 서버는 켜 두고 503으로 알린다
        state['error'] = f'{type(e).__name__}: {e}'
    yield


app = FastAPI(title='Seoul Bike Rental Prediction', lifespan=lifespan)


def model_not_ready():
    return JSONResponse(status_code=503, content={'status': 'error', 'reason': '모델을 읽지 못했습니다', 'detail': state['error']})


@app.get('/health')
def health():
    if state['model'] is None:
        return model_not_ready()
    return {'status': 'ok', 'model_path': str(predict.MODEL_PATH)}


@app.post('/predict')
def predict_rentals(payload: dict = Body(...)):
    if state['model'] is None:
        return model_not_ready()
    errors = predict.validate(payload)
    if errors:
        return JSONResponse(status_code=422, content={'errors': errors})
    return predict.predict(state['model'], payload)
