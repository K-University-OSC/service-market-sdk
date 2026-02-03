"""
MT PaaS 표준 API 헬퍼

서비스 업체가 표준 API를 쉽게 구현할 수 있도록 도와주는 모듈

사용 예시 (v1 - 기존):
    from mt_paas.standard_api import create_standard_router, StandardAPIHandler

    class MyHandler(StandardAPIHandler):
        async def activate_tenant(self, request):
            pass

    router = create_standard_router(MyHandler())
    app.include_router(router)

사용 예시 (v2 - 확장):
    from mt_paas.standard_api import create_standard_router_v2, StandardAPIHandlerV2

    class MyHandler(StandardAPIHandlerV2):
        # 생명주기 API (기존)
        async def activate_tenant(self, request): ...
        async def deactivate_tenant(self, tenant_id, request): ...
        async def get_tenant_status(self, tenant_id): ...
        async def get_tenant_usage(self, tenant_id, period): ...

        # 대시보드 API (신규)
        async def get_tenant_stats(self, tenant_id, period): ...
        async def get_tenant_costs(self, tenant_id, period): ...

        # 사용자 관리 API (신규)
        async def list_users(self, tenant_id, filters): ...
        async def create_user(self, tenant_id, request): ...
        async def get_user(self, tenant_id, user_id): ...
        async def update_user(self, tenant_id, user_id, request): ...
        async def delete_user(self, tenant_id, user_id): ...

        # 설정 API (신규)
        async def get_settings(self, tenant_id): ...

    router = create_standard_router_v2(MyHandler())
    app.include_router(router)
"""

# v1 - 기존 API (생명주기만)
from .router import create_standard_router
from .handler import StandardAPIHandler, TenantExistsError, TenantNotFoundError
from .models import (
    HealthResponse,
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    StatusResponse,
    UsageResponse,
    UsageData,
    ErrorResponse,
    ErrorCodes,
    ContactInfo,
)

# v2 - 확장 API (대시보드/사용자관리/리소스/설정)
from .router_v2 import create_standard_router_v2, create_service_market_compat_router
from .handler_v2 import (
    StandardAPIHandlerV2,
    UserExistsError,
    UserNotFoundError,
    QuotaExceededError,
    FeatureDisabledError,
)
from .models_v2 import (
    # Dashboard
    StatsResponse,
    StatsSummary,
    DailyTrend,
    HealthStatus,
    CostsResponse,
    ModelCost,
    UserCost,
    DailyCost,
    TopUsersResponse,
    TopUser,
    # Users
    UserFilters,
    UsersListResponse,
    UserInfo,
    UserUsage,
    UserRole,
    UserStatus,
    CreateUserRequest,
    CreateUserResponse,
    UpdateUserRequest,
    DeleteUserResponse,
    # Resources
    ResourceFilters,
    ResourcesResponse,
    ResourceItem,
    ResourceType,
    ResourceStats,
    # Settings
    SettingsResponse,
    TenantConfig,
    FeatureFlags,
    UsageLimits,
    Branding,
    SubscriptionInfo,
    UpdateSettingsRequest,
    # Error
    ErrorCodesV2,
)

__all__ = [
    # v1 - 기존
    "create_standard_router",
    "StandardAPIHandler",
    "TenantExistsError",
    "TenantNotFoundError",
    "HealthResponse",
    "ActivateRequest",
    "ActivateResponse",
    "DeactivateRequest",
    "DeactivateResponse",
    "StatusResponse",
    "UsageResponse",
    "UsageData",
    "ErrorResponse",
    "ErrorCodes",
    "ContactInfo",
    # v2 - 확장
    "create_standard_router_v2",
    "create_service_market_compat_router",
    "StandardAPIHandlerV2",
    "UserExistsError",
    "UserNotFoundError",
    "QuotaExceededError",
    "FeatureDisabledError",
    # v2 - Dashboard
    "StatsResponse",
    "StatsSummary",
    "DailyTrend",
    "HealthStatus",
    "CostsResponse",
    "ModelCost",
    "UserCost",
    "DailyCost",
    "TopUsersResponse",
    "TopUser",
    # v2 - Users
    "UserFilters",
    "UsersListResponse",
    "UserInfo",
    "UserUsage",
    "UserRole",
    "UserStatus",
    "CreateUserRequest",
    "CreateUserResponse",
    "UpdateUserRequest",
    "DeleteUserResponse",
    # v2 - Resources
    "ResourceFilters",
    "ResourcesResponse",
    "ResourceItem",
    "ResourceType",
    "ResourceStats",
    # v2 - Settings
    "SettingsResponse",
    "TenantConfig",
    "FeatureFlags",
    "UsageLimits",
    "Branding",
    "SubscriptionInfo",
    "UpdateSettingsRequest",
    # v2 - Error
    "ErrorCodesV2",
]
