"""
Service Market Simulator - Unit Tests

시뮬레이터의 각 컴포넌트를 단위 테스트합니다.

실행:
    cd ~/workspace/multi_tenant_paas
    pytest tests/test_simulator.py -v
"""

import pytest
from datetime import date, timedelta


class TestSimulatorDatabase:
    """SimulatorDatabase 테스트"""

    def test_database_initialization(self, simulator_db):
        """데이터베이스 초기화 테스트"""
        # 테이블 존재 확인
        tables = simulator_db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = [t["name"] for t in tables]

        assert "applications" in table_names
        assert "webhook_results" in table_names

    def test_insert_and_fetch(self, simulator_db):
        """데이터 삽입 및 조회 테스트"""
        from datetime import datetime

        data = {
            "application_id": 9999,
            "kind": "demo",
            "status": "pending",
            "applicant_id": 1,
            "applicant_name": "Test",
            "applicant_email": "test@test.com",
            "university_name": "Test Univ",
            "service_id": 1,
            "service_slug": "test",
            "service_title": "Test",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        row_id = simulator_db.insert("applications", data)
        assert row_id > 0

        row = simulator_db.fetch_one(
            "SELECT * FROM applications WHERE id = ?", (row_id,)
        )
        assert row is not None
        assert row["application_id"] == 9999
        assert row["kind"] == "demo"


class TestApplicationManager:
    """ApplicationManager 테스트"""

    def test_create_demo_application(self, application_manager):
        """데모 신청 생성 테스트"""
        app = application_manager.create_demo_application(
            applicant_email="demo@test.ac.kr",
            applicant_name="Demo User",
            university_name="Demo University"
        )

        assert app.id > 0
        assert app.application_id >= 1000
        assert app.kind == "demo"
        assert app.status == "pending"
        assert app.applicant_email == "demo@test.ac.kr"

        # 30일 기간 확인
        start = date.fromisoformat(app.start_date)
        end = date.fromisoformat(app.end_date)
        assert (end - start).days == 30

    def test_create_service_application(self, application_manager):
        """서비스 신청 생성 테스트"""
        app = application_manager.create_service_application(
            applicant_email="service@test.ac.kr",
            applicant_name="Service User",
            university_name="Service University",
            start_date="2026-03-01",
            end_date="2026-12-31"
        )

        assert app.id > 0
        assert app.kind == "service"
        assert app.start_date == "2026-03-01"
        assert app.end_date == "2026-12-31"

    def test_get_application(self, application_manager, sample_demo_application):
        """신청 조회 테스트"""
        app = application_manager.get_application(sample_demo_application.id)
        assert app is not None
        assert app.id == sample_demo_application.id

    def test_get_nonexistent_application(self, application_manager):
        """존재하지 않는 신청 조회 테스트"""
        app = application_manager.get_application(99999)
        assert app is None

    def test_list_applications(self, application_manager, multiple_applications):
        """신청 목록 조회 테스트"""
        # 전체 조회
        apps = application_manager.list_applications()
        assert len(apps) == 5

        # 데모만 조회
        demo_apps = application_manager.list_applications(kind="demo")
        assert len(demo_apps) == 3

        # 서비스만 조회
        service_apps = application_manager.list_applications(kind="service")
        assert len(service_apps) == 2

    def test_update_status(self, application_manager, sample_demo_application):
        """상태 업데이트 테스트"""
        updated = application_manager.update_status(
            sample_demo_application.id, "sent"
        )

        assert updated is not None
        assert updated.status == "sent"

    def test_delete_application(self, application_manager, sample_demo_application):
        """신청 삭제 테스트"""
        app_id = sample_demo_application.id

        result = application_manager.delete_application(app_id)
        assert result is True

        # 삭제 확인
        app = application_manager.get_application(app_id)
        assert app is None

    def test_count_applications(self, application_manager, multiple_applications):
        """신청 개수 조회 테스트"""
        total = application_manager.count_applications()
        assert total == 5

        demo_count = application_manager.count_applications(kind="demo")
        assert demo_count == 3

        pending_count = application_manager.count_applications(status="pending")
        assert pending_count == 5


class TestResultStore:
    """ResultStore 테스트"""

    def test_save_successful_result(self, result_store, sample_demo_application):
        """성공 결과 저장 테스트"""
        result = result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/api/tenant/webhook/application-approved",
            request_payload={"test": True},
            response_code=200,
            response_body={
                "success": True,
                "tenant_id": "test_1",
                "access_url": "http://test.com?tenant=test_1",
                "message": "Success"
            },
            response_time_ms=100.0
        )

        assert result.id > 0
        assert result.success is True
        assert result.webhook_success is True
        assert result.tenant_id == "test_1"

    def test_save_failed_result(self, result_store, sample_demo_application):
        """실패 결과 저장 테스트"""
        result = result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/webhook",
            request_payload={"test": True},
            response_code=None,
            response_body=None,
            response_time_ms=5000.0,
            error="Connection timeout"
        )

        assert result.success is False
        assert result.error_message == "Connection timeout"

    def test_get_result(self, result_store, sample_webhook_result):
        """결과 조회 테스트"""
        result = result_store.get_result(sample_webhook_result.id)
        assert result is not None
        assert result.id == sample_webhook_result.id

    def test_get_results_for_application(
        self, result_store, sample_demo_application
    ):
        """신청별 결과 조회 테스트"""
        # 여러 결과 저장
        for i in range(3):
            result_store.save_result(
                application_id=sample_demo_application.id,
                target_url="http://localhost:8000/webhook",
                request_payload={"test": i},
                response_code=200,
                response_body={"status": "approved"},
                response_time_ms=100.0 + i * 10
            )

        results = result_store.get_results_for_application(
            sample_demo_application.id
        )
        assert len(results) == 3

    def test_get_latest_results(self, result_store, sample_demo_application):
        """최신 결과 조회 테스트"""
        # 5개 결과 저장
        for i in range(5):
            result_store.save_result(
                application_id=sample_demo_application.id,
                target_url="http://localhost:8000/webhook",
                request_payload={"index": i},
                response_code=200,
                response_body={"status": "approved"},
                response_time_ms=100.0
            )

        # 3개만 조회
        results = result_store.get_latest_results(3)
        assert len(results) == 3

    def test_get_statistics(self, result_store, sample_demo_application):
        """통계 조회 테스트"""
        # 성공 결과 2개
        for _ in range(2):
            result_store.save_result(
                application_id=sample_demo_application.id,
                target_url="http://localhost:8000/webhook",
                request_payload={},
                response_code=200,
                response_body={"status": "approved"},
                response_time_ms=100.0
            )

        # 실패 결과 1개
        result_store.save_result(
            application_id=sample_demo_application.id,
            target_url="http://localhost:8000/webhook",
            request_payload={},
            response_code=None,
            response_body=None,
            response_time_ms=5000.0,
            error="Timeout"
        )

        stats = result_store.get_statistics()

        assert stats.total_webhook_calls == 3
        assert stats.successful_calls == 2
        assert stats.failed_calls == 1
        assert stats.success_rate == pytest.approx(66.67, rel=0.1)


