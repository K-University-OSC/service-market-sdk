"""
MT PaaS 표준 API 헬퍼

서비스 업체가 표준 API를 쉽게 구현할 수 있도록 도와주는 모듈

사용 예시:
    from mt_paas.standard_api import create_standard_router, StandardAPIHandler

    class MyHandler(StandardAPIHandler):
        async def activate_tenant(self, request):
            # 테넌트 생성 로직
            pass

    router = create_standard_router(MyHandler())
    app.include_router(router)
"""

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

__all__ = [
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
]
