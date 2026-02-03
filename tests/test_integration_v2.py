"""
Standard API v2 통합 테스트

Service Market ↔ 서비스 (advisor, llm_chatbot 등) v2 API 통합 테스트
(DB 없이 Mock 사용)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
sys.path.insert(0, "/home/aiedu/workspace/multi_tenant_paas")


class TestV2HandlerIntegration:
    """V2 핸들러 통합 테스트"""

    def test_handler_v2_inherits_v1(self):
        """V2 핸들러가 V1을 상속하는지 확인"""
        from mt_paas.standard_api import StandardAPIHandler, StandardAPIHandlerV2

        assert issubclass(StandardAPIHandlerV2, StandardAPIHandler)

    def test_handler_v2_has_all_methods(self):
        """V2 핸들러가 모든 필수 메서드를 갖고 있는지 확인"""
        from mt_paas.standard_api import StandardAPIHandlerV2

        # V1 methods
        v1_methods = [
            'activate_tenant',
            'deactivate_tenant',
            'get_tenant_status',
            'get_tenant_usage',
        ]

        # V2 new methods
        v2_methods = [
            'get_tenant_stats',
            'get_tenant_costs',
            'list_users',
            'create_user',
            'get_user',
            'update_user',
            'delete_user',
            'list_resources',
            'get_settings',
        ]

        for method in v1_methods + v2_methods:
            assert hasattr(StandardAPIHandlerV2, method), f"Missing method: {method}"


class TestMockServiceV2:
    """Mock 서비스 V2 API 테스트"""

    @pytest.fixture
    def mock_handler(self):
        """Mock V2 핸들러 생성"""
        from mt_paas.standard_api import StandardAPIHandlerV2
        from mt_paas.standard_api.models_v2 import (
            StatsResponse, StatsSummary, HealthStatus,
            CostsResponse, ModelCost, UserCost,
            UsersListResponse, UserInfo, UserRole, UserStatus, UserUsage,
            CreateUserResponse,
            DeleteUserResponse,
            ResourcesResponse, ResourceFilters,
            SettingsResponse, TenantConfig, FeatureFlags, UsageLimits, SubscriptionInfo
        )

        class MockServiceHandler(StandardAPIHandlerV2):
            """테스트용 Mock 핸들러"""

            def __init__(self):
                self.tenants = {}
                self.users = {}

            async def activate_tenant(self, request):
                tenant_id = request.tenant_id
                self.tenants[tenant_id] = {
                    "status": "active",
                    "plan": request.plan,
                    "features": request.features,
                }
                return {
                    "success": True,
                    "tenant_id": tenant_id,
                    "access_url": f"https://mock.example.com/{tenant_id}",
                    "message": "Tenant activated successfully"
                }

            async def deactivate_tenant(self, tenant_id: str, request):
                if tenant_id in self.tenants:
                    self.tenants[tenant_id]["status"] = "suspended"
                return {
                    "success": True,
                    "tenant_id": tenant_id,
                    "status": "suspended",
                    "data_preserved": request.preserve_data
                }

            async def get_tenant_status(self, tenant_id: str):
                if tenant_id not in self.tenants:
                    return {"tenant_id": tenant_id, "status": "not_found"}
                return {
                    "tenant_id": tenant_id,
                    **self.tenants[tenant_id]
                }

            async def get_tenant_usage(self, tenant_id: str, period: str):
                return {
                    "tenant_id": tenant_id,
                    "period": period,
                    "usage": {
                        "active_users": 50,
                        "api_calls": 10000,
                        "storage_mb": 500
                    }
                }

            # V2 메서드들
            async def get_tenant_stats(self, tenant_id: str, period: str = "30d"):
                return StatsResponse(
                    tenant_id=tenant_id,
                    period=period,
                    summary=StatsSummary(
                        total_users=100,
                        active_users=80,
                        total_messages=25000,
                        total_tokens=500000,
                        estimated_cost_usd=50.0
                    ),
                    health=HealthStatus(
                        status="healthy",
                        last_check=datetime.now().isoformat(),
                        response_time_ms=45
                    )
                )

            async def get_tenant_costs(self, tenant_id: str, period: str):
                return CostsResponse(
                    tenant_id=tenant_id,
                    period=period,
                    total_cost_usd=150.50,
                    by_model=[
                        ModelCost(model="gpt-4", input_tokens=50000, output_tokens=50000, cost_usd=100.0),
                        ModelCost(model="gpt-3.5", input_tokens=250000, output_tokens=250000, cost_usd=50.5)
                    ],
                    by_user_top10=[
                        UserCost(user_id="user1", name="홍길동", tokens=300000, cost_usd=75.25)
                    ]
                )

            async def list_users(self, tenant_id: str, filters):
                tenant_users = self.users.get(tenant_id, [])
                return UsersListResponse(
                    tenant_id=tenant_id,
                    users=tenant_users,
                    total=len(tenant_users),
                    limit=filters.limit,
                    offset=filters.offset
                )

            async def create_user(self, tenant_id: str, request):
                if tenant_id not in self.users:
                    self.users[tenant_id] = []

                user = UserInfo(
                    user_id=request.email.split("@")[0],
                    email=request.email,
                    name=request.name,
                    role=request.role,
                    status=UserStatus.ACTIVE,
                    created_at=datetime.now().isoformat()
                )
                self.users[tenant_id].append(user)
                return CreateUserResponse(
                    user_id=user.user_id,
                    email=user.email,
                    name=user.name,
                    role=user.role,
                    status=user.status,
                    created_at=user.created_at,
                    temporary_password=True
                )

            async def get_user(self, tenant_id: str, user_id: str):
                tenant_users = self.users.get(tenant_id, [])
                for user in tenant_users:
                    if user.user_id == user_id:
                        return user
                return None

            async def update_user(self, tenant_id: str, user_id: str, request):
                tenant_users = self.users.get(tenant_id, [])
                for user in tenant_users:
                    if user.user_id == user_id:
                        if request.role:
                            user.role = request.role
                        if request.status:
                            user.status = request.status
                        if request.name:
                            user.name = request.name
                        return user
                return None

            async def delete_user(self, tenant_id: str, user_id: str):
                tenant_users = self.users.get(tenant_id, [])
                for i, user in enumerate(tenant_users):
                    if user.user_id == user_id:
                        del tenant_users[i]
                        return DeleteUserResponse(
                            success=True,
                            user_id=user_id,
                            message="User deleted successfully"
                        )
                return DeleteUserResponse(
                    success=False,
                    user_id=user_id,
                    message="User not found"
                )

            async def list_resources(self, tenant_id: str, filters: ResourceFilters):
                return ResourcesResponse(
                    tenant_id=tenant_id,
                    resource_type=filters.type.value if filters.type else None,
                    total=0,
                    items=[]
                )

            async def get_settings(self, tenant_id: str):
                return SettingsResponse(
                    tenant_id=tenant_id,
                    config=TenantConfig(
                        max_users=100,
                        max_storage_mb=10000,
                        features=FeatureFlags(rag=True, chat=True, quiz=False),
                        limits=UsageLimits(daily_tokens=1000000, monthly_tokens=20000000)
                    ),
                    subscription=SubscriptionInfo(
                        plan="premium",
                        start_date="2025-09-01",
                        end_date="2026-08-31",
                        auto_renew=True
                    )
                )

        return MockServiceHandler()

    @pytest.mark.asyncio
    async def test_full_v2_lifecycle(self, mock_handler):
        """V2 API 전체 라이프사이클 테스트"""
        from mt_paas.standard_api.models import ActivateRequest, DeactivateRequest, ContactInfo
        from mt_paas.standard_api.models_v2 import UserFilters, CreateUserRequest, UserRole, ResourceFilters

        tenant_id = "test_university"

        # 1. 테넌트 활성화
        activate_req = ActivateRequest(
            tenant_id=tenant_id,
            tenant_name="테스트 대학교",
            plan="premium",
            features=["ai_chat", "rag"],
            contact=ContactInfo(email="admin@test.ac.kr", name="관리자")
        )
        result = await mock_handler.activate_tenant(activate_req)
        assert result["success"] == True
        assert result["tenant_id"] == tenant_id

        # 2. 상태 확인
        status = await mock_handler.get_tenant_status(tenant_id)
        assert status["status"] == "active"
        assert status["plan"] == "premium"

        # 3. 통계 조회 (V2)
        stats = await mock_handler.get_tenant_stats(tenant_id, "30d")
        assert stats.tenant_id == tenant_id
        assert stats.summary is not None
        assert stats.health is not None
        assert stats.summary.total_users == 100

        # 4. 비용 조회 (V2)
        costs = await mock_handler.get_tenant_costs(tenant_id, "2026-01")
        assert costs.total_cost_usd == 150.50
        assert len(costs.by_model) == 2

        # 5. 사용자 생성 (V2)
        create_req = CreateUserRequest(
            email="student@test.ac.kr",
            name="학생1",
            role=UserRole.USER
        )
        user = await mock_handler.create_user(tenant_id, create_req)
        assert user.email == "student@test.ac.kr"
        assert user.status.value == "active"

        # 6. 사용자 목록 (V2)
        users = await mock_handler.list_users(tenant_id, UserFilters())
        assert users.total == 1
        assert len(users.users) == 1

        # 7. 사용자 조회 (V2)
        found_user = await mock_handler.get_user(tenant_id, "student")
        assert found_user is not None
        assert found_user.name == "학생1"

        # 8. 리소스 조회 (V2)
        resources = await mock_handler.list_resources(tenant_id, ResourceFilters())
        assert resources.tenant_id == tenant_id
        assert resources.total == 0

        # 9. 설정 조회 (V2)
        settings = await mock_handler.get_settings(tenant_id)
        assert settings.config is not None
        assert settings.subscription is not None
        assert settings.config.features.rag == True
        assert settings.subscription.plan == "premium"

        # 10. 사용자 삭제 (V2)
        delete_result = await mock_handler.delete_user(tenant_id, "student")
        assert delete_result.success == True

        # 11. 비활성화
        deactivate_req = DeactivateRequest(
            reason="test_complete",
            preserve_data=True
        )
        result = await mock_handler.deactivate_tenant(tenant_id, deactivate_req)
        assert result["success"] == True
        assert result["data_preserved"] == True

        print("Full V2 lifecycle test passed!")


class TestServiceMarketCompatibility:
    """Service Market 호환성 테스트"""

    def test_alias_endpoints_exist(self):
        """호환성 별칭 엔드포인트 확인"""
        from mt_paas.standard_api import create_service_market_compat_router

        # 라우터 생성 가능 여부만 확인
        assert callable(create_service_market_compat_router)

    def test_v2_router_creation(self):
        """V2 라우터 생성 테스트"""
        from mt_paas.standard_api import create_standard_router_v2, StandardAPIHandlerV2
        from mt_paas.standard_api.models_v2 import ResourceFilters

        # Mock 핸들러 (최소 구현)
        class MinimalHandler(StandardAPIHandlerV2):
            async def activate_tenant(self, request): pass
            async def deactivate_tenant(self, tenant_id, request): pass
            async def get_tenant_status(self, tenant_id): pass
            async def get_tenant_usage(self, tenant_id, period): pass
            async def get_tenant_stats(self, tenant_id, period): pass
            async def get_tenant_costs(self, tenant_id, period): pass
            async def list_users(self, tenant_id, filters): pass
            async def create_user(self, tenant_id, request): pass
            async def get_user(self, tenant_id, user_id): pass
            async def update_user(self, tenant_id, user_id, request): pass
            async def delete_user(self, tenant_id, user_id): pass
            async def get_settings(self, tenant_id): pass

        router = create_standard_router_v2(MinimalHandler())
        assert router is not None

        # 라우터에 등록된 경로 확인
        routes = [route.path for route in router.routes]

        # V1 엔드포인트
        assert "/mt/tenant/{tenant_id}/activate" in routes
        assert "/mt/tenant/{tenant_id}/deactivate" in routes
        assert "/mt/tenant/{tenant_id}/status" in routes
        assert "/mt/tenant/{tenant_id}/usage" in routes

        # V2 엔드포인트
        assert "/mt/tenant/{tenant_id}/stats" in routes
        assert "/mt/tenant/{tenant_id}/stats/costs" in routes
        assert "/mt/tenant/{tenant_id}/users" in routes
        assert "/mt/tenant/{tenant_id}/users/{user_id}" in routes
        assert "/mt/tenant/{tenant_id}/resources" in routes
        assert "/mt/tenant/{tenant_id}/settings" in routes


class TestV2ModelsIntegration:
    """V2 모델 통합 테스트"""

    def test_stats_response_full(self):
        """StatsResponse 전체 필드 테스트"""
        from mt_paas.standard_api.models_v2 import (
            StatsResponse, StatsSummary, HealthStatus, DailyTrend
        )

        response = StatsResponse(
            tenant_id="test_univ",
            period="30d",
            summary=StatsSummary(
                total_users=100,
                active_users=80,
                total_messages=25000,
                total_tokens=500000,
                estimated_cost_usd=50.0
            ),
            health=HealthStatus(
                status="healthy",
                last_check="2026-01-30T10:00:00Z",
                response_time_ms=45
            ),
            trends={
                "daily": [
                    DailyTrend(date="2026-01-29", users=50, messages=1000, tokens=100000),
                    DailyTrend(date="2026-01-30", users=45, messages=900, tokens=90000)
                ]
            }
        )

        assert response.tenant_id == "test_univ"
        assert response.summary.total_users == 100
        assert response.health.status == "healthy"
        assert len(response.trends["daily"]) == 2

    def test_costs_response_full(self):
        """CostsResponse 전체 필드 테스트"""
        from mt_paas.standard_api.models_v2 import (
            CostsResponse, ModelCost, UserCost, DailyCost
        )

        response = CostsResponse(
            tenant_id="test_univ",
            period="2026-01",
            total_cost_usd=250.75,
            by_model=[
                ModelCost(model="gpt-4", input_tokens=50000, output_tokens=50000, cost_usd=150.0),
                ModelCost(model="gpt-3.5", input_tokens=250000, output_tokens=250000, cost_usd=100.75)
            ],
            by_user_top10=[
                UserCost(user_id="user1", name="홍길동", tokens=200000, cost_usd=125.0),
                UserCost(user_id="user2", name="김철수", tokens=100000, cost_usd=75.0)
            ],
            daily_trend=[
                DailyCost(date="2026-01-29", cost_usd=8.5),
                DailyCost(date="2026-01-30", cost_usd=7.25)
            ]
        )

        assert response.total_cost_usd == 250.75
        assert len(response.by_model) == 2
        assert response.by_user_top10[0].name == "홍길동"

    def test_users_list_response_full(self):
        """UsersListResponse 전체 필드 테스트"""
        from mt_paas.standard_api.models_v2 import (
            UsersListResponse, UserInfo, UserUsage, UserRole, UserStatus
        )

        response = UsersListResponse(
            tenant_id="test_univ",
            users=[
                UserInfo(
                    user_id="user1",
                    email="user1@test.ac.kr",
                    name="홍길동",
                    role=UserRole.ADMIN,
                    status=UserStatus.ACTIVE,
                    created_at="2026-01-01T00:00:00Z",
                    last_login="2026-01-30T10:00:00Z",
                    usage=UserUsage(
                        sessions=100,
                        messages=500,
                        tokens=50000
                    )
                )
            ],
            total=1,
            limit=20,
            offset=0
        )

        assert response.total == 1
        assert response.users[0].name == "홍길동"
        assert response.users[0].usage.sessions == 100


class TestExceptionsIntegration:
    """예외 처리 통합 테스트"""

    def test_v2_exceptions_hierarchy(self):
        """V2 예외 클래스 계층 테스트"""
        from mt_paas.standard_api.handler import (
            TenantExistsError,
            TenantNotFoundError,
        )
        from mt_paas.standard_api.handler_v2 import (
            UserExistsError,
            UserNotFoundError,
            QuotaExceededError,
            FeatureDisabledError,
        )

        # 기존 예외
        assert issubclass(TenantExistsError, Exception)
        assert issubclass(TenantNotFoundError, Exception)

        # V2 예외는 Exception 상속 확인
        assert issubclass(UserExistsError, Exception)
        assert issubclass(UserNotFoundError, Exception)
        assert issubclass(QuotaExceededError, Exception)
        assert issubclass(FeatureDisabledError, Exception)

    def test_exception_messages(self):
        """예외 메시지 테스트"""
        from mt_paas.standard_api.handler_v2 import (
            UserExistsError,
            UserNotFoundError,
            QuotaExceededError,
            FeatureDisabledError,
        )

        # UserExistsError - takes email only
        user_exists = UserExistsError("user1@test.com")
        assert "user1@test.com" in str(user_exists)
        assert user_exists.email == "user1@test.com"

        # UserNotFoundError - takes user_id only
        user_not_found = UserNotFoundError("user1")
        assert "user1" in str(user_not_found)
        assert user_not_found.user_id == "user1"

        # QuotaExceededError - takes resource and limit
        quota_exceeded = QuotaExceededError("tokens", 1000000)
        assert "tokens" in str(quota_exceeded)
        assert "1000000" in str(quota_exceeded)
        assert quota_exceeded.resource == "tokens"
        assert quota_exceeded.limit == 1000000

        # FeatureDisabledError - takes feature only
        feature_disabled = FeatureDisabledError("rag")
        assert "rag" in str(feature_disabled)
        assert feature_disabled.feature == "rag"


class TestPortConfiguration:
    """포트 설정 테스트"""

    def test_port_constants(self):
        """포트 상수 확인"""
        from mt_paas.config import Ports

        # 주요 포트 확인
        assert Ports.MT_PAAS_API == 11000
        assert Ports.MT_PAAS_ADMIN == 11001
        assert Ports.SERVICE_MARKET_API == 11010
        assert Ports.KELI_TUTOR_BASE == 11100

        # 테넌트 범위 확인
        assert Ports.TENANT_RANGE_START < Ports.TENANT_RANGE_END
        assert 11000 <= Ports.TENANT_RANGE_START <= 12000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
