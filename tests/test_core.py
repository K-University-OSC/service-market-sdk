"""
MT-PaaS 코어 모듈 테스트

DB 없이 동작하는 유닛 테스트
"""

import pytest
from datetime import datetime, timedelta
from dataclasses import asdict

# 임포트 테스트
def test_imports():
    """모든 모듈이 정상적으로 임포트되는지 확인"""
    from mt_paas import (
        setup_multi_tenant,
        MTPaaS,
        TenantManager,
        Ports,
        MTPaaSConfig,
        get_config,
    )
    from mt_paas.core import (
        TenantManager,
        DatabaseManager,
        TenantLifecycle,
        Tenant,
        TenantStatus,
        Subscription,
        SubscriptionPlan,
    )
    from mt_paas.middleware import (
        TenantMiddleware,
        get_current_tenant,
        TenantContext,
    )
    from mt_paas.standard_api import (
        StandardAPIHandler,
        create_standard_router,
        TenantExistsError,
        TenantNotFoundError,
    )
    from mt_paas.manifest import (
        ManifestValidator,
        Manifest,
    )
    assert True


class TestConfig:
    """설정 테스트"""

    def test_port_config(self):
        """포트 설정 테스트"""
        from mt_paas.config import PortConfig, Ports

        config = PortConfig()
        assert config.api_port == 11000
        assert config.admin_port == 11001
        assert config.tenant_port_start == 11100
        assert config.tenant_port_end == 11999

        # 테넌트별 포트 할당
        start, end = config.get_tenant_ports(0)
        assert start == 11100
        assert end == 11104  # 5 ports per tenant

        start, end = config.get_tenant_ports(1)
        assert start == 11105
        assert end == 11109

    def test_ports_class(self):
        """Ports 상수 클래스 테스트"""
        from mt_paas.config import Ports

        assert Ports.MT_PAAS_API == 11000
        assert Ports.MT_PAAS_ADMIN == 11001
        assert Ports.SERVICE_MARKET_API == 11010
        assert Ports.KELI_TUTOR_BASE == 11100
        assert Ports.TENANT_RANGE_START == 11200
        assert Ports.TENANT_RANGE_END == 11999

    def test_config_from_env(self):
        """환경변수 기반 설정 테스트"""
        import os
        from mt_paas.config import MTPaaSConfig

        # 기본값
        config = MTPaaSConfig.from_env()
        assert config.service_name == "mt_paas"
        assert config.database.host == "localhost"
        assert config.database.port == 5432

    def test_database_url(self):
        """DB URL 생성 테스트"""
        from mt_paas.config import DatabaseConfig

        config = DatabaseConfig(
            host="localhost",
            port=5432,
            username="testuser",
            password="testpass",
            database="testdb"
        )
        assert config.url == "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
        assert config.sync_url == "postgresql://testuser:testpass@localhost:5432/testdb"


class TestModels:
    """모델 테스트"""

    def test_tenant_status(self):
        """테넌트 상태 Enum 테스트"""
        from mt_paas.core.models import TenantStatus

        assert TenantStatus.PENDING.value == "pending"
        assert TenantStatus.ACTIVE.value == "active"
        assert TenantStatus.SUSPENDED.value == "suspended"
        assert TenantStatus.DELETED.value == "deleted"

    def test_subscription_plan(self):
        """구독 요금제 Enum 테스트"""
        from mt_paas.core.models import SubscriptionPlan

        assert SubscriptionPlan.FREE.value == "free"
        assert SubscriptionPlan.BASIC.value == "basic"
        assert SubscriptionPlan.PREMIUM.value == "premium"
        assert SubscriptionPlan.ENTERPRISE.value == "enterprise"

    def test_subscription_features(self):
        """요금제별 기능 테스트"""
        from mt_paas.core.models import Subscription, SubscriptionPlan

        free_features = Subscription.get_default_features(SubscriptionPlan.FREE)
        assert free_features["ai_chat"] == True
        assert free_features["rag"] == False

        premium_features = Subscription.get_default_features(SubscriptionPlan.PREMIUM)
        assert premium_features["ai_chat"] == True
        assert premium_features["rag"] == True
        assert premium_features["quiz"] == True


class TestSchemas:
    """스키마 테스트"""

    def test_tenant_create(self):
        """테넌트 생성 스키마 테스트"""
        from mt_paas.core.schemas import TenantCreate

        schema = TenantCreate(
            id="test_univ",
            name="테스트 대학교",
            plan="premium",
            features=["ai_chat", "rag"],
            admin_email="admin@test.ac.kr"
        )
        assert schema.id == "test_univ"
        assert schema.plan == "premium"
        assert "rag" in schema.features

    def test_tenant_create_defaults(self):
        """테넌트 생성 기본값 테스트"""
        from mt_paas.core.schemas import TenantCreate

        schema = TenantCreate(id="test", name="Test")
        assert schema.plan == "basic"
        assert schema.service_type == "generic"
        assert schema.features is None

    def test_tenant_response(self):
        """테넌트 응답 스키마 테스트"""
        from mt_paas.core.schemas import TenantResponse

        response = TenantResponse(
            id="test",
            name="Test",
            status="active",
            service_type="keli_tutor",
        )
        assert response.status == "active"


