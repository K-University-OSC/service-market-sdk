"""
표준 API v2 라우터 생성기

기존 라우터 + 대시보드/사용자관리/리소스/설정 API 엔드포인트 확장
"""

import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query, Depends, Path
from .handler import TenantNotFoundError
from .handler_v2 import (
    StandardAPIHandlerV2,
    UserExistsError,
    UserNotFoundError,
    QuotaExceededError,
    FeatureDisabledError,
)
from .models import HealthResponse, ErrorCodes
from .models_v2 import (
    # 기존 모델
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    StatusResponse,
    UsageResponse,
    ErrorResponse,
    # 신규 모델 - Dashboard
    StatsResponse,
    CostsResponse,
    TopUsersResponse,
    # 신규 모델 - Users
    UserFilters,
    UsersListResponse,
    CreateUserRequest,
    CreateUserResponse,
    UpdateUserRequest,
    UserInfo,
    DeleteUserResponse,
    UserRole,
    UserStatus,
    # 신규 모델 - Resources
    ResourceFilters,
    ResourcesResponse,
    ResourceType,
    # 신규 모델 - Settings
    SettingsResponse,
    UpdateSettingsRequest,
    # 에러 코드
    ErrorCodesV2,
)


def create_standard_router_v2(
    handler: StandardAPIHandlerV2,
    prefix: str = "/mt",
    api_key_header: str = "X-Market-API-Key",
    api_key_env: str = "MARKET_API_KEY",
    require_auth: bool = True,
) -> APIRouter:
    """
    표준 API v2 라우터 생성

    Args:
        handler: StandardAPIHandlerV2를 상속받은 핸들러 인스턴스
        prefix: API 경로 prefix (기본: /mt)
        api_key_header: API 키 헤더 이름
        api_key_env: API 키 환경변수 이름
        require_auth: 인증 필수 여부

    Returns:
        APIRouter: FastAPI 라우터

    Example:
        from mt_paas.standard_api import create_standard_router_v2, StandardAPIHandlerV2

        class MyHandler(StandardAPIHandlerV2):
            # 구현...
            pass

        handler = MyHandler()
        router = create_standard_router_v2(handler)
        app.include_router(router)
    """

    router = APIRouter(prefix=prefix, tags=["MT Standard API v2"])

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
    # Tenant Lifecycle (기존)
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
        if request.tenant_id != tenant_id:
            raise HTTPException(
                status_code=400,
                detail="tenant_id in path and body must match"
            )

        try:
            await handler.before_activate(request)
            response = await handler.activate_tenant(request)
            await handler.after_activate(response)
            return response

        except Exception as e:
            if "exists" in str(e).lower():
                raise HTTPException(status_code=409, detail=_error_detail(ErrorCodes.TENANT_EXISTS, e))
            raise HTTPException(status_code=500, detail=_error_detail(ErrorCodes.INTERNAL_ERROR, e))

    @router.post(
        "/tenant/{tenant_id}/deactivate",
        response_model=DeactivateResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
            401: {"model": ErrorResponse, "description": "Unauthorized"},
        },
        summary="테넌트 비활성화",
        description="테넌트를 비활성화합니다."
    )
    async def deactivate_tenant(
        tenant_id: str,
        request: DeactivateRequest,
        api_key: str = Depends(verify_api_key)
    ) -> DeactivateResponse:
        """테넌트 비활성화"""
        try:
            await handler.before_deactivate(tenant_id, request)
            response = await handler.deactivate_tenant(tenant_id, request)
            await handler.after_deactivate(response)
            return response

        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=_error_detail(ErrorCodes.INTERNAL_ERROR, e))

    @router.get(
        "/tenant/{tenant_id}/status",
        response_model=StatusResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="테넌트 상태 조회"
    )
    async def get_tenant_status(
        tenant_id: str,
        api_key: str = Depends(verify_api_key)
    ) -> StatusResponse:
        """테넌트 상태 조회"""
        try:
            return await handler.get_tenant_status(tenant_id)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    @router.get(
        "/tenant/{tenant_id}/usage",
        response_model=UsageResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="사용량 조회"
    )
    async def get_tenant_usage(
        tenant_id: str,
        period: str = Query(..., description="조회 기간 (YYYY-MM)", example="2026-01"),
        api_key: str = Depends(verify_api_key)
    ) -> UsageResponse:
        """사용량 조회"""
        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError:
            raise HTTPException(status_code=400, detail=_error_detail(ErrorCodes.INVALID_REQUEST, "period must be in YYYY-MM format"))

        try:
            return await handler.get_tenant_usage(tenant_id, period)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    # =========================================================================
    # Dashboard API (신규)
    # =========================================================================

    @router.get(
        "/tenant/{tenant_id}/stats",
        response_model=StatsResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="대시보드 통계",
        description="Service Market 대시보드용 테넌트 통계 조회"
    )
    async def get_tenant_stats(
        tenant_id: str,
        period: str = Query(default="30d", description="조회 기간 (7d, 30d, 90d)", example="30d"),
        api_key: str = Depends(verify_api_key)
    ) -> StatsResponse:
        """대시보드 통계 조회"""
        try:
            return await handler.get_tenant_stats(tenant_id, period)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    @router.get(
        "/tenant/{tenant_id}/stats/costs",
        response_model=CostsResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="비용 분석",
        description="모델별, 사용자별 비용 분석"
    )
    async def get_tenant_costs(
        tenant_id: str,
        period: str = Query(default="30d", description="조회 기간"),
        api_key: str = Depends(verify_api_key)
    ) -> CostsResponse:
        """비용 분석 조회"""
        try:
            return await handler.get_tenant_costs(tenant_id, period)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    @router.get(
        "/tenant/{tenant_id}/stats/top-users",
        response_model=TopUsersResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="활성 사용자 목록"
    )
    async def get_top_users(
        tenant_id: str,
        period: str = Query(default="30d", description="조회 기간"),
        limit: int = Query(default=10, ge=1, le=50, description="최대 개수"),
        api_key: str = Depends(verify_api_key)
    ) -> TopUsersResponse:
        """활성 사용자 목록 조회"""
        try:
            return await handler.get_top_users(tenant_id, period, limit)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    # =========================================================================
    # User Management API (신규)
    # =========================================================================

    @router.get(
        "/tenant/{tenant_id}/users",
        response_model=UsersListResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="사용자 목록",
        description="Service Market에서 테넌트 사용자 관리"
    )
    async def list_users(
        tenant_id: str,
        role: Optional[UserRole] = Query(default=None, description="역할 필터"),
        status: Optional[UserStatus] = Query(default=None, description="상태 필터"),
        search: Optional[str] = Query(default=None, description="검색어"),
        limit: int = Query(default=20, ge=1, le=100, description="페이지 크기"),
        offset: int = Query(default=0, ge=0, description="오프셋"),
        api_key: str = Depends(verify_api_key)
    ) -> UsersListResponse:
        """사용자 목록 조회"""
        filters = UserFilters(
            role=role,
            status=status,
            search=search,
            limit=limit,
            offset=offset
        )
        try:
            return await handler.list_users(tenant_id, filters)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    @router.post(
        "/tenant/{tenant_id}/users",
        response_model=CreateUserResponse,
        status_code=201,
        responses={
            409: {"model": ErrorResponse, "description": "User already exists"},
            404: {"model": ErrorResponse, "description": "Tenant not found"},
            429: {"model": ErrorResponse, "description": "Quota exceeded"},
        },
        summary="사용자 생성"
    )
    async def create_user(
        tenant_id: str,
        request: CreateUserRequest,
        api_key: str = Depends(verify_api_key)
    ) -> CreateUserResponse:
        """사용자 생성"""
        try:
            return await handler.create_user(tenant_id, request)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))
        except UserExistsError as e:
            raise HTTPException(status_code=409, detail=_error_detail(ErrorCodesV2.USER_EXISTS, e))
        except QuotaExceededError as e:
            raise HTTPException(status_code=429, detail=_error_detail(ErrorCodesV2.QUOTA_EXCEEDED, e))

    @router.get(
        "/tenant/{tenant_id}/users/{user_id}",
        response_model=UserInfo,
        responses={
            404: {"model": ErrorResponse, "description": "User or tenant not found"},
        },
        summary="사용자 조회"
    )
    async def get_user(
        tenant_id: str,
        user_id: str = Path(..., description="사용자 ID"),
        api_key: str = Depends(verify_api_key)
    ) -> UserInfo:
        """사용자 조회"""
        try:
            return await handler.get_user(tenant_id, user_id)
        except (TenantNotFoundError, UserNotFoundError) as e:
            code = ErrorCodes.TENANT_NOT_FOUND if isinstance(e, TenantNotFoundError) else ErrorCodesV2.USER_NOT_FOUND
            raise HTTPException(status_code=404, detail=_error_detail(code, e))

    @router.put(
        "/tenant/{tenant_id}/users/{user_id}",
        response_model=UserInfo,
        responses={
            404: {"model": ErrorResponse, "description": "User or tenant not found"},
        },
        summary="사용자 수정"
    )
    async def update_user(
        tenant_id: str,
        user_id: str = Path(..., description="사용자 ID"),
        request: UpdateUserRequest = None,
        api_key: str = Depends(verify_api_key)
    ) -> UserInfo:
        """사용자 수정"""
        try:
            return await handler.update_user(tenant_id, user_id, request)
        except (TenantNotFoundError, UserNotFoundError) as e:
            code = ErrorCodes.TENANT_NOT_FOUND if isinstance(e, TenantNotFoundError) else ErrorCodesV2.USER_NOT_FOUND
            raise HTTPException(status_code=404, detail=_error_detail(code, e))

    @router.delete(
        "/tenant/{tenant_id}/users/{user_id}",
        response_model=DeleteUserResponse,
        responses={
            404: {"model": ErrorResponse, "description": "User or tenant not found"},
        },
        summary="사용자 삭제"
    )
    async def delete_user(
        tenant_id: str,
        user_id: str = Path(..., description="사용자 ID"),
        api_key: str = Depends(verify_api_key)
    ) -> DeleteUserResponse:
        """사용자 삭제"""
        try:
            return await handler.delete_user(tenant_id, user_id)
        except (TenantNotFoundError, UserNotFoundError) as e:
            code = ErrorCodes.TENANT_NOT_FOUND if isinstance(e, TenantNotFoundError) else ErrorCodesV2.USER_NOT_FOUND
            raise HTTPException(status_code=404, detail=_error_detail(code, e))

    # =========================================================================
    # Resource API (신규)
    # =========================================================================

    @router.get(
        "/tenant/{tenant_id}/resources",
        response_model=ResourcesResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="리소스 목록",
        description="코스, 토론, 문서 등 서비스별 리소스 조회"
    )
    async def list_resources(
        tenant_id: str,
        type: Optional[ResourceType] = Query(default=None, description="리소스 타입"),
        search: Optional[str] = Query(default=None, description="검색어"),
        limit: int = Query(default=20, ge=1, le=100, description="페이지 크기"),
        offset: int = Query(default=0, ge=0, description="오프셋"),
        api_key: str = Depends(verify_api_key)
    ) -> ResourcesResponse:
        """리소스 목록 조회"""
        filters = ResourceFilters(
            type=type,
            search=search,
            limit=limit,
            offset=offset
        )
        try:
            return await handler.list_resources(tenant_id, filters)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    # =========================================================================
    # Settings API (신규)
    # =========================================================================

    @router.get(
        "/tenant/{tenant_id}/settings",
        response_model=SettingsResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="테넌트 설정 조회"
    )
    async def get_settings(
        tenant_id: str,
        api_key: str = Depends(verify_api_key)
    ) -> SettingsResponse:
        """테넌트 설정 조회"""
        try:
            return await handler.get_settings(tenant_id)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))

    @router.put(
        "/tenant/{tenant_id}/settings",
        response_model=SettingsResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Tenant not found"},
        },
        summary="테넌트 설정 수정"
    )
    async def update_settings(
        tenant_id: str,
        request: UpdateSettingsRequest,
        api_key: str = Depends(verify_api_key)
    ) -> SettingsResponse:
        """테넌트 설정 수정"""
        try:
            return await handler.update_settings(tenant_id, request)
        except TenantNotFoundError as e:
            raise HTTPException(status_code=404, detail=_error_detail(ErrorCodes.TENANT_NOT_FOUND, e))
        except FeatureDisabledError as e:
            raise HTTPException(status_code=403, detail=_error_detail(ErrorCodesV2.FEATURE_DISABLED, e))

    return router


