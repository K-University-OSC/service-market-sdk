"""
Service Market API 엔드포인트

Service Market에서 제공하는 관리 API
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from .client import ServiceMarketClient
from .models import TenantActivation, TenantDeactivation, UsageReport

logger = logging.getLogger(__name__)

router = APIRouter()


# 전역 클라이언트 (앱 시작 시 설정)
_market_client: Optional[ServiceMarketClient] = None


def get_market_client() -> ServiceMarketClient:
    """Market 클라이언트 의존성"""
    if _market_client is None:
        raise HTTPException(
            status_code=500,
            detail="Service Market not initialized"
        )
    return _market_client


def set_market_client(client: ServiceMarketClient):
    """Market 클라이언트 설정"""
    global _market_client
    _market_client = client


# =============================================================================
# Request/Response Models
# =============================================================================

class ServiceRegisterRequest(BaseModel):
    """서비스 등록 요청"""
    service_id: str
    name: str
    base_url: str
    api_key: str
    description: Optional[str] = None
    category: str = "education"


class ActivateTenantRequest(BaseModel):
    """테넌트 활성화 요청"""
    tenant_id: str
    tenant_name: str
    plan: str
    features: List[str]
    config: Optional[dict] = None
    contact_email: str
    contact_name: str


class DeactivateTenantRequest(BaseModel):
    """테넌트 비활성화 요청"""
    reason: str
    preserve_data: bool = True


# =============================================================================
# 서비스 관리 API
# =============================================================================

@router.post("/services/register")
async def register_service(
    request: ServiceRegisterRequest,
    market: ServiceMarketClient = Depends(get_market_client)
):
    """서비스 등록"""
    try:
        market.register_service(
            service_id=request.service_id,
            base_url=request.base_url,
            api_key=request.api_key,
        )
        return {
            "success": True,
            "service_id": request.service_id,
            "message": f"Service {request.name} registered"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/health")
async def check_all_services(
    market: ServiceMarketClient = Depends(get_market_client)
):
    """모든 서비스 헬스체크"""
    return await market.health_check_all()


@router.get("/services/{service_id}/health")
async def check_service_health(
    service_id: str,
    market: ServiceMarketClient = Depends(get_market_client)
):
    """특정 서비스 헬스체크"""
    try:
        client = market.get_service(service_id)
        return await client.health_check()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# 테넌트 관리 API
# =============================================================================

@router.post("/services/{service_id}/tenants/{tenant_id}/activate")
async def activate_tenant(
    service_id: str,
    tenant_id: str,
    request: ActivateTenantRequest,
    market: ServiceMarketClient = Depends(get_market_client)
):
    """테넌트 활성화"""
    if request.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail="tenant_id in path and body must match"
        )

    try:
        activation = TenantActivation(
            tenant_id=tenant_id,
            tenant_name=request.tenant_name,
            service_id=service_id,
            plan=request.plan,
            features=request.features,
            config=request.config,
            contact_email=request.contact_email,
            contact_name=request.contact_name,
        )
        result = await market.activate_tenant(service_id, activation)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Activation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/{service_id}/tenants/{tenant_id}/deactivate")
async def deactivate_tenant(
    service_id: str,
    tenant_id: str,
    request: DeactivateTenantRequest,
    market: ServiceMarketClient = Depends(get_market_client)
):
    """테넌트 비활성화"""
    try:
        deactivation = TenantDeactivation(
            tenant_id=tenant_id,
            service_id=service_id,
            reason=request.reason,
            preserve_data=request.preserve_data,
        )
        result = await market.deactivate_tenant(service_id, deactivation)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Deactivation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/{service_id}/tenants/{tenant_id}/status")
async def get_tenant_status(
    service_id: str,
    tenant_id: str,
    market: ServiceMarketClient = Depends(get_market_client)
):
    """테넌트 상태 조회"""
    try:
        client = market.get_service(service_id)
        return await client.get_tenant_status(tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/services/{service_id}/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    service_id: str,
    tenant_id: str,
    period: str = Query(..., description="YYYY-MM format"),
    market: ServiceMarketClient = Depends(get_market_client)
):
    """테넌트 사용량 조회"""
    try:
        client = market.get_service(service_id)
        return await client.get_tenant_usage(tenant_id, period)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# 빌링 API
# =============================================================================

@router.get("/tenants/{tenant_id}/billing/summary")
async def get_billing_summary(
    tenant_id: str,
    period: str = Query(..., description="YYYY-MM format"),
    market: ServiceMarketClient = Depends(get_market_client)
):
    """테넌트 통합 빌링 요약"""
    usage_reports = await market.get_all_usage(tenant_id, period)

    total_cost = sum(
        report.total_cost or 0
        for report in usage_reports.values()
    )

    return {
        "tenant_id": tenant_id,
        "period": period,
        "services": {
            service_id: {
                "metrics": [m.dict() for m in report.metrics],
                "cost": report.total_cost
            }
            for service_id, report in usage_reports.items()
        },
        "total_cost": total_cost,
        "currency": "KRW"
    }


def create_market_router(market_client: ServiceMarketClient) -> APIRouter:
    """Market 라우터 생성"""
    set_market_client(market_client)
    return router