class TestApplicationModel:
    """Application 모델 테스트"""

    def test_to_webhook_payload(self, sample_demo_application):
        """웹훅 페이로드 변환 테스트 (실제 service_market 스펙)"""
        payload = sample_demo_application.to_webhook_payload()

        # 실제 service_market 스펙에서는 application 객체 안에 id, kind 등이 포함
        assert "application" in payload
        assert "applicant" in payload
        assert "service" in payload

        assert payload["application"]["kind"] == "demo"
        assert payload["application"]["id"] == sample_demo_application.application_id
        assert payload["applicant"]["email"] == sample_demo_application.applicant_email

    def test_to_response(self, sample_demo_application):
        """API 응답 변환 테스트"""
        response = sample_demo_application.to_response()

        assert response.id == sample_demo_application.id
        assert response.application_id == sample_demo_application.application_id
        assert response.kind == "demo"


class TestWebhookTestContext:
    """WebhookTestContext 테스트"""

    def test_context_has_all_managers(self, webhook_test_context):
        """컨텍스트에 모든 매니저가 있는지 테스트"""
        ctx = webhook_test_context

        assert ctx.db is not None
        assert ctx.applications is not None
        assert ctx.results is not None

    def test_context_workflow(self, webhook_test_context):
        """컨텍스트를 사용한 전체 워크플로우 테스트"""
        ctx = webhook_test_context

        # 1. 신청 생성
        app = ctx.applications.create_demo_application(
            applicant_email="workflow@test.ac.kr",
            applicant_name="Workflow Test",
            university_name="Workflow University"
        )
        assert app.id > 0

        # 2. 결과 저장
        result = ctx.results.save_result(
            application_id=app.id,
            target_url="http://test.com/webhook",
            request_payload=app.to_webhook_payload(),
            response_code=200,
            response_body={"status": "approved", "tenant_id": "wf_1"},
            response_time_ms=150.0
        )
        assert result.success

        # 3. 상태 업데이트
        ctx.applications.update_status(app.id, "completed")

        # 4. 확인
        updated = ctx.applications.get_application(app.id)
        assert updated.status == "completed"

        results = ctx.results.get_results_for_application(app.id)
        assert len(results) == 1
