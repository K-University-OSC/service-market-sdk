"""
Multi-Tenant PaaS (mt_paas)
===========================

Service Market에서 제공하는 공통 멀티테넌트 Platform as a Service

사용법:
    from mt_paas import setup_multi_tenant
    from mt_paas.core import TenantManager, TenantLifecycle
    from mt_paas.middleware import TenantMiddleware, get_current_tenant
    from mt_paas.config import MTPaaSConfig, Ports

Example:
    from fastapi import FastAPI
    from mt_paas import setup_multi_tenant

    app = FastAPI()
    mt = setup_multi_tenant(app, central_db_url="postgresql+asyncpg://...")

    @app.on_event("startup")
    async def startup():
        await mt.init()
"""

from .core.manager import TenantManager
from .core.database import DatabaseManager
from .core.lifecycle import TenantLifecycle
from .core.models import Tenant, TenantStatus, Subscription, SubscriptionPlan
from .core.schemas import TenantCreate, TenantUpdate, TenantResponse
from .middleware.tenant import TenantMiddleware, get_current_tenant, TenantContext
from .setup import setup_multi_tenant, MTPaaS, get_mt_paas
from .config import MTPaaSConfig, Ports, get_config

__version__ = "0.1.0"
__all__ = [
    # Setup
    "setup_multi_tenant",
    "MTPaaS",
    "get_mt_paas",
    # Config
    "MTPaaSConfig",
    "Ports",
    "get_config",
    # Core
    "TenantManager",
    "DatabaseManager",
    "TenantLifecycle",
    "Tenant",
    "TenantStatus",
    "Subscription",
    "SubscriptionPlan",
    # Schemas
    "TenantCreate",
    "TenantUpdate",
    "TenantResponse",
    # Middleware
    "TenantMiddleware",
    "TenantContext",
    "get_current_tenant",
]
