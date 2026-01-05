"""
표준 API 핸들러 추상 클래스

서비스 업체는 이 클래스를 상속받아 비즈니스 로직을 구현합니다.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .models import (
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    StatusResponse,
    UsageResponse,
    UsageData,
)


class StandardAPIHandler(ABC):
    """
    표준 API 핸들러 추상 클래스

    서비스 업체는 이 클래스를 상속받아 각 메서드를 구현합니다.

    Example:
        class MyServiceHandler(StandardAPIHandler):
            def __init__(self, db_manager):
                self.db = db_manager

            async def activate_tenant(self, request: ActivateRequest) -> ActivateResponse:
                # 테넌트 생성 로직
                await self.db.create_tenant(request.tenant_id, ...)
                return ActivateResponse(
                    success=True,
                    tenant_id=request.tenant_id,
                    access_url=f"https://myservice.com/{request.tenant_id}",
                    message="Tenant created"
                )

            # ... 다른 메서드들
    """

    @property
    def service_version(self) -> str:
        """서비스 버전 (오버라이드 권장)"""
        return "1.0.0"

    @property
    def base_url(self) -> str:
        """서비스 기본 URL (오버라이드 필수)"""
        raise NotImplementedError("base_url must be overridden")

    # =========================================================================
    # Health Check
    # =========================================================================

    async def check_health(self) -> str:
        """
        서비스 상태 확인

        Returns:
            str: "healthy", "degraded", or "unhealthy"

        기본 구현은 "healthy"를 반환합니다.
        DB 연결 상태 등을 확인하려면 오버라이드하세요.
        """
        return "healthy"

    # =========================================================================
    # Tenant Lifecycle
    # =========================================================================

    @abstractmethod
    async def activate_tenant(self, request: ActivateRequest) -> ActivateResponse:
        """
        테넌트 활성화

        새 테넌트를 생성하고 필요한 리소스를 할당합니다.

        Args:
            request: 활성화 요청 정보

        Returns:
            ActivateResponse: 활성화 결과

        Raises:
            TenantExistsError: 이미 존재하는 테넌트

        Example:
            async def activate_tenant(self, request):
                # DB에 테넌트 생성
                tenant = await self.db.create_tenant(
                    id=request.tenant_id,
                    name=request.tenant_name,
                    plan=request.plan,
                    features=request.features,
                    config=request.config,
                )

                # 접속 URL 생성
                access_url = f"{self.base_url}/{request.tenant_id}"

                return ActivateResponse(
                    success=True,
                    tenant_id=request.tenant_id,
                    access_url=access_url,
                    message="Tenant activated successfully"
                )
        """
        pass

    @abstractmethod
    async def deactivate_tenant(
        self,
        tenant_id: str,
        request: DeactivateRequest
    ) -> DeactivateResponse:
        """
        테넌트 비활성화

        테넌트 접근을 차단하고 선택적으로 데이터를 보존합니다.

        Args:
            tenant_id: 테넌트 ID
            request: 비활성화 요청 정보

        Returns:
            DeactivateResponse: 비활성화 결과

        Raises:
            TenantNotFoundError: 존재하지 않는 테넌트

        Example:
            async def deactivate_tenant(self, tenant_id, request):
                tenant = await self.db.get_tenant(tenant_id)
                if not tenant:
                    raise TenantNotFoundError(tenant_id)

                # 상태 변경
                await self.db.update_tenant_status(tenant_id, "deactivated")

                # 데이터 보존 기간 설정
                retention_date = None
                if request.preserve_data:
                    retention_date = datetime.utcnow() + timedelta(days=90)

                return DeactivateResponse(
                    success=True,
                    tenant_id=tenant_id,
                    status="deactivated",
                    data_preserved=request.preserve_data,
                    data_retention_until=retention_date.isoformat() if retention_date else None
                )
        """
        pass

    @abstractmethod
    async def get_tenant_status(self, tenant_id: str) -> StatusResponse:
        """
        테넌트 상태 조회

        Args:
            tenant_id: 테넌트 ID

        Returns:
            StatusResponse: 테넌트 상태 정보

        Raises:
            TenantNotFoundError: 존재하지 않는 테넌트

        Example:
            async def get_tenant_status(self, tenant_id):
                tenant = await self.db.get_tenant(tenant_id)
                if not tenant:
                    raise TenantNotFoundError(tenant_id)

                return StatusResponse(
                    tenant_id=tenant.id,
                    status=tenant.status,
                    plan=tenant.plan,
                    features=tenant.features,
                    created_at=tenant.created_at.isoformat(),
                    updated_at=tenant.updated_at.isoformat()
                )
        """
        pass

    @abstractmethod
    async def get_tenant_usage(
        self,
        tenant_id: str,
        period: str
    ) -> UsageResponse:
        """
        테넌트 사용량 조회

        Args:
            tenant_id: 테넌트 ID
            period: 조회 기간 (YYYY-MM 형식)

        Returns:
            UsageResponse: 사용량 정보

        Raises:
            TenantNotFoundError: 존재하지 않는 테넌트

        Example:
            async def get_tenant_usage(self, tenant_id, period):
                tenant = await self.db.get_tenant(tenant_id)
                if not tenant:
                    raise TenantNotFoundError(tenant_id)

                # 사용량 데이터 조회
                stats = await self.analytics.get_monthly_stats(tenant_id, period)

                return UsageResponse(
                    tenant_id=tenant_id,
                    period=period,
                    usage=UsageData(
                        active_users=stats.active_users,
                        total_sessions=stats.sessions,
                        api_calls=stats.api_calls,
                        ai_tokens=stats.tokens_used,
                        storage_mb=stats.storage_mb
                    )
                )
        """
        pass

    # =========================================================================
    # Optional Hooks
    # =========================================================================

    async def before_activate(self, request: ActivateRequest) -> None:
        """활성화 전 훅 (선택적 오버라이드)"""
        pass

    async def after_activate(self, response: ActivateResponse) -> None:
        """활성화 후 훅 (선택적 오버라이드)"""
        pass

    async def before_deactivate(
        self,
        tenant_id: str,
        request: DeactivateRequest
    ) -> None:
        """비활성화 전 훅 (선택적 오버라이드)"""
        pass

    async def after_deactivate(self, response: DeactivateResponse) -> None:
        """비활성화 후 훅 (선택적 오버라이드)"""
        pass


# =============================================================================
# Custom Exceptions
# =============================================================================

class TenantExistsError(Exception):
    """테넌트가 이미 존재할 때 발생"""
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        super().__init__(f"Tenant {tenant_id} already exists")


class TenantNotFoundError(Exception):
    """테넌트를 찾을 수 없을 때 발생"""
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        super().__init__(f"Tenant {tenant_id} not found")
