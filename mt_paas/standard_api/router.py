"""
표준 API 라우터 생성기

FastAPI 라우터를 자동으로 생성하여 표준 API를 제공합니다.
"""

import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query, Depends
from .handler import StandardAPIHandler, TenantExistsError, TenantNotFoundError
from .models import (
    HealthResponse,
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    StatusResponse,
    UsageResponse,
    ErrorResponse,
    ErrorCodes,
)


def create_standard_router(
    handler: StandardAPIHandler,
    prefix: str = "/mt",
    api_key_header: str = "X-Market-API-Key",
    api_key_env: str = "MARKET_API_KEY",
    require_auth: bool = True,
) -> APIRouter:
    """
    표준 API 라우터 생성

    Args:
        handler: StandardAPIHandler를 상속받은 핸들러 인스턴스
        prefix: API 경로 prefix (기본: /mt)
        api_key_header: API 키 헤더 이름
        api_key_env: API 키 환경변수 이름
        require_auth: 인증 필수 여부

    Returns:
        APIRouter: FastAPI 라우터

    Example:
        from mt_paas.standard_api import create_standard_router, StandardAPIHandler

        class MyHandler(StandardAPIHandler):
            # 구현...
            pass

        handler = MyHandler()
        router = create_standard_router(handler)
        app.include_router(router)
    """

    router = APIRouter(prefix=prefix, tags=["MT Standard API"])

    # =========================================================================
    # API Key 검증 의존성
    # =========================================================================

    async def verify_api_key(
        api_key: Optional[str] = Header(None, alias=api_key_header)
    ) -> str:
        """API 키 검증"""
        if not require_auth:
            return "no-auth"

        expected_key = os.getenv(api_key_env)
        if not expected_key:
            raise HTTPException(
                status_code=500,
                detail=f"API key not configured. Set {api_key_env} environment variable."
            )

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail=f"Missing {api_key_header} header"
            )

        if api_key != expected_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        return api_key

    # =========================================================================
    # Health Check
    # =========================================================================

    @router.get(
        "/health",
        response_model=HealthResponse,
        summary="헬스체크",
        description="서비스 상태 확인"
    )
    async def health_check() -> HealthResponse:
        """헬스체크 - 인증 불필요"""
        try:
            status = await handler.check_health()
        except Exception:
            status = "unhealthy"

        return HealthResponse(
            status=status,
            version=handler.service_version,
            timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    # =========================================================================
    # Tenant Activate
    # =========================================================================

    @router.post(
        "/tenant/{tenant_id}/activate",
        response_model=ActivateResponse,
        responses={
            409: {"model": ErrorResponse, "description": "Tenant already exists"},
            401: {"model": ErrorResponse, "description": "Unauthorized"},
        },
        summary="테넌트 활성화",
        description="새 테넌트를 생성하고 활성화합니다."
    )
    async def activate_tenant(
        tenant_id: str,
        request: ActivateRequest,
        api_key: str = Depends(verify_api_key)
    ) -> ActivateResponse:
        """테넌트 활성화"""
        # tenant_id 일치 확인
        if request.tenant_id != tenant_id:
            raise HTTPException(
                status_code=400,
                detail="tenant_id in path and body must match"
            )

        try:
            # 전처리 훅
            await handler.before_activate(request)

            # 활성화 실행
            response = await handler.activate_tenant(request)

            # 후처리 훅
            await handler.after_activate(response)

            return response

        except TenantExistsError as e:
            raise HTTPException(
                status_code=409,
                detail={
                    "success": False,
                    "error": ErrorCodes.TENANT_EXISTS,
                    "message": str(e)
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": ErrorCodes.INTERNAL_ERROR,
                    "message": str(e)
                }
            )

    # =========================================================================
    # Tenant Deactivate
    # =========================================================================

    @router.post(
        "/tenant/{tenant_id}/deactivate",
        response_model=DeactivateResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
            401: {"model": ErrorResponse, "description": "Unauthorized"},
        },
        summary="테넌트 비활성화",
        description="테넌트를 비활성화하고 접근을 차단합니다."
    )
    async def deactivate_tenant(
        tenant_id: str,
        request: DeactivateRequest,
        api_key: str = Depends(verify_api_key)
    ) -> DeactivateResponse:
        """테넌트 비활성화"""
        try:
            # 전처리 훅
            await handler.before_deactivate(tenant_id, request)

            # 비활성화 실행
            response = await handler.deactivate_tenant(tenant_id, request)

            # 후처리 훅
            await handler.after_deactivate(response)

            return response

        except TenantNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": ErrorCodes.TENANT_NOT_FOUND,
                    "message": str(e)
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": ErrorCodes.INTERNAL_ERROR,
                    "message": str(e)
                }
            )

    # =========================================================================
    # Tenant Status
    # =========================================================================

    @router.get(
        "/tenant/{tenant_id}/status",
        response_model=StatusResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
            401: {"model": ErrorResponse, "description": "Unauthorized"},
        },
        summary="테넌트 상태 조회",
        description="테넌트의 현재 상태를 조회합니다."
    )
    async def get_tenant_status(
        tenant_id: str,
        api_key: str = Depends(verify_api_key)
    ) -> StatusResponse:
        """테넌트 상태 조회"""
        try:
            return await handler.get_tenant_status(tenant_id)

        except TenantNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": ErrorCodes.TENANT_NOT_FOUND,
                    "message": str(e)
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": ErrorCodes.INTERNAL_ERROR,
                    "message": str(e)
                }
            )

    # =========================================================================
    # Tenant Usage
    # =========================================================================

    @router.get(
        "/tenant/{tenant_id}/usage",
        response_model=UsageResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
            401: {"model": ErrorResponse, "description": "Unauthorized"},
        },
        summary="사용량 조회",
        description="테넌트의 사용량 데이터를 조회합니다."
    )
    async def get_tenant_usage(
        tenant_id: str,
        period: str = Query(
            ...,
            description="조회 기간 (YYYY-MM 형식)",
            example="2026-01"
        ),
        api_key: str = Depends(verify_api_key)
    ) -> UsageResponse:
        """사용량 조회"""
        # period 형식 검증
        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": ErrorCodes.INVALID_REQUEST,
                    "message": "period must be in YYYY-MM format"
                }
            )

        try:
            return await handler.get_tenant_usage(tenant_id, period)

        except TenantNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "success": False,
                    "error": ErrorCodes.TENANT_NOT_FOUND,
                    "message": str(e)
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": ErrorCodes.INTERNAL_ERROR,
                    "message": str(e)
                }
            )

    return router
