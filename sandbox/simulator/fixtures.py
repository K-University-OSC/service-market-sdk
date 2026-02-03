"""
Service Market Simulator - Pytest Fixtures

pytest에서 사용할 수 있는 fixture들을 제공합니다.

Usage:
    # tests/conftest.py에서 import
    from sandbox.simulator.fixtures import *

    # 테스트에서 사용
    def test_create_application(application_manager):
        app = application_manager.create_demo_application(
            applicant_email="test@univ.ac.kr",
            applicant_name="Test",
            university_name="Test University"
        )
        assert app.kind == "demo"
"""

import pytest
from typing import Generator
from dataclasses import dataclass

from .database import SimulatorDatabase, get_database
from .application_manager import ApplicationManager
from .result_store import ResultStore
from .models import Application, WebhookResult


@dataclass
class WebhookTestContext:
    """테스트 컨텍스트 - 모든 매니저를 한 번에 제공"""
    db: SimulatorDatabase
    applications: ApplicationManager
    results: ResultStore


@pytest.fixture
def simulator_db() -> Generator[SimulatorDatabase, None, None]:
    """
    인메모리 SQLite 데이터베이스 fixture

    Usage:
        def test_something(simulator_db):
            # simulator_db는 초기화된 SimulatorDatabase 인스턴스
            row = simulator_db.fetch_one("SELECT 1")
    """
    db = get_database(":memory:")
    yield db
    db.close()


@pytest.fixture
def application_manager(simulator_db: SimulatorDatabase) -> ApplicationManager:
    """
    ApplicationManager fixture

    Usage:
        def test_create_app(application_manager):
            app = application_manager.create_demo_application(
                applicant_email="test@univ.ac.kr",
                applicant_name="Test",
                university_name="Test University"
            )
            assert app.id > 0
    """
    return ApplicationManager(simulator_db)


@pytest.fixture
def result_store(simulator_db: SimulatorDatabase) -> ResultStore:
    """
    ResultStore fixture

    Usage:
        def test_save_result(result_store, sample_demo_application):
            result = result_store.save_result(
                application_id=sample_demo_application.id,
                target_url="http://localhost:8000/api/tenant/webhook/application-approved",
                request_payload={"application": {...}, "applicant": {...}, "service": {...}},
                response_code=200,
                response_body={"success": True, "tenant_id": "...", "access_url": "..."},
                response_time_ms=100.0
            )
            assert result.success
    """
    return ResultStore(simulator_db)


@pytest.fixture
def sample_demo_application(application_manager: ApplicationManager) -> Application:
    """
    샘플 데모 신청 fixture

    Usage:
        def test_demo_app(sample_demo_application):
            assert sample_demo_application.kind == "demo"
            assert sample_demo_application.status == "pending"
    """
    return application_manager.create_demo_application(
        applicant_email="demo_test@university.ac.kr",
        applicant_name="Demo Test User",
        university_name="Demo Test University"
    )


@pytest.fixture
def sample_service_application(application_manager: ApplicationManager) -> Application:
    """
    샘플 서비스 신청 fixture

    Usage:
        def test_service_app(sample_service_application):
            assert sample_service_application.kind == "service"
    """
    return application_manager.create_service_application(
        applicant_email="service_test@university.ac.kr",
        applicant_name="Service Test User",
        university_name="Service Test University",
        start_date="2026-02-01",
        end_date="2026-12-31"
    )


@pytest.fixture
def sample_webhook_result(
    result_store: ResultStore,
    sample_demo_application: Application
) -> WebhookResult:
    """
    샘플 웹훅 결과 fixture (실제 service_market 스펙)

    Usage:
        def test_webhook_result(sample_webhook_result):
            assert sample_webhook_result.success
            assert sample_webhook_result.tenant_id == "test_tenant_1"
    """
    return result_store.save_result(
        application_id=sample_demo_application.id,
        target_url="http://localhost:8000/api/tenant/webhook/application-approved",
        request_payload=sample_demo_application.to_webhook_payload(),
        response_code=200,
        response_body={
            "success": True,
            "tenant_id": "test_tenant_1",
            "message": "테넌트 'Demo Test University' 생성 완료",
            "access_url": "http://localhost:8000/?tenant=test_tenant_1",
            "admin_credentials": {
                "email": "demo_test@university.ac.kr",
                "note": "LMS 계정으로 로그인하세요."
            },
            "created_at": "2026-02-01T10:00:00"
        },
        response_time_ms=150.0
    )


@pytest.fixture
def sample_failed_result(
    result_store: ResultStore,
    sample_demo_application: Application
) -> WebhookResult:
    """
    샘플 실패한 웹훅 결과 fixture

    Usage:
        def test_failed_result(sample_failed_result):
            assert not sample_failed_result.success
    """
    return result_store.save_result(
        application_id=sample_demo_application.id,
        target_url="http://localhost:8000/api/tenant/webhook/application-approved",
        request_payload=sample_demo_application.to_webhook_payload(),
        response_code=None,
        response_body=None,
        response_time_ms=5000.0,
        error="Connection timeout"
    )


@pytest.fixture
def webhook_test_context(
    simulator_db: SimulatorDatabase,
    application_manager: ApplicationManager,
    result_store: ResultStore
) -> WebhookTestContext:
    """
    통합 테스트 컨텍스트 fixture

    모든 매니저를 한 번에 제공합니다.

    Usage:
        def test_full_flow(webhook_test_context):
            ctx = webhook_test_context

            # 신청 생성
            app = ctx.applications.create_demo_application(...)

            # 결과 저장
            result = ctx.results.save_result(...)

            # DB 직접 접근
            row = ctx.db.fetch_one("SELECT COUNT(*) FROM applications")
    """
    return WebhookTestContext(
        db=simulator_db,
        applications=application_manager,
        results=result_store
    )


@pytest.fixture
def multiple_applications(application_manager: ApplicationManager) -> list[Application]:
    """
    여러 신청 fixture (테스트용)

    Usage:
        def test_list_applications(multiple_applications):
            assert len(multiple_applications) == 5
    """
    apps = []

    # 데모 신청 3개
    for i in range(3):
        app = application_manager.create_demo_application(
            applicant_email=f"demo{i}@university.ac.kr",
            applicant_name=f"Demo User {i}",
            university_name=f"University {i}"
        )
        apps.append(app)

    # 서비스 신청 2개
    for i in range(2):
        app = application_manager.create_service_application(
            applicant_email=f"service{i}@university.ac.kr",
            applicant_name=f"Service User {i}",
            university_name=f"Service University {i}",
            start_date="2026-03-01",
            end_date="2026-12-31"
        )
        apps.append(app)

    return apps


# Export all fixtures
__all__ = [
    "simulator_db",
    "application_manager",
    "result_store",
    "sample_demo_application",
    "sample_service_application",
    "sample_webhook_result",
    "sample_failed_result",
    "webhook_test_context",
    "multiple_applications",
    "WebhookTestContext",
]
