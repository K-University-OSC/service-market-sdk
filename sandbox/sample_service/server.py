"""
더미 AI 서비스 - Service Market 연동 테스트용

MT-PaaS 문서(AI_SERVICE_QUICKSTART.md)만으로 연동 가능한지 검증하기 위한 서비스
"""

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import os
import re
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="Dummy AI Service",
    description="Service Market 연동 테스트용 더미 서비스",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 환경변수에서 API Key 로드 (문서 기준 기본값)
MT_PAAS_API_KEY = os.getenv("MT_PAAS_API_KEY", "mt_dev_key_12345")
SERVICE_BASE_URL = os.getenv("SERVICE_BASE_URL", "http://220.66.157.70:10210")

# 테넌트 저장소 (메모리 기반 - 실제로는 DB 사용)
tenants_db = {}
applications_db = []


# ============================================================================
# Pydantic 모델 (문서 11.2 기준)
# ============================================================================

class AutoProvisionPayload(BaseModel):
    """Service Market에서 전송하는 Webhook 페이로드 (문서 11.2 기준)"""
    application_id: int
    kind: str  # "demo" or "service"
    contact: Optional[str] = None
    reason: Optional[str] = None
    applicant: dict  # {id, name, email, university_name}
    service: dict    # {id, slug, title}
    callback_url: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD


class AutoProvisionResponse(BaseModel):
    """Webhook 응답 (문서 11.3 기준)"""
    status: str  # "approved", "processing", "rejected", "error"
    tenant_id: Optional[str] = None
    tenant_url: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[str] = None


# ============================================================================
# 헬퍼 함수
# ============================================================================

def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """API Key 검증 (문서 4.1 기준)"""
    if not x_api_key or x_api_key != MT_PAAS_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


def generate_tenant_id(university_name: str, application_id: int, kind: str) -> str:
    """테넌트 ID 생성"""
    # 한글 제거, 특수문자를 언더스코어로 변환
    slug = re.sub(r'[^a-zA-Z0-9]', '_', university_name.lower())[:15]
    prefix = "demo" if kind == "demo" else "svc"
    return f"{prefix}_{slug}_{application_id}"


# ============================================================================
# 기본 엔드포인트
# ============================================================================

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "Dummy AI Service",
        "version": "1.0.0",
        "description": "Service Market 연동 테스트용 더미 서비스",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "webhook": "/api/tenant/webhook/auto-provision"
        }
    }


