#!/usr/bin/env python3
"""
Service Market Webhook Simulator

Service Market이 보내는 Webhook을 시뮬레이션하는 로컬 서버입니다.
개발 업체는 이 시뮬레이터로 자신의 서비스를 테스트할 수 있습니다.

주요 기능:
    1. 데모/서비스 신청 관리
    2. 웹훅 전송 및 결과 저장
    3. 통계 조회

사용법:
    # 서버 실행
    python webhook_simulator.py --port 9000

    # 데모 신청 생성 및 웹훅 전송
    curl -X POST http://localhost:9000/applications/demo \
        -H "Content-Type: application/json" \
        -d '{"applicant_email": "test@seoul.ac.kr", "university_name": "서울대학교"}'

    curl -X POST "http://localhost:9000/applications/1/send?target_url=http://localhost:8000/api/tenant/webhook/auto-provision"
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
import random
import string
import logging
import os

from .database import SimulatorDatabase, get_database
from .application_manager import ApplicationManager
from .result_store import ResultStore
from .models import (
    DemoApplicationRequest,
    ServiceApplicationRequest,
    ApplicationResponse,
    WebhookResultResponse,
    StatisticsResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터베이스 경로 (환경 변수로 설정 가능)
DB_PATH = os.getenv("SIMULATOR_DB_PATH", "simulator.db")

# 전역 인스턴스 (서버 시작 시 초기화)
_db: Optional[SimulatorDatabase] = None
_app_manager: Optional[ApplicationManager] = None
_result_store: Optional[ResultStore] = None


def get_db() -> SimulatorDatabase:
    global _db
    if _db is None:
        _db = get_database(DB_PATH)
    return _db


def get_app_manager() -> ApplicationManager:
    global _app_manager
    if _app_manager is None:
        _app_manager = ApplicationManager(get_db())
    return _app_manager


def get_result_store() -> ResultStore:
    global _result_store
    if _result_store is None:
        _result_store = ResultStore(get_db())
    return _result_store


def init_simulator(db_path: str = "simulator.db"):
    """시뮬레이터 초기화 (외부에서 호출 가능)"""
    global _db, _app_manager, _result_store, DB_PATH
    DB_PATH = db_path
    _db = get_database(db_path)
    _app_manager = ApplicationManager(_db)
    _result_store = ResultStore(_db)
    return _db, _app_manager, _result_store


# FastAPI 앱
app = FastAPI(
    title="Service Market Webhook Simulator",
    description="""
서비스 마켓의 Webhook 동작을 시뮬레이션하는 로컬 서버입니다.

## 주요 기능

1. **데모 신청 (30일)**: POST /applications/demo
2. **서비스 신청 (커스텀 기간)**: POST /applications/service
3. **웹훅 전송**: POST /applications/{id}/send
4. **결과 조회**: GET /results
5. **통계 조회**: GET /stats

## 테스트 플로우

1. 신청 생성 → 2. 웹훅 전송 → 3. 결과 확인
    """,
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기존 호환성을 위한 인메모리 기록
test_history: List[Dict[str, Any]] = []


# ============================================================================
# Request/Response Models (기존 호환성)
# ============================================================================

class SimulateRequest(BaseModel):
    """시뮬레이션 요청 (기존 API 호환)"""
    target_url: str
    api_key: str = "mt_dev_key_12345"
    kind: str = "demo"
    applicant_email: Optional[str] = None
    university_name: Optional[str] = None
    application_id: Optional[int] = None


class SimulateResponse(BaseModel):
    """시뮬레이션 응답 (기존 API 호환)"""
    success: bool
    request_sent: Dict[str, Any]
    response_received: Optional[Dict[str, Any]] = None
    status_code: int
    response_time_ms: float
    error: Optional[str] = None


class SendWebhookResponse(BaseModel):
    """웹훅 전송 응답"""
    success: bool
    application: ApplicationResponse
    result: WebhookResultResponse
    message: str


# ============================================================================
# Helper Functions
# ============================================================================

def generate_test_data(kind: str = "demo") -> Dict[str, Any]:
    """테스트 데이터 생성 (기존 API 호환)"""
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
        "callback_url": "http://simulator:9000/callback",
        "start_date": start_date,
        "end_date": end_date
    }


async def send_webhook(
    target_url: str,
    payload: dict,
    api_key: str = "mt_dev_key_12345"
) -> tuple[int, Optional[dict], float, Optional[str]]:
    """
    웹훅 전송

    Returns:
        (status_code, response_body, response_time_ms, error)
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

            return response.status_code, response_data, elapsed, None

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds() * 1000
        return 0, None, elapsed, str(e)


