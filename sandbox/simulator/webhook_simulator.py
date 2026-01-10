#!/usr/bin/env python3
"""
Service Market Webhook Simulator

Service Market이 보내는 Webhook을 시뮬레이션하는 로컬 서버입니다.
개발 업체는 이 시뮬레이터로 자신의 서비스를 테스트할 수 있습니다.

사용법:
    python webhook_simulator.py --port 8001

    # 다른 터미널에서:
    curl -X POST http://localhost:8001/simulate/provision \
        -H "Content-Type: application/json" \
        -d '{"target_url": "http://localhost:8000/api/tenant/webhook/auto-provision"}'
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
import random
import string
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Service Market Webhook Simulator",
    description="Service Market의 Webhook 동작을 시뮬레이션하는 로컬 서버",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 테스트 기록 저장
test_history: List[Dict[str, Any]] = []


class SimulateRequest(BaseModel):
    """시뮬레이션 요청"""
    target_url: str
    api_key: str = "mt_dev_key_12345"
    kind: str = "demo"
    applicant_email: Optional[str] = None
    university_name: Optional[str] = None
    application_id: Optional[int] = None


class SimulateResponse(BaseModel):
    """시뮬레이션 응답"""
    success: bool
    request_sent: Dict[str, Any]
    response_received: Optional[Dict[str, Any]] = None
    status_code: int
    response_time_ms: float
    error: Optional[str] = None


def generate_test_data(kind: str = "demo") -> Dict[str, Any]:
    """테스트 데이터 생성"""
    app_id = random.randint(1000, 9999)
    suffix = ''.join(random.choices(string.ascii_lowercase, k=4))

    universities = [
        "서울대학교", "연세대학교", "고려대학교", "한양대학교",
        "성균관대학교", "이화여자대학교", "중앙대학교", "경희대학교"
    ]

    names = ["김철수", "이영희", "박민수", "최지영", "정현우", "강서연"]

    university = random.choice(universities)
    name = random.choice(names)
    email = f"user_{suffix}@{university.replace('대학교', '')}.ac.kr"

    start_date = datetime.now().strftime("%Y-%m-%d")
    if kind == "demo":
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    else:
        end_date = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

    return {
        "application_id": app_id,
        "kind": kind,
        "contact": f"02-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
        "reason": f"{university} {kind} 신청",
        "applicant": {
            "id": random.randint(1, 100),
            "name": name,
            "email": email,
            "university_name": university
        },
        "service": {
            "id": random.randint(1, 10),
            "slug": "test-service",
            "title": "Test Service"
        },
        "callback_url": "http://simulator:8001/callback",
        "start_date": start_date,
        "end_date": end_date
    }


@app.get("/")
async def root():
    """루트"""
    return {
        "service": "Service Market Webhook Simulator",
        "version": "1.0.0",
        "endpoints": {
            "simulate_provision": "POST /simulate/provision",
            "simulate_custom": "POST /simulate/custom",
            "history": "GET /history",
            "docs": "/docs"
        }
    }


@app.post("/simulate/provision", response_model=SimulateResponse)
async def simulate_provision(request: SimulateRequest):
    """
    테넌트 프로비저닝 Webhook 시뮬레이션

    Service Market이 신청 승인 시 보내는 Webhook을 시뮬레이션합니다.
    """
    # 테스트 데이터 생성
    payload = generate_test_data(request.kind)

    # 사용자 지정 값 덮어쓰기
    if request.applicant_email:
        payload["applicant"]["email"] = request.applicant_email
    if request.university_name:
        payload["applicant"]["university_name"] = request.university_name
    if request.application_id:
        payload["application_id"] = request.application_id

    # Webhook 호출
    start = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                request.target_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": request.api_key
                }
            )
            elapsed = (datetime.now() - start).total_seconds() * 1000

            response_data = None
            try:
                response_data = response.json()
            except:
                pass

            result = SimulateResponse(
                success=response.status_code == 200,
                request_sent=payload,
                response_received=response_data,
                status_code=response.status_code,
                response_time_ms=elapsed
            )

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds() * 1000
        result = SimulateResponse(
            success=False,
            request_sent=payload,
            status_code=0,
            response_time_ms=elapsed,
            error=str(e)
        )

    # 기록 저장
    test_history.append({
        "timestamp": datetime.now().isoformat(),
        "target_url": request.target_url,
        "result": result.dict()
    })

    logger.info(f"Webhook sent to {request.target_url}: {result.success}")

    return result


@app.post("/simulate/custom", response_model=SimulateResponse)
async def simulate_custom(
    target_url: str,
    payload: Dict[str, Any],
    api_key: str = "mt_dev_key_12345"
):
    """
    커스텀 페이로드로 Webhook 시뮬레이션

    원하는 페이로드를 직접 지정하여 Webhook을 테스트합니다.
    """
    start = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                target_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": api_key
                }
            )
            elapsed = (datetime.now() - start).total_seconds() * 1000

            response_data = None
            try:
                response_data = response.json()
            except:
                pass

            return SimulateResponse(
                success=response.status_code == 200,
                request_sent=payload,
                response_received=response_data,
                status_code=response.status_code,
                response_time_ms=elapsed
            )

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds() * 1000
        return SimulateResponse(
            success=False,
            request_sent=payload,
            status_code=0,
            response_time_ms=elapsed,
            error=str(e)
        )


@app.get("/history")
async def get_history(limit: int = 10):
    """테스트 기록 조회"""
    return {
        "count": len(test_history),
        "history": test_history[-limit:][::-1]  # 최신순
    }


@app.delete("/history")
async def clear_history():
    """테스트 기록 삭제"""
    test_history.clear()
    return {"message": "기록이 삭제되었습니다"}


@app.post("/callback")
async def callback(data: Dict[str, Any]):
    """콜백 수신 (비동기 처리용)"""
    logger.info(f"Callback received: {data}")
    return {"received": True, "data": data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