class TestTenantContext:
    """테넌트 컨텍스트 테스트"""

    def test_context_creation(self):
        """컨텍스트 생성 테스트"""
        from mt_paas.middleware.tenant import TenantContext

        ctx = TenantContext(
            tenant_id="hallym_univ",
            plan="premium",
            features={"rag": True, "quiz": False}
        )
        assert ctx.tenant_id == "hallym_univ"
        assert ctx.plan == "premium"
        assert ctx.has_feature("rag") == True
        assert ctx.has_feature("quiz") == False
        assert ctx.has_feature("unknown") == False

    def test_context_defaults(self):
        """컨텍스트 기본값 테스트"""
        from mt_paas.middleware.tenant import TenantContext

        ctx = TenantContext(tenant_id="test")
        assert ctx.plan == "basic"
        assert ctx.features == {}
        assert ctx.config == {}

    def test_context_var(self):
        """컨텍스트 변수 테스트"""
        from mt_paas.middleware.tenant import (
            TenantContext,
            get_current_tenant,
            set_current_tenant,
            clear_current_tenant,
        )

        # 초기 상태
        assert get_current_tenant() is None

        # 설정
        ctx = TenantContext(tenant_id="test")
        set_current_tenant(ctx)
        assert get_current_tenant() is not None
        assert get_current_tenant().tenant_id == "test"

        # 정리
        clear_current_tenant()
        assert get_current_tenant() is None


class TestManifest:
    """매니페스트 테스트"""

    def test_manifest_from_dict(self):
        """딕셔너리에서 매니페스트 생성 테스트"""
        from mt_paas.manifest import Manifest

        data = {
            "service": {
                "name": "keli_tutor",
                "version": "1.0.0",
                "description": "AI 튜터 서비스",
                "category": "education",
            },
            "endpoints": {
                "base_url": "https://keli.example.com",
                "health_check": "/mt/health",
            },
            "auth": {
                "type": "api_key",
                "header_name": "X-Market-API-Key",
            },
            "plans": [
                {
                    "name": "basic",
                    "display_name": "기본",
                    "max_users": 50,
                    "max_storage_mb": 1000,
                    "features": ["ai_chat"],
                }
            ]
        }

        manifest = Manifest.from_dict(data)
        assert manifest.service.name == "keli_tutor"
        assert manifest.service.version == "1.0.0"
        assert manifest.endpoints.base_url == "https://keli.example.com"
        assert manifest.auth.type == "api_key"
        assert len(manifest.plans) == 1
        assert manifest.plans[0].name == "basic"

    def test_manifest_to_dict(self):
        """매니페스트 딕셔너리 변환 테스트"""
        from mt_paas.manifest import Manifest

        data = {
            "service": {
                "name": "test_service",
                "version": "2.0.0",
            },
            "endpoints": {
                "base_url": "http://localhost:8000",
            }
        }

        manifest = Manifest.from_dict(data)
        result = manifest.to_dict()

        assert result["service"]["name"] == "test_service"
        assert result["service"]["version"] == "2.0.0"
        assert result["endpoints"]["base_url"] == "http://localhost:8000"


class TestStandardAPIModels:
    """표준 API 모델 테스트"""

    def test_activate_request(self):
        """활성화 요청 모델 테스트"""
        from mt_paas.standard_api.models import ActivateRequest, ContactInfo

        request = ActivateRequest(
            tenant_id="test_univ",
            tenant_name="테스트 대학교",
            plan="premium",
            features=["ai_chat", "rag"],
            contact=ContactInfo(email="admin@test.ac.kr", name="관리자")
        )
        assert request.tenant_id == "test_univ"
        assert request.plan == "premium"
        assert request.contact.email == "admin@test.ac.kr"

    def test_activate_response(self):
        """활성화 응답 모델 테스트"""
        from mt_paas.standard_api.models import ActivateResponse

        response = ActivateResponse(
            success=True,
            tenant_id="test_univ",
            access_url="https://test.example.com/test_univ",
            message="Activated"
        )
        assert response.success == True
        assert "test_univ" in response.access_url

    def test_usage_response(self):
        """사용량 응답 모델 테스트"""
        from mt_paas.standard_api.models import UsageResponse, UsageData

        response = UsageResponse(
            tenant_id="test",
            period="2026-01",
            usage=UsageData(
                active_users=100,
                total_sessions=500,
                api_calls=10000
            )
        )
        assert response.usage.active_users == 100
        assert response.usage.api_calls == 10000


class TestLifecycleEvents:
    """라이프사이클 이벤트 테스트"""

    def test_lifecycle_events(self):
        """라이프사이클 이벤트 Enum 테스트"""
        from mt_paas.core.lifecycle import LifecycleEvent

        assert LifecycleEvent.BEFORE_CREATE.value == "before_create"
        assert LifecycleEvent.AFTER_CREATE.value == "after_create"
        assert LifecycleEvent.BEFORE_PROVISION.value == "before_provision"
        assert LifecycleEvent.AFTER_ACTIVATE.value == "after_activate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