# =============================================================================
# Service Market 호환 라우터 (Alias)
# =============================================================================

def create_service_market_compat_router(
    handler: StandardAPIHandlerV2,
    api_key_header: str = "X-API-Key",
    api_key_env: str = "MARKET_API_KEY",
) -> APIRouter:
    """
    Service Market 기존 경로 호환 라우터 생성

    기존 Service Market이 사용하던 /api/tenant/* 경로를 mt_paas 표준 경로로 매핑합니다.

    Example:
        compat_router = create_service_market_compat_router(handler)
        app.include_router(compat_router)
    """

    router = APIRouter(prefix="/api/tenant", tags=["Service Market Compat"])

    async def verify_api_key(
        api_key: Optional[str] = Header(None, alias=api_key_header)
    ) -> str:
        expected_key = os.getenv(api_key_env)
        if not expected_key or not api_key or api_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key

    @router.post(
        "/webhook/auto-provision",
        summary="Auto Provision Webhook (Compat)",
        description="Service Market 호환: /mt/tenant/{id}/activate로 매핑"
    )
    async def auto_provision(
        request: ActivateRequest,
        api_key: str = Depends(verify_api_key)
    ):
        """Service Market 자동 프로비저닝 Webhook (호환)"""
        try:
            return await handler.activate_tenant(request)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get(
        "/stats/{tenant_id}",
        response_model=StatsResponse,
        summary="Tenant Stats (Compat)",
        description="Service Market 호환: /mt/tenant/{id}/stats로 매핑"
    )
    async def get_stats(
        tenant_id: str,
        api_key: str = Depends(verify_api_key)
    ):
        """테넌트 통계 조회 (호환)"""
        return await handler.get_tenant_stats(tenant_id, "30d")

    @router.get(
        "/users/{tenant_id}",
        response_model=UsersListResponse,
        summary="Tenant Users (Compat)",
        description="Service Market 호환: /mt/tenant/{id}/users로 매핑"
    )
    async def get_users(
        tenant_id: str,
        role: Optional[str] = Query(default=None),
        limit: int = Query(default=20),
        offset: int = Query(default=0),
        api_key: str = Depends(verify_api_key)
    ):
        """테넌트 사용자 목록 (호환)"""
        filters = UserFilters(
            role=UserRole(role) if role else None,
            limit=limit,
            offset=offset
        )
        return await handler.list_users(tenant_id, filters)

    @router.get(
        "/courses/{tenant_id}",
        response_model=ResourcesResponse,
        summary="Tenant Courses (Compat)",
        description="Service Market 호환: /mt/tenant/{id}/resources?type=course로 매핑"
    )
    async def get_courses(
        tenant_id: str,
        api_key: str = Depends(verify_api_key)
    ):
        """테넌트 코스 목록 (호환)"""
        filters = ResourceFilters(type=ResourceType.COURSE)
        return await handler.list_resources(tenant_id, filters)

    @router.get(
        "/discussions/{tenant_id}",
        response_model=ResourcesResponse,
        summary="Tenant Discussions (Compat)",
        description="Service Market 호환: /mt/tenant/{id}/resources?type=discussion로 매핑"
    )
    async def get_discussions(
        tenant_id: str,
        api_key: str = Depends(verify_api_key)
    ):
        """테넌트 토론 목록 (호환)"""
        filters = ResourceFilters(type=ResourceType.DISCUSSION)
        return await handler.list_resources(tenant_id, filters)

    return router


# =============================================================================
# Helper Functions
# =============================================================================

def _error_detail(code: str, error: Exception | str) -> dict:
    """에러 응답 생성"""
    message = str(error) if isinstance(error, Exception) else error
    return {
        "success": False,
        "error": code,
        "message": message
    }
