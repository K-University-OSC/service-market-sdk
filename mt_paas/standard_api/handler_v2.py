"""
표준 API v2 핸들러 추상 클래스

기존 StandardAPIHandler를 확장하여 대시보드/사용자관리/리소스 API 지원
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from .handler import StandardAPIHandler, TenantExistsError, TenantNotFoundError
from .models_v2 import (
    # 기존 모델
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    StatusResponse,
    UsageResponse,
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
    # 신규 모델 - Resources
    ResourceFilters,
    ResourcesResponse,
    # 신규 모델 - Settings
    SettingsResponse,
    UpdateSettingsRequest,
)


class StandardAPIHandlerV2(StandardAPIHandler):
    """
    표준 API v2 핸들러 추상 클래스

    기존 생명주기 API + 대시보드/사용자관리/리소스/설정 API를 지원합니다.

    Example:
        class AdvisorHandler(StandardAPIHandlerV2):
            def __init__(self, db_manager):
                self.db = db_manager

            @property
            def base_url(self) -> str:
                return "https://advisor.k-university.ai"

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
            ...
    """

    # =========================================================================
    # Dashboard API (신규)
    # =========================================================================

    @abstractmethod
    async def get_tenant_stats(
        self,
        tenant_id: str,
        period: str = "30d"
    ) -> StatsResponse:
        """
        테넌트 대시보드 통계 조회

        Service Market 대시보드에서 테넌트 요약 정보를 표시하기 위해 사용합니다.

        Args:
            tenant_id: 테넌트 ID
            period: 조회 기간 (7d, 30d, 90d 등)

        Returns:
            StatsResponse: 대시보드 통계

        Example:
            async def get_tenant_stats(self, tenant_id, period):
                async with self.get_tenant_session(tenant_id) as session:
                    users = await self._count_users(session)
                    messages = await self._count_messages(session, period)
                    tokens = await self._sum_tokens(session, period)

                    return StatsResponse(
                        tenant_id=tenant_id,
                        period=period,
                        summary=StatsSummary(
                            total_users=users.total,
                            active_users=users.active,
                            total_messages=messages,
                            total_tokens=tokens,
                            estimated_cost_usd=self._calculate_cost(tokens)
                        )
                    )
        """
        pass

    @abstractmethod
    async def get_tenant_costs(
        self,
        tenant_id: str,
        period: str = "30d"
    ) -> CostsResponse:
        """
        테넌트 비용 분석 조회

        모델별, 사용자별, 일별 비용 분석 데이터를 반환합니다.

        Args:
            tenant_id: 테넌트 ID
            period: 조회 기간

        Returns:
            CostsResponse: 비용 분석 데이터

        Example:
            async def get_tenant_costs(self, tenant_id, period):
                async with self.get_tenant_session(tenant_id) as session:
                    model_costs = await self._get_model_costs(session, period)
                    user_costs = await self._get_user_costs(session, period)

                    return CostsResponse(
                        tenant_id=tenant_id,
                        period=period,
                        total_cost_usd=sum(m.cost_usd for m in model_costs),
                        by_model=model_costs,
                        by_user_top10=user_costs[:10]
                    )
        """
        pass

    async def get_top_users(
        self,
        tenant_id: str,
        period: str = "30d",
        limit: int = 10
    ) -> TopUsersResponse:
        """
        활성 사용자 목록 조회 (선택적 구현)

        기본 구현은 빈 목록을 반환합니다.

        Args:
            tenant_id: 테넌트 ID
            period: 조회 기간
            limit: 최대 개수

        Returns:
            TopUsersResponse: 활성 사용자 목록
        """
        return TopUsersResponse(
            tenant_id=tenant_id,
            period=period,
            users=[]
        )

    # =========================================================================
    # User Management API (신규)
    # =========================================================================

    @abstractmethod
    async def list_users(
        self,
        tenant_id: str,
        filters: UserFilters
    ) -> UsersListResponse:
        """
        테넌트 사용자 목록 조회

        Service Market에서 테넌트의 사용자를 관리하기 위해 사용합니다.

        Args:
            tenant_id: 테넌트 ID
            filters: 필터 조건 (role, status, search, limit, offset)

        Returns:
            UsersListResponse: 사용자 목록

        Example:
            async def list_users(self, tenant_id, filters):
                async with self.get_tenant_session(tenant_id) as session:
                    query = select(User)

                    if filters.role:
                        query = query.where(User.role == filters.role)
                    if filters.status:
                        query = query.where(User.status == filters.status)
                    if filters.search:
                        query = query.where(
                            User.name.ilike(f"%{filters.search}%") |
                            User.email.ilike(f"%{filters.search}%")
                        )

                    total = await session.scalar(select(func.count()).select_from(query.subquery()))
                    users = await session.scalars(
                        query.offset(filters.offset).limit(filters.limit)
                    )

                    return UsersListResponse(
                        tenant_id=tenant_id,
                        total=total,
                        limit=filters.limit,
                        offset=filters.offset,
                        users=[self._to_user_info(u) for u in users]
                    )
        """
        pass

    @abstractmethod
    async def create_user(
        self,
        tenant_id: str,
        request: CreateUserRequest
    ) -> CreateUserResponse:
        """
        테넌트 사용자 생성

        Args:
            tenant_id: 테넌트 ID
            request: 사용자 생성 요청

        Returns:
            CreateUserResponse: 생성된 사용자 정보

        Raises:
            UserExistsError: 이미 존재하는 사용자
            QuotaExceededError: 사용자 수 한도 초과

        Example:
            async def create_user(self, tenant_id, request):
                async with self.get_tenant_session(tenant_id) as session:
                    # 중복 체크
                    existing = await session.scalar(
                        select(User).where(User.email == request.email)
                    )
                    if existing:
                        raise UserExistsError(request.email)

                    # 비밀번호 생성
                    password = request.password or self._generate_temp_password()

                    # 사용자 생성
                    user = User(
                        email=request.email,
                        name=request.name,
                        role=request.role,
                        password_hash=self._hash_password(password)
                    )
                    session.add(user)
                    await session.commit()

                    # 환영 이메일 발송
                    if request.send_welcome_email:
                        await self._send_welcome_email(user, password)

                    return CreateUserResponse(
                        user_id=user.id,
                        email=user.email,
                        name=user.name,
                        role=user.role,
                        status="active",
                        created_at=user.created_at.isoformat(),
                        temporary_password=request.password is None
                    )
        """
        pass

    @abstractmethod
    async def get_user(
        self,
        tenant_id: str,
        user_id: str
    ) -> UserInfo:
        """
        테넌트 사용자 조회

        Args:
            tenant_id: 테넌트 ID
            user_id: 사용자 ID

        Returns:
            UserInfo: 사용자 정보

        Raises:
            UserNotFoundError: 존재하지 않는 사용자
        """
        pass

    @abstractmethod
    async def update_user(
        self,
        tenant_id: str,
        user_id: str,
        request: UpdateUserRequest
    ) -> UserInfo:
        """
        테넌트 사용자 수정

        Args:
            tenant_id: 테넌트 ID
            user_id: 사용자 ID
            request: 수정 요청

        Returns:
            UserInfo: 수정된 사용자 정보

        Raises:
            UserNotFoundError: 존재하지 않는 사용자
        """
        pass

    @abstractmethod
    async def delete_user(
        self,
        tenant_id: str,
        user_id: str
    ) -> DeleteUserResponse:
        """
        테넌트 사용자 삭제

        Args:
            tenant_id: 테넌트 ID
            user_id: 사용자 ID

        Returns:
            DeleteUserResponse: 삭제 결과

        Raises:
            UserNotFoundError: 존재하지 않는 사용자
        """
        pass

    # =========================================================================
    # Resource API (신규)
    # =========================================================================

    async def list_resources(
        self,
        tenant_id: str,
        filters: ResourceFilters
    ) -> ResourcesResponse:
        """
        테넌트 리소스 목록 조회 (선택적 구현)

        코스, 토론, 문서 등 서비스별 리소스를 조회합니다.
        기본 구현은 빈 목록을 반환합니다.

        Args:
            tenant_id: 테넌트 ID
            filters: 필터 조건

        Returns:
            ResourcesResponse: 리소스 목록
        """
        return ResourcesResponse(
            tenant_id=tenant_id,
            resource_type=filters.type.value if filters.type else None,
            total=0,
            items=[]
        )

    # =========================================================================
    # Settings API (신규)
    # =========================================================================

    @abstractmethod
    async def get_settings(
        self,
        tenant_id: str
    ) -> SettingsResponse:
        """
        테넌트 설정 조회

        Args:
            tenant_id: 테넌트 ID

        Returns:
            SettingsResponse: 설정 정보

        Example:
            async def get_settings(self, tenant_id):
                tenant = await self._get_tenant(tenant_id)
                subscription = await self._get_subscription(tenant_id)

                return SettingsResponse(
                    tenant_id=tenant_id,
                    config=TenantConfig(
                        max_users=tenant.config.get("max_users"),
                        features=FeatureFlags(**tenant.features),
                        limits=UsageLimits(**tenant.limits)
                    ),
                    subscription=SubscriptionInfo(
                        plan=subscription.plan,
                        start_date=subscription.start_date.isoformat(),
                        end_date=subscription.end_date.isoformat() if subscription.end_date else None,
                        auto_renew=subscription.auto_renew
                    )
                )
        """
        pass

    async def update_settings(
        self,
        tenant_id: str,
        request: UpdateSettingsRequest
    ) -> SettingsResponse:
        """
        테넌트 설정 수정 (선택적 구현)

        기본 구현은 현재 설정을 반환합니다.

        Args:
            tenant_id: 테넌트 ID
            request: 수정 요청

        Returns:
            SettingsResponse: 수정된 설정
        """
        return await self.get_settings(tenant_id)


# =============================================================================
# Extended Exceptions (신규)
# =============================================================================

class UserExistsError(Exception):
    """사용자가 이미 존재할 때 발생"""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"User {email} already exists")


class UserNotFoundError(Exception):
    """사용자를 찾을 수 없을 때 발생"""
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class QuotaExceededError(Exception):
    """한도 초과 시 발생"""
    def __init__(self, resource: str, limit: int):
        self.resource = resource
        self.limit = limit
        super().__init__(f"{resource} quota exceeded (limit: {limit})")


class FeatureDisabledError(Exception):
    """기능이 비활성화되어 있을 때 발생"""
    def __init__(self, feature: str):
        self.feature = feature
        super().__init__(f"Feature {feature} is disabled for this tenant")