@app.get("/health")
async def health():
    """헬스체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "tenants_count": len(tenants_db),
        "applications_count": len(applications_db)
    }


# ============================================================================
# Webhook 엔드포인트 (문서 섹션 4 기준)
# ============================================================================

@app.post("/api/tenant/webhook/auto-provision", response_model=AutoProvisionResponse)
async def auto_provision(
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Service Market에서 신청 승인 시 호출되는 Webhook

    문서 기준:
    - 엔드포인트: POST /api/tenant/webhook/auto-provision
    - 인증: X-API-Key 헤더
    - 페이로드: AutoProvisionPayload (문서 11.2)
    - 응답: AutoProvisionResponse (문서 11.3)
    """
    # 1. API Key 검증
    verify_api_key(x_api_key)

    # 2. 페이로드 파싱
    body = await request.json()
    logger.info(f"[Webhook] Received payload: {body}")

    try:
        payload = AutoProvisionPayload(**body)
    except Exception as e:
        logger.error(f"[Webhook] Payload parsing error: {e}")
        return AutoProvisionResponse(
            status="error",
            message=f"페이로드 파싱 오류: {str(e)}"
        )

    # 3. 데이터 추출
    applicant = payload.applicant
    service = payload.service
    university_name = applicant.get("university_name", "Unknown")
    admin_email = applicant.get("email", "")

    # 4. 기존 테넌트 확인 (문서 11.4 - 테넌트 재사용 로직)
    existing_tenant = None
    for tid, tenant in tenants_db.items():
        if tenant.get("admin_email") == admin_email:
            existing_tenant = tenant
            break

    if existing_tenant:
        # 기존 테넌트 재사용
        tenant_id = existing_tenant["id"]
        logger.info(f"[Webhook] Reusing existing tenant: {tenant_id}")

        # 신청 내역 저장
        applications_db.append({
            "id": len(applications_db) + 1,
            "application_id": payload.application_id,
            "tenant_id": tenant_id,
            "kind": payload.kind,
            "applicant_email": admin_email,
            "applicant_name": applicant.get("name"),
            "university_name": university_name,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "created_at": datetime.now().isoformat()
        })

        tenant_url = f"{SERVICE_BASE_URL}/?tenant={tenant_id}"

        return AutoProvisionResponse(
            status="approved",
            tenant_id=tenant_id,
            tenant_url=tenant_url,
            message=f"기존 테넌트 '{tenant_id}'에 신규 서비스 신청이 추가되었습니다."
        )

    # 5. 새 테넌트 생성
    tenant_id = generate_tenant_id(university_name, payload.application_id, payload.kind)

    # 만료일 계산
    if payload.kind == "demo":
        expires_at = datetime.now() + timedelta(days=30)
    else:
        if payload.end_date:
            try:
                expires_at = datetime.strptime(payload.end_date, "%Y-%m-%d")
            except:
                expires_at = datetime.now() + timedelta(days=365)
        else:
            expires_at = datetime.now() + timedelta(days=365)

    # 테넌트 저장
    tenants_db[tenant_id] = {
        "id": tenant_id,
        "name": university_name,
        "admin_email": admin_email,
        "admin_name": applicant.get("name"),
        "kind": payload.kind,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at.isoformat()
    }

    # 신청 내역 저장
    applications_db.append({
        "id": len(applications_db) + 1,
        "application_id": payload.application_id,
        "tenant_id": tenant_id,
        "kind": payload.kind,
        "applicant_email": admin_email,
        "applicant_name": applicant.get("name"),
        "university_name": university_name,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "created_at": datetime.now().isoformat()
    })

    logger.info(f"[Webhook] Created new tenant: {tenant_id}")

    # 6. 응답 반환 (문서 11.3 기준)
    tenant_url = f"{SERVICE_BASE_URL}/?tenant={tenant_id}"

    return AutoProvisionResponse(
        status="approved",
        tenant_id=tenant_id,
        tenant_url=tenant_url,
        message=f"테넌트 '{university_name}' 생성 완료",
        expires_at=expires_at.isoformat()
    )


# ============================================================================
# 테넌트 관리 API (문서 4.1 참고)
# ============================================================================

@app.get("/api/tenant/list")
async def list_tenants():
    """테넌트 목록 조회"""
    return {
        "count": len(tenants_db),
        "tenants": list(tenants_db.values())
    }


@app.get("/api/tenant/status/{tenant_id}")
async def get_tenant_status(tenant_id: str):
    """테넌트 상태 조회"""
    if tenant_id not in tenants_db:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다")

    return tenants_db[tenant_id]


@app.get("/api/applications")
async def list_applications():
    """신청 목록 조회"""
    return {
        "count": len(applications_db),
        "applications": applications_db
    }


# ============================================================================
# 더미 서비스 기능 (실제 AI 기능 시뮬레이션)
# ============================================================================

@app.get("/api/chat")
async def dummy_chat(tenant_id: str = None, message: str = "안녕하세요"):
    """더미 AI 채팅 (테스트용)"""
    if tenant_id and tenant_id not in tenants_db:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다")

    return {
        "tenant_id": tenant_id,
        "user_message": message,
        "ai_response": f"[Dummy AI] 메시지 '{message}'를 받았습니다. 이것은 테스트용 더미 응답입니다.",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# 실행
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10210)
