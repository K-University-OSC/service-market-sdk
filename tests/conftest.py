"""
Multi-Tenant PaaS - Pytest Configuration

테스트에서 사용할 공통 fixture들을 정의합니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Simulator fixtures import
from sandbox.simulator.fixtures import (
    simulator_db,
    application_manager,
    result_store,
    sample_demo_application,
    sample_service_application,
    sample_webhook_result,
    sample_failed_result,
    webhook_test_context,
    multiple_applications,
    WebhookTestContext,
)

# Re-export all fixtures
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