# ============================================================================
# Root & Health Endpoints
# ============================================================================

@app.get("/")
async def root():
    """루트 - API 정보"""
    return {
        "service": "Service Market Webhook Simulator",
        "version": "2.0.0",
        "endpoints": {
            "applications": {
                "create_demo": "POST /applications/demo",
                "create_service": "POST /applications/service",
                "list": "GET /applications",
                "get": "GET /applications/{id}",
                "send_webhook": "POST /applications/{id}/send",
                "delete": "DELETE /applications/{id}"
            },
            "results": {
                "list": "GET /results",
                "get": "GET /results/{id}",
                "by_application": "GET /results/application/{app_id}"
            },
            "stats": "GET /stats",
            "legacy": {
                "simulate_provision": "POST /simulate/provision",
                "simulate_custom": "POST /simulate/custom",
                "history": "GET /history"
            },
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy", "version": "2.0.0"}


# ============================================================================
# Application Management Endpoints
# ============================================================================

@app.post("/applications/demo", response_model=ApplicationResponse)
async def create_demo_application(request: DemoApplicationRequest):
    """
    데모 신청 생성 (30일)

    Request Body:
    ```json
    {
        "applicant_email": "test@seoul.ac.kr",
        "applicant_name": "홍길동",
        "university_name": "서울대학교",
        "service_slug": "test-service",
        "service_title": "Test Service"
    }
    ```
    """
    manager = get_app_manager()
    app = manager.create_demo_application(
        applicant_email=request.applicant_email,
        applicant_name=request.applicant_name,
        university_name=request.university_name,
        service_slug=request.service_slug,
        service_title=request.service_title
    )
    logger.info(f"Demo application created: {app.application_id}")
    return app.to_response()


@app.post("/applications/service", response_model=ApplicationResponse)
async def create_service_application(request: ServiceApplicationRequest):
    """
    서비스 신청 생성 (커스텀 기간)

    Request Body:
    ```json
    {
        "applicant_email": "admin@yonsei.ac.kr",
        "applicant_name": "김관리",
        "university_name": "연세대학교",
        "start_date": "2026-02-01",
        "end_date": "2026-12-31"
    }
    ```
    """
    manager = get_app_manager()
    app = manager.create_service_application(
        applicant_email=request.applicant_email,
        applicant_name=request.applicant_name,
        university_name=request.university_name,
        start_date=request.start_date,
        end_date=request.end_date,
        service_slug=request.service_slug,
        service_title=request.service_title
    )
    logger.info(f"Service application created: {app.application_id}")
    return app.to_response()


@app.get("/applications", response_model=List[ApplicationResponse])
async def list_applications(
    kind: Optional[str] = Query(None, description="demo 또는 service"),
    status: Optional[str] = Query(None, description="pending, sent, completed, failed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """신청 목록 조회"""
    manager = get_app_manager()
    apps = manager.list_applications(
        kind=kind,
        status=status,
        limit=limit,
        offset=offset
    )
    return [app.to_response() for app in apps]


@app.get("/applications/{id}", response_model=ApplicationResponse)
async def get_application(id: int):
    """신청 상세 조회"""
    manager = get_app_manager()
    app = manager.get_application(id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app.to_response()


@app.delete("/applications/{id}")
async def delete_application(id: int):
    """신청 삭제"""
    manager = get_app_manager()
    store = get_result_store()

    # 관련 결과도 삭제
    store.delete_results_for_application(id)

    if not manager.delete_application(id):
        raise HTTPException(status_code=404, detail="Application not found")

    return {"message": "Application deleted", "id": id}


@app.post("/applications/{id}/send", response_model=SendWebhookResponse)
async def send_application_webhook(
    id: int,
    target_url: str = Query(..., description="대상 서비스 URL"),
    api_key: str = Query("mt_dev_key_12345", description="API 키")
):
    """
    신청에 대한 웹훅 전송

    Query Parameters:
    - target_url: 대상 서비스의 웹훅 엔드포인트 (예: http://localhost:8000/api/tenant/webhook/application-approved)
    - api_key: X-API-Key 헤더 값 (기본값: mt_dev_key_12345)

    Example:
    ```
    POST /applications/1/send?target_url=http://localhost:8000/api/tenant/webhook/application-approved
    ```
    """
    manager = get_app_manager()
    store = get_result_store()

    # 신청 조회
    application = manager.get_application(id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # 웹훅 페이로드 생성
    payload = application.to_webhook_payload()

    # 웹훅 전송
    status_code, response_body, response_time, error = await send_webhook(
        target_url=target_url,
        payload=payload,
        api_key=api_key
    )

    # 결과 저장
    result = store.save_result(
        application_id=id,
        target_url=target_url,
        request_payload=payload,
        response_code=status_code,
        response_body=response_body,
        response_time_ms=response_time,
        api_key=api_key,
        error=error
    )

    # 신청 상태 업데이트 (실제 service_market 스펙: success 필드 사용)
    if result.success:
        if response_body and response_body.get("success") is True:
            manager.update_status(id, "completed")
        else:
            manager.update_status(id, "sent")
    else:
        manager.update_status(id, "failed")

    # 갱신된 신청 조회
    updated_app = manager.get_application(id)

    logger.info(f"Webhook sent for application {id}: success={result.success}")

    return SendWebhookResponse(
        success=result.success,
        application=updated_app.to_response(),
        result=result.to_response(),
        message="Webhook sent successfully" if result.success else f"Webhook failed: {error or 'Unknown error'}"
    )


# ============================================================================
# Results Endpoints
# ============================================================================

@app.get("/results", response_model=List[WebhookResultResponse])
async def list_results(
    limit: int = Query(50, ge=1, le=200),
    success_only: bool = Query(False, description="성공한 결과만")
):
    """웹훅 결과 목록 조회"""
    store = get_result_store()
    if success_only:
        results = store.get_successful_results(limit)
    else:
        results = store.get_latest_results(limit)
    return [r.to_response() for r in results]


@app.get("/results/{id}", response_model=WebhookResultResponse)
async def get_result(id: int):
    """웹훅 결과 상세 조회"""
    store = get_result_store()
    result = store.get_result(id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result.to_response()


@app.get("/results/application/{app_id}", response_model=List[WebhookResultResponse])
async def get_application_results(app_id: int):
    """특정 신청의 모든 웹훅 결과 조회"""
    store = get_result_store()
    results = store.get_results_for_application(app_id)
    return [r.to_response() for r in results]


@app.delete("/results")
async def clear_results():
    """모든 웹훅 결과 삭제"""
    store = get_result_store()
    count = store.clear_all()
    return {"message": f"Cleared {count} results"}


# ============================================================================
# Statistics Endpoint
# ============================================================================

@app.get("/stats", response_model=StatisticsResponse)
async def get_statistics():
    """통계 조회"""
    store = get_result_store()
    return store.get_statistics()


# ============================================================================
# Tenant Admin Query Endpoints (테넌트 어드민 조회)
# ============================================================================

class TenantQueryRequest(BaseModel):
    """테넌트 조회 요청"""
    target_base_url: str  # 회사 서비스 기본 URL (예: http://company-service.com)
    api_key: str = "mt_dev_key_12345"


class TenantInfo(BaseModel):
    """테넌트 정보"""
    tenant_id: str
    university_name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    users_count: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None


class TenantListResponse(BaseModel):
    """테넌트 목록 응답"""
    success: bool
    tenants: List[TenantInfo]
    total: int
    message: Optional[str] = None


class TenantDetailResponse(BaseModel):
    """테넌트 상세 응답"""
    success: bool
    tenant: Optional[TenantInfo] = None
    users: Optional[List[Dict[str, Any]]] = None
    stats: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


@app.post("/admin/tenants", response_model=TenantListResponse)
async def query_tenant_list(request: TenantQueryRequest):
    """
    회사 서비스의 테넌트 목록 조회

    서비스 마켓에서 회사 서비스에 등록된 테넌트 목록을 조회합니다.
    회사 서비스는 GET /api/tenant/list 엔드포인트를 구현해야 합니다.

    Example:
    ```json
    {
        "target_base_url": "http://localhost:8580",
        "api_key": "mt_dev_key_12345"
    }
    ```
    """
    target_url = f"{request.target_base_url.rstrip('/')}/api/tenant/list"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                target_url,
                headers={"X-API-Key": request.api_key}
            )

            if response.status_code == 200:
                data = response.json()
                tenants = data.get("tenants", [])
                return TenantListResponse(
                    success=True,
                    tenants=[TenantInfo(**t) if isinstance(t, dict) else TenantInfo(tenant_id=str(t)) for t in tenants],
                    total=len(tenants),
                    message=f"조회 성공: {len(tenants)}개 테넌트"
                )
            else:
                return TenantListResponse(
                    success=False,
                    tenants=[],
                    total=0,
                    message=f"조회 실패: HTTP {response.status_code}"
                )

    except Exception as e:
        return TenantListResponse(
            success=False,
            tenants=[],
            total=0,
            message=f"연결 오류: {str(e)}"
        )


@app.post("/admin/tenants/{tenant_id}", response_model=TenantDetailResponse)
async def query_tenant_detail(
    tenant_id: str,
    request: TenantQueryRequest
):
    """
    회사 서비스의 테넌트 상세 조회

    특정 테넌트의 상세 정보, 사용자 목록, 사용 통계를 조회합니다.
    회사 서비스는 GET /api/tenant/status/{tenant_id} 엔드포인트를 구현해야 합니다.

    Example:
    ```json
    {
        "target_base_url": "http://localhost:8580",
        "api_key": "mt_dev_key_12345"
    }
    ```
    """
    base_url = request.target_base_url.rstrip('/')

    result = TenantDetailResponse(success=True)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. 테넌트 상태 조회
            status_url = f"{base_url}/api/tenant/status/{tenant_id}"
            status_resp = await client.get(
                status_url,
                headers={"X-API-Key": request.api_key}
            )

            if status_resp.status_code == 200:
                status_data = status_resp.json()
                result.tenant = TenantInfo(
                    tenant_id=tenant_id,
                    university_name=status_data.get("university_name"),
                    email=status_data.get("email"),
                    status=status_data.get("status"),
                    created_at=status_data.get("created_at"),
                    users_count=status_data.get("users_count"),
                    extra=status_data
                )
            else:
                result.success = False
                result.message = f"테넌트 조회 실패: HTTP {status_resp.status_code}"
                return result

            # 2. 사용자 목록 조회 (선택적)
            try:
                users_url = f"{base_url}/api/tenant/{tenant_id}/users"
                users_resp = await client.get(
                    users_url,
                    headers={"X-API-Key": request.api_key}
                )
                if users_resp.status_code == 200:
                    users_data = users_resp.json()
                    result.users = users_data.get("users", [])
            except:
                pass  # 사용자 목록 API가 없을 수 있음

            # 3. 통계 조회 (선택적)
            try:
                stats_url = f"{base_url}/api/tenant/{tenant_id}/stats"
                stats_resp = await client.get(
                    stats_url,
                    headers={"X-API-Key": request.api_key}
                )
                if stats_resp.status_code == 200:
                    result.stats = stats_resp.json()
            except:
                pass  # 통계 API가 없을 수 있음

            result.message = "조회 성공"
            return result

    except Exception as e:
        return TenantDetailResponse(
            success=False,
            message=f"연결 오류: {str(e)}"
        )


@app.post("/admin/tenants/{tenant_id}/users")
async def query_tenant_users(
    tenant_id: str,
    request: TenantQueryRequest
):
    """
    테넌트 사용자 목록 조회

    회사 서비스에서 특정 테넌트의 사용자 목록을 조회합니다.
    """
    target_url = f"{request.target_base_url.rstrip('/')}/api/tenant/{tenant_id}/users"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                target_url,
                headers={"X-API-Key": request.api_key}
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "조회 성공"
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "message": f"조회 실패: HTTP {response.status_code}"
                }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "message": f"연결 오류: {str(e)}"
        }


@app.post("/admin/tenants/{tenant_id}/stats")
async def query_tenant_stats(
    tenant_id: str,
    request: TenantQueryRequest
):
    """
    테넌트 사용 통계 조회

    회사 서비스에서 특정 테넌트의 사용 통계를 조회합니다.
    """
    target_url = f"{request.target_base_url.rstrip('/')}/api/tenant/{tenant_id}/stats"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                target_url,
                headers={"X-API-Key": request.api_key}
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json(),
                    "message": "조회 성공"
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "message": f"조회 실패: HTTP {response.status_code}"
                }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "message": f"연결 오류: {str(e)}"
        }


# ============================================================================
# Legacy Endpoints (기존 API 호환성 유지)
# ============================================================================

@app.post("/simulate/provision", response_model=SimulateResponse)
async def simulate_provision(request: SimulateRequest):
    """
    [Legacy] 테넌트 프로비저닝 Webhook 시뮬레이션

    Service Market이 신청 승인 시 보내는 Webhook을 시뮬레이션합니다.
    새 API 사용을 권장합니다: POST /applications/demo + POST /applications/{id}/send
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
    status_code, response_data, elapsed, error = await send_webhook(
        target_url=request.target_url,
        payload=payload,
        api_key=request.api_key
    )

    result = SimulateResponse(
        success=status_code == 200,
        request_sent=payload,
        response_received=response_data,
        status_code=status_code,
        response_time_ms=elapsed,
        error=error
    )

    # 기록 저장 (인메모리)
    test_history.append({
        "timestamp": datetime.now().isoformat(),
        "target_url": request.target_url,
        "result": result.dict()
    })

    logger.info(f"[Legacy] Webhook sent to {request.target_url}: success={result.success}")

    return result


@app.post("/simulate/custom", response_model=SimulateResponse)
async def simulate_custom(
    target_url: str,
    payload: Dict[str, Any],
    api_key: str = "mt_dev_key_12345"
):
    """
    [Legacy] 커스텀 페이로드로 Webhook 시뮬레이션

    원하는 페이로드를 직접 지정하여 Webhook을 테스트합니다.
    """
    status_code, response_data, elapsed, error = await send_webhook(
        target_url=target_url,
        payload=payload,
        api_key=api_key
    )

    return SimulateResponse(
        success=status_code == 200,
        request_sent=payload,
        response_received=response_data,
        status_code=status_code,
        response_time_ms=elapsed,
        error=error
    )


@app.get("/history")
async def get_history(limit: int = 10):
    """[Legacy] 테스트 기록 조회 (인메모리)"""
    return {
        "count": len(test_history),
        "history": test_history[-limit:][::-1]  # 최신순
    }


@app.delete("/history")
async def clear_history():
    """[Legacy] 테스트 기록 삭제 (인메모리)"""
    test_history.clear()
    return {"message": "기록이 삭제되었습니다"}


@app.post("/callback")
async def callback(data: Dict[str, Any]):
    """콜백 수신 (비동기 처리용)"""
    logger.info(f"Callback received: {data}")
    return {"received": True, "data": data}


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 DB 초기화"""
    init_simulator(DB_PATH)
    logger.info(f"Simulator initialized with DB: {DB_PATH}")


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="Service Market Webhook Simulator")
    parser.add_argument("--port", type=int, default=9000, help="Server port")
    parser.add_argument("--host", default="0.0.0.0", help="Server host")
    parser.add_argument("--db", default="simulator.db", help="Database path")
    args = parser.parse_args()

    DB_PATH = args.db
    uvicorn.run(app, host=args.host, port=args.port)
