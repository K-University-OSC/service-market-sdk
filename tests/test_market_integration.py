"""
Service Market Integration Tests

서비스 마켓 시뮬레이터와 멀티 테넌트 서비스 간의 연동을 테스트합니다.

실행:
    # 단위 테스트 (mock 기반)
    pytest tests/test_market_integration.py -v

    # 통합 테스트 (실제 서버 필요)
    pytest tests/test_market_integration.py -v -m integration
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


class TestWebhookPayload:
    """웹훅 페이로드 테스트 (실제 service_market 스펙)"""

    def test_demo_payload_format(self, sample_demo_application):
        """데모 신청 페이로드 형식 테스트"""
        payload = sample_demo_application.to_webhook_payload()

        # 실제 service_market 스펙: application, applicant, service 객체
        assert "application" in payload
        assert "applicant" in payload
        assert "service" in payload

        # application 구조 확인
        application = payload["application"]
        assert "id" in application
        assert "kind" in application
        assert application["kind"] == "demo"

        # applicant 구조 확인
        applicant = payload["applicant"]
        assert "id" in applicant
        assert "name" in applicant
        assert "email" in applicant
        assert "university_name" in applicant

        # service 구조 확인
        service = payload["service"]
        assert "id" in service
        assert "slug" in service
        assert "title" in service

    def test_service_payload_format(self, sample_service_application):
        """서비스 신청 페이로드 형식 테스트"""
        payload = sample_service_application.to_webhook_payload()

        # 실제 service_market 스펙
        assert payload["application"]["kind"] == "service"

    def test_payload_has_contact_and_reason(self, sample_demo_application):
        """페이로드에 contact, reason 필드가 있는지 테스트 (application 객체 안에)"""
        payload = sample_demo_application.to_webhook_payload()

        # 실제 service_market 스펙: contact, reason은 application 객체 안에
        assert "contact" in payload["application"]
        assert "reason" in payload["application"]


class TestWebhookResponse:
    """웹훅 응답 테스트 (실제 service_market 스펙)"""

    def test_approved_response_parsing(self, result_store, sample_demo_application):
        """승인 응답 파싱 테스트"""
        result = result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/api/tenant/webhook/application-approved",
            request_payload={},
            response_code=200,
            response_body={
                "success": True,
                "tenant_id": "demo_123",
                "access_url": "http://service.com?tenant=demo_123",
                "message": "Tenant created successfully",
                "created_at": "2026-02-01T10:00:00"
            },
            response_time_ms=150.0
        )

        assert result.success is True
        assert result.webhook_success is True
        assert result.tenant_id == "demo_123"
        assert result.access_url == "http://service.com?tenant=demo_123"

    def test_processing_response_parsing(self, result_store, sample_demo_application):
        """처리중 응답 파싱 테스트 (success: false로 처리)"""
        result = result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/api/tenant/webhook/application-approved",
            request_payload={},
            response_code=200,
            response_body={
                "success": False,
                "message": "Tenant creation in progress"
            },
            response_time_ms=100.0
        )

        assert result.success is True  # HTTP 200이므로 success
        assert result.webhook_success is False
        assert result.tenant_id is None

    def test_rejected_response_parsing(self, result_store, sample_demo_application):
        """거절 응답 파싱 테스트"""
        result = result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/api/tenant/webhook/application-approved",
            request_payload={},
            response_code=200,
            response_body={
                "success": False,
                "message": "Invalid university domain"
            },
            response_time_ms=50.0
        )

        assert result.success is True  # HTTP 200이므로 success
        assert result.webhook_success is False

    def test_error_response_handling(self, result_store, sample_demo_application):
        """에러 응답 처리 테스트"""
        result = result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/api/tenant/webhook/application-approved",
            request_payload={},
            response_code=500,
            response_body={
                "detail": "Internal server error"
            },
            response_time_ms=200.0,
            error=None  # HTTP 500은 성공으로 처리되지 않음
        )

        assert result.success is False
        assert result.webhook_success is None  # 500 에러시 success 필드가 없음


class TestApplicationStatusFlow:
    """신청 상태 흐름 테스트"""

    def test_pending_to_sent(self, webhook_test_context):
        """pending → sent 상태 전환 테스트"""
        ctx = webhook_test_context

        app = ctx.applications.create_demo_application(
            applicant_email="flow1@test.ac.kr",
            applicant_name="Flow Test",
            university_name="Flow University"
        )
        assert app.status == "pending"

        # 웹훅 전송 후 (processing 응답)
        ctx.results.save_result(
            application_id=app.id,
            target_url="http://localhost:8000/webhook",
            request_payload={},
            response_code=200,
            response_body={"status": "processing", "message": "..."},
            response_time_ms=100.0
        )
        ctx.applications.update_status(app.id, "sent")

        updated = ctx.applications.get_application(app.id)
        assert updated.status == "sent"

    def test_pending_to_completed(self, webhook_test_context):
        """pending → completed 상태 전환 테스트 (즉시 승인)"""
        ctx = webhook_test_context

        app = ctx.applications.create_demo_application(
            applicant_email="flow2@test.ac.kr",
            applicant_name="Flow Test",
            university_name="Flow University"
        )

        # 즉시 승인
        ctx.results.save_result(
            application_id=app.id,
            target_url="http://localhost:8000/webhook",
            request_payload={},
            response_code=200,
            response_body={"status": "approved", "tenant_id": "t1"},
            response_time_ms=100.0
        )
        ctx.applications.update_status(app.id, "completed")

        updated = ctx.applications.get_application(app.id)
        assert updated.status == "completed"

    def test_pending_to_failed(self, webhook_test_context):
        """pending → failed 상태 전환 테스트"""
        ctx = webhook_test_context

        app = ctx.applications.create_demo_application(
            applicant_email="flow3@test.ac.kr",
            applicant_name="Flow Test",
            university_name="Flow University"
        )

        # 웹훅 실패
        ctx.results.save_result(
            application_id=app.id,
            target_url="http://localhost:8000/webhook",
            request_payload={},
            response_code=None,
            response_body=None,
            response_time_ms=5000.0,
            error="Connection refused"
        )
        ctx.applications.update_status(app.id, "failed")

        updated = ctx.applications.get_application(app.id)
        assert updated.status == "failed"


class TestTenantReuse:
    """테넌트 재사용 테스트"""

    def test_same_email_same_tenant_concept(self, webhook_test_context):
        """동일 이메일은 동일 테넌트를 재사용해야 함 (개념 테스트)"""
        ctx = webhook_test_context

        email = "reuse@test.ac.kr"

        # 첫 번째 신청
        app1 = ctx.applications.create_demo_application(
            applicant_email=email,
            applicant_name="User",
            university_name="Test University"
        )

        # 두 번째 신청 (동일 이메일)
        app2 = ctx.applications.create_demo_application(
            applicant_email=email,
            applicant_name="User",
            university_name="Test University"
        )

        # 시뮬레이터는 신청만 관리, 테넌트 재사용은 AI 서비스 책임
        # 여기서는 동일 이메일로 여러 신청이 가능함을 확인
        assert app1.applicant_email == app2.applicant_email
        assert app1.id != app2.id


class TestStatisticsCalculation:
    """통계 계산 테스트"""

    def test_empty_statistics(self, result_store):
        """빈 통계 테스트"""
        stats = result_store.get_statistics()

        assert stats.total_applications == 0
        assert stats.total_webhook_calls == 0
        assert stats.success_rate == 0.0

    def test_mixed_results_statistics(self, webhook_test_context):
        """혼합 결과 통계 테스트"""
        ctx = webhook_test_context

        # 데모 2개, 서비스 1개 생성
        demo1 = ctx.applications.create_demo_application(
            applicant_email="stats1@test.ac.kr",
            applicant_name="Stats 1",
            university_name="Univ 1"
        )
        demo2 = ctx.applications.create_demo_application(
            applicant_email="stats2@test.ac.kr",
            applicant_name="Stats 2",
            university_name="Univ 2"
        )
        service1 = ctx.applications.create_service_application(
            applicant_email="stats3@test.ac.kr",
            applicant_name="Stats 3",
            university_name="Univ 3",
            start_date="2026-01-01",
            end_date="2026-12-31"
        )

        # 성공 2개, 실패 1개
        ctx.results.save_result(
            application_id=demo1.id,
            target_url="http://test.com",
            request_payload={},
            response_code=200,
            response_body={"status": "approved"},
            response_time_ms=100.0
        )
        ctx.results.save_result(
            application_id=demo2.id,
            target_url="http://test.com",
            request_payload={},
            response_code=200,
            response_body={"status": "approved"},
            response_time_ms=150.0
        )
        ctx.results.save_result(
            application_id=service1.id,
            target_url="http://test.com",
            request_payload={},
            response_code=None,
            response_body=None,
            response_time_ms=5000.0,
            error="Timeout"
        )

        stats = ctx.results.get_statistics()

        assert stats.total_applications == 3
        assert stats.demo_applications == 2
        assert stats.service_applications == 1
        assert stats.total_webhook_calls == 3
        assert stats.successful_calls == 2
        assert stats.failed_calls == 1
        assert stats.success_rate == pytest.approx(66.67, rel=0.1)


class TestServiceMarketAPISimulation:
    """서비스 마켓 API 시뮬레이션 테스트"""

    def test_demo_application_api_flow(self, webhook_test_context):
        """데모 신청 API 흐름 테스트"""
        ctx = webhook_test_context

        # 1. POST /applications/demo 시뮬레이션
        app = ctx.applications.create_demo_application(
            applicant_email="api_demo@university.ac.kr",
            applicant_name="API Demo User",
            university_name="API Demo University",
            service_slug="keli-tutor",
            service_title="KELI Tutor"
        )

        assert app.kind == "demo"
        assert app.service_slug == "keli-tutor"

        # 2. POST /applications/{id}/send 시뮬레이션 (mock)
        payload = app.to_webhook_payload()
        mock_response = {
            "status": "approved",
            "tenant_id": f"demo_{app.application_id}",
            "tenant_url": f"http://keli-tutor.example.com/?tenant=demo_{app.application_id}",
            "message": "Demo tenant created",
            "expires_at": "2026-03-01T23:59:59"
        }

        result = ctx.results.save_result(
            application_id=app.id,
            target_url="http://keli-tutor.example.com/api/tenant/webhook/auto-provision",
            request_payload=payload,
            response_code=200,
            response_body=mock_response,
            response_time_ms=250.0
        )

        ctx.applications.update_status(app.id, "completed")

        # 3. 결과 검증
        assert result.success
        assert result.tenant_id == f"demo_{app.application_id}"

        final_app = ctx.applications.get_application(app.id)
        assert final_app.status == "completed"

    def test_service_application_api_flow(self, webhook_test_context):
        """서비스 신청 API 흐름 테스트"""
        ctx = webhook_test_context

        # 1. POST /applications/service
        app = ctx.applications.create_service_application(
            applicant_email="api_service@university.ac.kr",
            applicant_name="API Service Admin",
            university_name="API Service University",
            start_date="2026-03-01",
            end_date="2027-02-28",
            service_slug="advisor",
            service_title="AI Advisor"
        )

        assert app.kind == "service"
        assert app.service_slug == "advisor"

        # 2. 웹훅 전송 (mock)
        payload = app.to_webhook_payload()
        mock_response = {
            "status": "approved",
            "tenant_id": f"service_{app.application_id}",
            "tenant_url": f"http://advisor.example.com/?tenant=service_{app.application_id}",
            "message": "Service tenant created",
        }

        result = ctx.results.save_result(
            application_id=app.id,
            target_url="http://advisor.example.com/api/tenant/webhook/auto-provision",
            request_payload=payload,
            response_code=200,
            response_body=mock_response,
            response_time_ms=300.0
        )

        ctx.applications.update_status(app.id, "completed")

        # 3. 검증
        assert result.success
        assert "service_" in result.tenant_id


# Integration tests (requires running servers)
@pytest.mark.integration
class TestLiveIntegration:
    """실제 서버를 사용한 통합 테스트

    이 테스트를 실행하려면:
    1. 샘플 서비스 실행: cd sandbox/sample_service && uvicorn server:app --port 8000
    2. pytest tests/test_market_integration.py -v -m integration
    """

    @pytest.mark.skip(reason="Requires running sample_service")
    def test_live_demo_webhook(self, webhook_test_context):
        """실제 서버에 데모 웹훅 전송 테스트"""
        # 이 테스트는 sample_service가 실행 중일 때만 동작
        pass

    @pytest.mark.skip(reason="Requires running sample_service")
    def test_live_tenant_reuse(self, webhook_test_context):
        """실제 서버에서 테넌트 재사용 테스트"""
        pass
