"""
Core 모듈 - 멀티테넌트 핵심 기능

- TenantManager: 테넌트 생명주기 관리
- DatabaseManager: DB 연결 풀 관리
- TenantLifecycle: 테넌트 라이프사이클 관리
- Tenant, Subscription: 모델
"""
from .manager import TenantManager
from .database import DatabaseManager
from .models import Tenant, TenantStatus, Subscription, SubscriptionPlan, UsageLog
from .schemas import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    SubscriptionCreate,
    SubscriptionResponse,
)
from .lifecycle import TenantLifecycle, LifecycleEvent

__all__ = [
    # Managers
    "TenantManager",
    "DatabaseManager",
    "TenantLifecycle",
    "LifecycleEvent",
    # Models
    "Tenant",
    "TenantStatus",
    "Subscription",
    "SubscriptionPlan",
    "UsageLog",
    # Schemas
    "TenantCreate",
    "TenantUpdate",
    "TenantResponse",
    "SubscriptionCreate",
    "SubscriptionResponse",
]
