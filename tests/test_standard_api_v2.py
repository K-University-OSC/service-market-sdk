"""
Standard API v2 테스트

대시보드/사용자관리/리소스/설정 API 모델 및 핸들러 테스트
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime


# =============================================================================
# 임포트 테스트
# =============================================================================

def test_v2_imports():
    """v2 모듈 임포트 테스트"""
    from mt_paas.standard_api import (
        # v2 라우터
        create_standard_router_v2,
        create_service_market_compat_router,
        # v2 핸들러
        StandardAPIHandlerV2,
        UserExistsError,
        UserNotFoundError,
        QuotaExceededError,
        FeatureDisabledError,
        # Dashboard 모델
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
        # Users 모델
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
        # Resources 모델
        ResourceFilters,
        ResourcesResponse,
        ResourceItem,
        ResourceType,
        ResourceStats,
        # Settings 모델
        SettingsResponse,
        TenantConfig,
        FeatureFlags,
        UsageLimits,
        Branding,
        SubscriptionInfo,
        UpdateSettingsRequest,
        # Error 코드
        ErrorCodesV2,
    )
    assert True


# =============================================================================
# Dashboard 모델 테스트
# =============================================================================

class TestDashboardModels:
    """대시보드 모델 테스트"""

    def test_stats_summary(self):
        """StatsSummary 모델 테스트"""
        from mt_paas.standard_api import StatsSummary

        summary = StatsSummary(
            total_users=1250,
            active_users=890,
            new_users_this_period=45,
            total_sessions=15680,
            total_messages=89450,
            total_tokens=12500000,
            estimated_cost_usd=125.50
        )
        assert summary.total_users == 1250
        assert summary.active_users == 890
        assert summary.estimated_cost_usd == 125.50

    def test_stats_summary_defaults(self):
        """StatsSummary 기본값 테스트"""
        from mt_paas.standard_api import StatsSummary

        summary = StatsSummary()
        assert summary.total_users == 0
        assert summary.active_users == 0
        assert summary.estimated_cost_usd == 0.0

    def test_daily_trend(self):
        """DailyTrend 모델 테스트"""
        from mt_paas.standard_api import DailyTrend

        trend = DailyTrend(
            date="2026-01-29",
            users=120,
            messages=3200,
            tokens=450000
        )
        assert trend.date == "2026-01-29"
        assert trend.users == 120

    def test_stats_response(self):
        """StatsResponse 모델 테스트"""
        from mt_paas.standard_api import StatsResponse, StatsSummary, HealthStatus

        response = StatsResponse(
            tenant_id="hallym_univ",
            period="30d",
            summary=StatsSummary(
                total_users=100,
                active_users=80,
                total_messages=5000
            ),
            health=HealthStatus(
                status="healthy",
                last_check="2026-01-30T10:00:00Z",
                response_time_ms=45
            )
        )
        assert response.tenant_id == "hallym_univ"
        assert response.period == "30d"
        assert response.summary.total_users == 100
        assert response.health.status == "healthy"

    def test_model_cost(self):
        """ModelCost 모델 테스트"""
        from mt_paas.standard_api import ModelCost

        cost = ModelCost(
            model="gpt-4",
            input_tokens=5000000,
            output_tokens=2000000,
            cost_usd=85.00
        )
        assert cost.model == "gpt-4"
        assert cost.cost_usd == 85.00

    def test_costs_response(self):
        """CostsResponse 모델 테스트"""
        from mt_paas.standard_api import CostsResponse, ModelCost, UserCost

        response = CostsResponse(
            tenant_id="hallym_univ",
            period="30d",
            total_cost_usd=125.50,
            by_model=[
                ModelCost(model="gpt-4", input_tokens=5000000, output_tokens=2000000, cost_usd=85.00),
                ModelCost(model="gpt-3.5-turbo", input_tokens=4000000, output_tokens=1500000, cost_usd=40.50)
            ],
            by_user_top10=[
                UserCost(user_id="user_123", name="김철수", cost_usd=15.20, tokens=1200000)
            ]
        )
        assert response.total_cost_usd == 125.50
        assert len(response.by_model) == 2
        assert response.by_model[0].model == "gpt-4"

    def test_top_users_response(self):
        """TopUsersResponse 모델 테스트"""
        from mt_paas.standard_api import TopUsersResponse, TopUser

        response = TopUsersResponse(
            tenant_id="hallym_univ",
            period="30d",
            users=[
                TopUser(
                    user_id="user_1",
                    name="홍길동",
                    email="hong@hallym.ac.kr",
                    sessions=150,
                    messages=2340,
                    tokens=350000,
                    last_active="2026-01-30T09:00:00Z"
                )
            ]
        )
        assert len(response.users) == 1
        assert response.users[0].name == "홍길동"


# =============================================================================
# User 모델 테스트
# =============================================================================

class TestUserModels:
    """사용자 관리 모델 테스트"""

    def test_user_role_enum(self):
        """UserRole Enum 테스트"""
        from mt_paas.standard_api import UserRole

        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.MODERATOR.value == "moderator"

    def test_user_status_enum(self):
        """UserStatus Enum 테스트"""
        from mt_paas.standard_api import UserStatus

        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.INACTIVE.value == "inactive"
        assert UserStatus.SUSPENDED.value == "suspended"

    def test_user_filters(self):
        """UserFilters 모델 테스트"""
        from mt_paas.standard_api import UserFilters, UserRole, UserStatus

        filters = UserFilters(
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            search="김",
            limit=20,
            offset=0
        )
        assert filters.role == UserRole.ADMIN
        assert filters.search == "김"
        assert filters.limit == 20

    def test_user_filters_defaults(self):
        """UserFilters 기본값 테스트"""
        from mt_paas.standard_api import UserFilters

        filters = UserFilters()
        assert filters.role is None
        assert filters.status is None
        assert filters.limit == 20
        assert filters.offset == 0

    def test_user_info(self):
        """UserInfo 모델 테스트"""
        from mt_paas.standard_api import UserInfo, UserRole, UserStatus, UserUsage

        user = UserInfo(
            user_id="user_123",
            email="admin@hallym.ac.kr",
            name="관리자",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            created_at="2025-09-01T00:00:00Z",
            last_login="2026-01-30T09:00:00Z",
            usage=UserUsage(sessions=150, messages=2340, tokens=350000)
        )
        assert user.user_id == "user_123"
        assert user.role == UserRole.ADMIN
        assert user.usage.sessions == 150

    def test_users_list_response(self):
        """UsersListResponse 모델 테스트"""
        from mt_paas.standard_api import UsersListResponse, UserInfo, UserRole, UserStatus

        response = UsersListResponse(
            tenant_id="hallym_univ",
            total=1250,
            limit=20,
            offset=0,
            users=[
                UserInfo(
                    user_id="user_1",
                    email="user1@hallym.ac.kr",
                    name="사용자1",
                    role=UserRole.USER,
                    status=UserStatus.ACTIVE,
                    created_at="2025-09-01T00:00:00Z"
                )
            ]
        )
        assert response.total == 1250
        assert len(response.users) == 1

    def test_create_user_request(self):
        """CreateUserRequest 모델 테스트"""
        from mt_paas.standard_api import CreateUserRequest, UserRole

        request = CreateUserRequest(
            email="newuser@hallym.ac.kr",
            name="신규 사용자",
            role=UserRole.USER,
            send_welcome_email=True
        )
        assert request.email == "newuser@hallym.ac.kr"
        assert request.role == UserRole.USER
        assert request.send_welcome_email == True

    def test_create_user_response(self):
        """CreateUserResponse 모델 테스트"""
        from mt_paas.standard_api import CreateUserResponse, UserRole, UserStatus

        response = CreateUserResponse(
            user_id="user_456",
            email="newuser@hallym.ac.kr",
            name="신규 사용자",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            created_at="2026-01-30T10:30:00Z",
            temporary_password=True
        )
        assert response.user_id == "user_456"
        assert response.temporary_password == True

    def test_delete_user_response(self):
        """DeleteUserResponse 모델 테스트"""
        from mt_paas.standard_api import DeleteUserResponse

        response = DeleteUserResponse(
            success=True,
            user_id="user_123",
            message="User deleted successfully"
        )
        assert response.success == True


# =============================================================================
# Resource 모델 테스트
# =============================================================================

class TestResourceModels:
    """리소스 모델 테스트"""

    def test_resource_type_enum(self):
        """ResourceType Enum 테스트"""
        from mt_paas.standard_api import ResourceType

        assert ResourceType.COURSE.value == "course"
        assert ResourceType.DISCUSSION.value == "discussion"
        assert ResourceType.DOCUMENT.value == "document"
        assert ResourceType.SESSION.value == "session"

    def test_resource_filters(self):
        """ResourceFilters 모델 테스트"""
        from mt_paas.standard_api import ResourceFilters, ResourceType

        filters = ResourceFilters(
            type=ResourceType.COURSE,
            search="AI",
            limit=20,
            offset=0
        )
        assert filters.type == ResourceType.COURSE
        assert filters.search == "AI"

    def test_resource_item(self):
        """ResourceItem 모델 테스트"""
        from mt_paas.standard_api import ResourceItem, ResourceType, ResourceStats

        item = ResourceItem(
            id="course_001",
            title="AI 개론",
            type=ResourceType.COURSE,
            created_by="user_123",
            created_at="2025-10-01T00:00:00Z",
            stats=ResourceStats(participants=35, discussions=120, documents=15)
        )
        assert item.id == "course_001"
        assert item.type == ResourceType.COURSE
        assert item.stats.participants == 35

    def test_resources_response(self):
        """ResourcesResponse 모델 테스트"""
        from mt_paas.standard_api import ResourcesResponse, ResourceItem, ResourceType

        response = ResourcesResponse(
            tenant_id="hallym_univ",
            resource_type="course",
            total=45,
            items=[
                ResourceItem(
                    id="course_001",
                    title="AI 개론",
                    type=ResourceType.COURSE,
                    created_at="2025-10-01T00:00:00Z"
                )
            ]
        )
        assert response.total == 45
        assert len(response.items) == 1


# =============================================================================
# Settings 모델 테스트
# =============================================================================

class TestSettingsModels:
    """설정 모델 테스트"""

    def test_feature_flags(self):
        """FeatureFlags 모델 테스트"""
        from mt_paas.standard_api import FeatureFlags

        flags = FeatureFlags(
            rag=True,
            chat=True,
            quiz=False,
            api_integration=True
        )
        assert flags.rag == True
        assert flags.quiz == False

    def test_feature_flags_defaults(self):
        """FeatureFlags 기본값 테스트"""
        from mt_paas.standard_api import FeatureFlags

        flags = FeatureFlags()
        assert flags.rag == True
        assert flags.chat == True
        assert flags.quiz == False

    def test_usage_limits(self):
        """UsageLimits 모델 테스트"""
        from mt_paas.standard_api import UsageLimits

        limits = UsageLimits(
            daily_tokens=1000000,
            monthly_tokens=20000000,
            max_file_size_mb=50,
            max_users=2000,
            max_storage_mb=10240
        )
        assert limits.daily_tokens == 1000000
        assert limits.max_users == 2000

    def test_branding(self):
        """Branding 모델 테스트"""
        from mt_paas.standard_api import Branding

        branding = Branding(
            logo_url="https://example.com/logo.png",
            primary_color="#003366"
        )
        assert branding.logo_url == "https://example.com/logo.png"
        assert branding.primary_color == "#003366"

    def test_subscription_info(self):
        """SubscriptionInfo 모델 테스트"""
        from mt_paas.standard_api import SubscriptionInfo

        info = SubscriptionInfo(
            plan="premium",
            start_date="2025-09-01",
            end_date="2026-08-31",
            auto_renew=True
        )
        assert info.plan == "premium"
        assert info.auto_renew == True

    def test_tenant_config(self):
        """TenantConfig 모델 테스트"""
        from mt_paas.standard_api import TenantConfig, FeatureFlags, UsageLimits

        config = TenantConfig(
            max_users=2000,
            max_storage_mb=10240,
            features=FeatureFlags(rag=True, quiz=True),
            limits=UsageLimits(daily_tokens=500000)
        )
        assert config.max_users == 2000
        assert config.features.quiz == True

    def test_settings_response(self):
        """SettingsResponse 모델 테스트"""
        from mt_paas.standard_api import (
            SettingsResponse, TenantConfig, FeatureFlags,
            UsageLimits, SubscriptionInfo
        )

        response = SettingsResponse(
            tenant_id="hallym_univ",
            config=TenantConfig(
                features=FeatureFlags(rag=True),
                limits=UsageLimits()
            ),
            subscription=SubscriptionInfo(
                plan="premium",
                start_date="2025-09-01"
            )
        )
        assert response.tenant_id == "hallym_univ"
        assert response.config.features.rag == True
        assert response.subscription.plan == "premium"


# =============================================================================
# Exception 테스트
# =============================================================================

class TestExceptions:
    """예외 클래스 테스트"""

    def test_user_exists_error(self):
        """UserExistsError 테스트"""
        from mt_paas.standard_api import UserExistsError

        error = UserExistsError("test@example.com")
        assert error.email == "test@example.com"
        assert "test@example.com" in str(error)
        assert "already exists" in str(error)

    def test_user_not_found_error(self):
        """UserNotFoundError 테스트"""
        from mt_paas.standard_api import UserNotFoundError

        error = UserNotFoundError("user_123")
        assert error.user_id == "user_123"
        assert "user_123" in str(error)
        assert "not found" in str(error)

    def test_quota_exceeded_error(self):
        """QuotaExceededError 테스트"""
        from mt_paas.standard_api import QuotaExceededError

        error = QuotaExceededError("users", 1000)
        assert error.resource == "users"
        assert error.limit == 1000
        assert "quota exceeded" in str(error).lower()

    def test_feature_disabled_error(self):
        """FeatureDisabledError 테스트"""
        from mt_paas.standard_api import FeatureDisabledError

        error = FeatureDisabledError("quiz")
        assert error.feature == "quiz"
        assert "disabled" in str(error).lower()


# =============================================================================
# Error Codes 테스트
# =============================================================================

class TestErrorCodes:
    """에러 코드 테스트"""

    def test_error_codes_v2(self):
        """ErrorCodesV2 테스트"""
        from mt_paas.standard_api import ErrorCodesV2

        # v1 상속
        assert ErrorCodesV2.TENANT_EXISTS == "TENANT_EXISTS"
        assert ErrorCodesV2.TENANT_NOT_FOUND == "TENANT_NOT_FOUND"

        # v2 확장
        assert ErrorCodesV2.USER_EXISTS == "USER_EXISTS"
        assert ErrorCodesV2.USER_NOT_FOUND == "USER_NOT_FOUND"
        assert ErrorCodesV2.QUOTA_EXCEEDED == "QUOTA_EXCEEDED"
        assert ErrorCodesV2.FEATURE_DISABLED == "FEATURE_DISABLED"


# =============================================================================
# Handler 기본 테스트
# =============================================================================

class TestHandlerV2Base:
    """StandardAPIHandlerV2 기본 테스트"""

    def test_handler_inheritance(self):
        """핸들러 상속 관계 테스트"""
        from mt_paas.standard_api import StandardAPIHandler, StandardAPIHandlerV2

        # StandardAPIHandlerV2는 StandardAPIHandler를 상속해야 함
        assert issubclass(StandardAPIHandlerV2, StandardAPIHandler)

    def test_handler_abstract_methods(self):
        """핸들러 추상 메서드 테스트"""
        from mt_paas.standard_api import StandardAPIHandlerV2
        import inspect

        # v2에서 추가된 추상 메서드 확인
        abstract_methods = []
        for name, method in inspect.getmembers(StandardAPIHandlerV2):
            if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__:
                abstract_methods.append(name)

        # 필수 추상 메서드들이 있어야 함
        expected_methods = [
            'activate_tenant',
            'deactivate_tenant',
            'get_tenant_status',
            'get_tenant_usage',
            'get_tenant_stats',
            'get_tenant_costs',
            'list_users',
            'create_user',
            'get_user',
            'update_user',
            'delete_user',
            'get_settings',
        ]

        for method in expected_methods:
            assert method in abstract_methods, f"Missing abstract method: {method}"


# =============================================================================
# Mock Handler 테스트
# =============================================================================

class MockHandlerV2:
    """테스트용 Mock 핸들러"""

    def __init__(self):
        self.tenants = {}
        self.users = {}

    @property
    def service_version(self):
        return "2.0.0"

    @property
    def base_url(self):
        return "https://test.example.com"

    async def check_health(self):
        return "healthy"

    async def get_tenant_stats(self, tenant_id, period="30d"):
        from mt_paas.standard_api import StatsResponse, StatsSummary

        return StatsResponse(
            tenant_id=tenant_id,
            period=period,
            summary=StatsSummary(
                total_users=100,
                active_users=80,
                total_messages=5000
            )
        )

    async def get_tenant_costs(self, tenant_id, period="30d"):
        from mt_paas.standard_api import CostsResponse

        return CostsResponse(
            tenant_id=tenant_id,
            period=period,
            total_cost_usd=50.00,
            by_model=[],
            by_user_top10=[]
        )

    async def list_users(self, tenant_id, filters):
        from mt_paas.standard_api import UsersListResponse

        return UsersListResponse(
            tenant_id=tenant_id,
            total=0,
            limit=filters.limit,
            offset=filters.offset,
            users=[]
        )


class TestMockHandler:
    """Mock 핸들러 테스트"""

    @pytest.mark.asyncio
    async def test_mock_get_stats(self):
        """Mock 통계 조회 테스트"""
        handler = MockHandlerV2()
        result = await handler.get_tenant_stats("test_tenant", "30d")

        assert result.tenant_id == "test_tenant"
        assert result.period == "30d"
        assert result.summary.total_users == 100

    @pytest.mark.asyncio
    async def test_mock_get_costs(self):
        """Mock 비용 조회 테스트"""
        handler = MockHandlerV2()
        result = await handler.get_tenant_costs("test_tenant", "30d")

        assert result.tenant_id == "test_tenant"
        assert result.total_cost_usd == 50.00

    @pytest.mark.asyncio
    async def test_mock_list_users(self):
        """Mock 사용자 목록 테스트"""
        from mt_paas.standard_api import UserFilters

        handler = MockHandlerV2()
        filters = UserFilters(limit=20, offset=0)
        result = await handler.list_users("test_tenant", filters)

        assert result.tenant_id == "test_tenant"
        assert result.total == 0
        assert result.limit == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
