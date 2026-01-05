"""
통합 테스트

Service Market ↔ KELI Tutor 통합 테스트
(DB 없이 Mock 사용)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
sys.path.insert(0, "/home/aiedu/workspace/multi_tenant_paas")
sys.path.insert(0, "/home/aiedu/workspace/service_market/tenant-templates/keli_tutor")


class TestServiceMarketClient:
    """Service Market 클라이언트 테스트"""

    def test_client_creation(self):
        """클라이언트 생성"""
        from mt_paas.market import ServiceClient

        client = ServiceClient(
            base_url="https://keli.example.com",
            api_key="test-api-key"
        )
        assert client.base_url == "https://keli.example.com"
        assert client.api_key == "test-api-key"

    def test_url_generation(self):
        """URL 생성"""
        from mt_paas.market import ServiceClient

        client = ServiceClient(
            base_url="https://keli.example.com",
            api_key="test"
        )
        url = client._url("/mt/tenant/{tenant_id}/status", tenant_id="hallym")
        assert url == "https://keli.example.com/mt/tenant/hallym/status"


class TestServiceMarketIntegration:
    """Market 통합 클라이언트 테스트"""

    def test_register_service(self):
        """서비스 등록"""
        from mt_paas.market import ServiceMarketClient

        market = ServiceMarketClient()
        market.register_service(
            service_id="keli_tutor",
            base_url="https://keli.example.com",
            api_key="test-key"
        )

        assert "keli_tutor" in market._services
        client = market.get_service("keli_tutor")
        assert client.base_url == "https://keli.example.com"

    def test_get_unknown_service(self):
        """없는 서비스 조회"""
        from mt_paas.market import ServiceMarketClient

        market = ServiceMarketClient()

        with pytest.raises(ValueError, match="not registered"):
            market.get_service("unknown_service")


class TestActivationFlow:
    """활성화 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_activation_request_format(self):
        """활성화 요청 형식"""
        from mt_paas.market.models import TenantActivation

        activation = TenantActivation(
            tenant_id="hallym_univ",
            tenant_name="한림대학교",
            service_id="keli_tutor",
            plan="premium",
            features=["ai_chat", "rag", "quiz"],
            contact_email="admin@hallym.ac.kr",
            contact_name="홍길동"
        )

        assert activation.tenant_id == "hallym_univ"
        assert activation.plan == "premium"
        assert "rag" in activation.features

    @pytest.mark.asyncio
    async def test_mock_activation(self):
        """Mock 활성화 테스트"""
        from mt_paas.market import ServiceMarketClient
        from mt_paas.market.models import TenantActivation

        market = ServiceMarketClient()
        market.register_service(
            service_id="keli_tutor",
            base_url="https://keli.example.com",
            api_key="test-key"
        )

        # Mock HTTP 클라이언트
        mock_response = {
            "success": True,
            "tenant_id": "hallym_univ",
            "access_url": "https://keli.example.com/hallym_univ",
            "message": "Activated"
        }

        with patch.object(
            market._services["keli_tutor"],
            "activate_tenant",
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            activation = TenantActivation(
                tenant_id="hallym_univ",
                tenant_name="한림대학교",
                service_id="keli_tutor",
                plan="premium",
                features=["ai_chat"],
                contact_email="admin@hallym.ac.kr",
                contact_name="홍길동"
            )

            result = await market.activate_tenant("keli_tutor", activation)
            assert result["success"] == True
            assert result["tenant_id"] == "hallym_univ"


class TestDeactivationFlow:
    """비활성화 플로우 테스트"""

    @pytest.mark.asyncio
    async def test_deactivation_request_format(self):
        """비활성화 요청 형식"""
        from mt_paas.market.models import TenantDeactivation

        deactivation = TenantDeactivation(
            tenant_id="hallym_univ",
            service_id="keli_tutor",
            reason="subscription_expired",
            preserve_data=True
        )

        assert deactivation.reason == "subscription_expired"
        assert deactivation.preserve_data == True


class TestUsageFlow:
    """사용량 조회 플로우 테스트"""

    def test_usage_report_model(self):
        """사용량 보고서 모델"""
        from mt_paas.market.models import UsageReport, UsageMetric

        report = UsageReport(
            tenant_id="hallym_univ",
            service_id="keli_tutor",
            period="2026-01",
            metrics=[
                UsageMetric(name="active_users", value=150, unit="count"),
                UsageMetric(name="ai_tokens", value=500000, unit="tokens"),
            ],
            total_cost=150000
        )

        assert report.tenant_id == "hallym_univ"
        assert len(report.metrics) == 2
        assert report.total_cost == 150000


class TestBillingFlow:
    """빌링 플로우 테스트"""

    def test_billing_info_model(self):
        """빌링 정보 모델"""
        from mt_paas.market.models import BillingInfo, BillingItem

        billing = BillingInfo(
            tenant_id="hallym_univ",
            service_id="keli_tutor",
            period="2026-01",
            items=[
                BillingItem(
                    name="AI 토큰 사용량",
                    unit="1000 tokens",
                    quantity=500,
                    unit_price=5,
                    amount=2500
                ),
                BillingItem(
                    name="API 호출",
                    unit="1000 calls",
                    quantity=15,
                    unit_price=10,
                    amount=150
                ),
            ],
            subtotal=2650,
            tax=265,
            total=2915,
            currency="KRW"
        )

        assert billing.total == 2915
        assert len(billing.items) == 2


class TestKeliTutorHandler:
    """KELI Tutor 핸들러 테스트"""

    def test_handler_creation(self):
        """핸들러 생성"""
        from app.handler import KeliTutorHandler

        mock_mt = MagicMock()
        handler = KeliTutorHandler(mock_mt)

        assert handler.service_version == "1.0.0"
        assert "k-university" in handler.base_url


class TestEndToEndScenario:
    """E2E 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_full_tenant_lifecycle(self):
        """전체 테넌트 생명주기 시나리오"""
        from mt_paas.market import ServiceMarketClient
        from mt_paas.market.models import TenantActivation, TenantDeactivation

        # 1. Market 초기화
        market = ServiceMarketClient()

        # 2. 서비스 등록
        market.register_service(
            service_id="keli_tutor",
            base_url="https://keli.k-university.ai",
            api_key="test-api-key"
        )

        # 3. Mock 설정
        client = market.get_service("keli_tutor")

        # Mock activate
        with patch.object(client, "activate_tenant", new_callable=AsyncMock) as mock_activate:
            mock_activate.return_value = {
                "success": True,
                "tenant_id": "test_univ",
                "access_url": "https://keli.k-university.ai/test_univ",
                "message": "Activated"
            }

            activation = TenantActivation(
                tenant_id="test_univ",
                tenant_name="테스트 대학교",
                service_id="keli_tutor",
                plan="premium",
                features=["ai_chat", "rag"],
                contact_email="admin@test.ac.kr",
                contact_name="관리자"
            )

            result = await market.activate_tenant("keli_tutor", activation)
            assert result["success"] == True

        # Mock status
        with patch.object(client, "get_tenant_status", new_callable=AsyncMock) as mock_status:
            mock_status.return_value = {
                "tenant_id": "test_univ",
                "status": "active",
                "plan": "premium",
                "features": ["ai_chat", "rag"]
            }

            status = await client.get_tenant_status("test_univ")
            assert status["status"] == "active"

        # Mock usage
        with patch.object(client, "get_tenant_usage", new_callable=AsyncMock) as mock_usage:
            mock_usage.return_value = {
                "tenant_id": "test_univ",
                "period": "2026-01",
                "usage": {
                    "active_users": 50,
                    "ai_tokens": 100000
                }
            }

            usage = await client.get_tenant_usage("test_univ", "2026-01")
            assert usage["usage"]["active_users"] == 50

        # Mock deactivate
        with patch.object(client, "deactivate_tenant", new_callable=AsyncMock) as mock_deactivate:
            mock_deactivate.return_value = {
                "success": True,
                "tenant_id": "test_univ",
                "status": "suspended",
                "data_preserved": True
            }

            deactivation = TenantDeactivation(
                tenant_id="test_univ",
                service_id="keli_tutor",
                reason="subscription_expired",
                preserve_data=True
            )

            result = await market.deactivate_tenant("keli_tutor", deactivation)
            assert result["success"] == True
            assert result["data_preserved"] == True

        print("Full tenant lifecycle test passed!")


class TestPortConfiguration:
    """포트 설정 테스트"""

    def test_port_range(self):
        """포트 범위 확인 (11000-12000)"""
        from mt_paas.config import Ports

        assert 11000 <= Ports.MT_PAAS_API <= 12000
        assert 11000 <= Ports.SERVICE_MARKET_API <= 12000
        assert 11000 <= Ports.KELI_TUTOR_BASE <= 12000
        assert 11000 <= Ports.TENANT_RANGE_START <= 12000
        assert 11000 <= Ports.TENANT_RANGE_END <= 12000

    def test_no_port_conflict(self):
        """포트 충돌 없음 확인"""
        from mt_paas.config import Ports

        ports = [
            Ports.MT_PAAS_API,
            Ports.MT_PAAS_ADMIN,
            Ports.SERVICE_MARKET_API,
            Ports.SERVICE_MARKET_WEB,
            Ports.KELI_TUTOR_BASE,
        ]

        # 모든 포트가 고유한지 확인
        assert len(ports) == len(set(ports)), "Port conflict detected!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
