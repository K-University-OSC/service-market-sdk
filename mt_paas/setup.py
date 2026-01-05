"""
FastAPI 앱에 멀티테넌트 기능을 한 번에 설정하는 헬퍼 함수
"""
import logging
from typing import Optional, List, Callable
from fastapi import FastAPI

from mt_paas.core.manager import TenantManager
from mt_paas.core.database import DatabaseManager
from mt_paas.core.lifecycle import TenantLifecycle
from mt_paas.middleware.tenant import TenantMiddleware, TenantContext
from mt_paas.config import MTPaaSConfig, get_config

logger = logging.getLogger(__name__)


class MTPaaS:
    """
    MT-PaaS 통합 객체

    모든 MT-PaaS 기능에 대한 단일 진입점을 제공합니다.

    Example:
        from mt_paas import setup_multi_tenant

        mt = await setup_multi_tenant(app)

        # 테넌트 생성
        tenant = await mt.lifecycle.create(
            tenant_id="hallym_univ",
            name="한림대학교"
        )
    """

    def __init__(
        self,
        app: FastAPI,
        config: MTPaaSConfig,
        db_manager: DatabaseManager,
    ):
        self.app = app
        self.config = config
        self.db = db_manager
        self.manager = TenantManager(db_manager)
        self.lifecycle = TenantLifecycle(db_manager)

    async def init(self) -> None:
        """초기화 (DB 연결 등)"""
        await self.db.init_central_db()
        logger.info("MT-PaaS initialized")

    async def close(self) -> None:
        """리소스 정리"""
        await self.db.close()
        logger.info("MT-PaaS closed")


def setup_multi_tenant(
    app: FastAPI,
    central_db_url: Optional[str] = None,
    config: Optional[MTPaaSConfig] = None,
    tenant_header_name: str = "X-Tenant-ID",
    tenant_lookup: Optional[Callable[[str], TenantContext]] = None,
    exclude_paths: Optional[List[str]] = None,
    require_tenant: bool = False,
) -> MTPaaS:
    """
    FastAPI 앱에 멀티테넌트 기능을 설정합니다.

    Args:
        app: FastAPI 앱 인스턴스
        central_db_url: 중앙 DB URL (테넌트 메타정보 저장)
        config: MT-PaaS 설정 (None이면 환경변수에서 로드)
        tenant_header_name: 테넌트 ID를 담는 HTTP 헤더 이름
        tenant_lookup: 커스텀 테넌트 조회 함수
        exclude_paths: 테넌트 검증 제외 경로
        require_tenant: True면 테넌트 필수

    Returns:
        MTPaaS: MT-PaaS 통합 객체

    Example:
        ```python
        from fastapi import FastAPI
        from mt_paas import setup_multi_tenant

        app = FastAPI()

        mt = setup_multi_tenant(
            app,
            central_db_url="postgresql+asyncpg://localhost/mt_paas_central"
        )

        @app.on_event("startup")
        async def startup():
            await mt.init()

        @app.on_event("shutdown")
        async def shutdown():
            await mt.close()
        ```
    """
    # 설정 로드
    cfg = config or get_config()

    # DB URL 오버라이드
    if central_db_url:
        cfg.database.host = "custom"  # URL 직접 사용 표시
        db_url = central_db_url
    else:
        db_url = cfg.database.url

    # DatabaseManager 생성
    db_manager = DatabaseManager(db_url)

    # MTPaaS 객체 생성
    mt = MTPaaS(app, cfg, db_manager)

    # 기본 제외 경로
    default_exclude = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/mt/health",
        "/favicon.ico",
    ]

    # 미들웨어 추가
    app.add_middleware(
        TenantMiddleware,
        tenant_lookup=tenant_lookup or _create_default_lookup(mt),
        header_name=tenant_header_name,
        exclude_paths=exclude_paths or default_exclude,
        require_tenant=require_tenant,
    )

    # 앱 상태에 저장 (다른 곳에서 접근 가능하도록)
    app.state.mt_paas = mt
    app.state.tenant_manager = mt.manager
    app.state.db_manager = mt.db

    logger.info(f"MT-PaaS setup complete (API port: {cfg.ports.api_port})")
    return mt


def _create_default_lookup(mt: MTPaaS) -> Callable:
    """기본 테넌트 조회 함수 생성"""

    async def lookup(tenant_id: str) -> Optional[TenantContext]:
        try:
            tenant = await mt.manager.get_tenant(tenant_id)
            if tenant and tenant.is_active:
                # 구독 정보 조회
                async with mt.db.get_central_session() as session:
                    from sqlalchemy import select
                    from mt_paas.core.models import Subscription
                    result = await session.execute(
                        select(Subscription)
                        .where(Subscription.tenant_id == tenant_id)
                        .where(Subscription.is_active == True)
                    )
                    subscription = result.scalar_one_or_none()

                return TenantContext(
                    tenant_id=tenant.id,
                    plan=subscription.plan.value if subscription else "basic",
                    features=subscription.features if subscription else {},
                    config=tenant.config or {},
                )
        except Exception as e:
            logger.debug(f"Tenant lookup failed for {tenant_id}: {e}")
        return None

    return lookup


# 편의 함수
def get_mt_paas(app: FastAPI) -> Optional[MTPaaS]:
    """FastAPI 앱에서 MT-PaaS 객체 가져오기"""
    return getattr(app.state, "mt_paas", None)


def get_tenant_manager(app: FastAPI) -> Optional[TenantManager]:
    """FastAPI 앱에서 TenantManager 가져오기"""
    return getattr(app.state, "tenant_manager", None)
