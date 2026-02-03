"""
Service Market Simulator Package

서비스 마켓의 동작을 시뮬레이션하여 멀티 테넌트 서비스를 테스트합니다.

Usage:
    # CLI 사용
    python -m sandbox.simulator.cli serve --port 9000
    python -m sandbox.simulator.cli demo --target http://localhost:8000/api/tenant/webhook/auto-provision

    # Python에서 사용
    from sandbox.simulator import ApplicationManager, ResultStore, SimulatorDatabase

    db = SimulatorDatabase(":memory:")
    db.init_db()

    manager = ApplicationManager(db)
    app = manager.create_demo_application(
        applicant_email="test@univ.ac.kr",
        applicant_name="Test User",
        university_name="Test University"
    )
"""

from .database import SimulatorDatabase
from .application_manager import ApplicationManager
from .result_store import ResultStore
from .models import (
    Application,
    WebhookResult,
    ApplicationCreate,
    DemoApplicationRequest,
    ServiceApplicationRequest,
    WebhookResponseModel,
)

__all__ = [
    "SimulatorDatabase",
    "ApplicationManager",
    "ResultStore",
    "Application",
    "WebhookResult",
    "ApplicationCreate",
    "DemoApplicationRequest",
    "ServiceApplicationRequest",
    "WebhookResponseModel",
]

__version__ = "1.0.0"
