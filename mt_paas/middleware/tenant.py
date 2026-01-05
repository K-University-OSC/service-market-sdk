"""
테넌트 컨텍스트 미들웨어

요청별로 테넌트를 식별하고 컨텍스트에 저장합니다.
"""

from contextvars import ContextVar
from typing import Optional, Callable, Any
from dataclasses import dataclass
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# 현재 요청의 테넌트 컨텍스트
_current_tenant: ContextVar[Optional["TenantContext"]] = ContextVar(
    "current_tenant", default=None
)


@dataclass
class TenantContext:
    """테넌트 컨텍스트 정보"""
    tenant_id: str
    plan: str = "basic"
    features: dict = None
    config: dict = None

    def __post_init__(self):
        if self.features is None:
            self.features = {}
        if self.config is None:
            self.config = {}

    def has_feature(self, feature: str) -> bool:
        """특정 기능 활성화 여부"""
        return self.features.get(feature, False)


def get_current_tenant() -> Optional[TenantContext]:
    """현재 요청의 테넌트 컨텍스트 반환"""
    return _current_tenant.get()


def get_tenant_id() -> Optional[str]:
    """현재 테넌트 ID 반환"""
    ctx = _current_tenant.get()
    return ctx.tenant_id if ctx else None


def set_current_tenant(context: TenantContext) -> None:
    """테넌트 컨텍스트 설정"""
    _current_tenant.set(context)


def clear_current_tenant() -> None:
    """테넌트 컨텍스트 초기화"""
    _current_tenant.set(None)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    테넌트 식별 미들웨어

    요청에서 테넌트를 식별하여 컨텍스트에 저장합니다.

    식별 방법 (우선순위):
    1. X-Tenant-ID 헤더
    2. URL 경로 (/tenant/{tenant_id}/...)
    3. 서브도메인 ({tenant_id}.service.com)

    Example:
        from fastapi import FastAPI
        from mt_paas.middleware import TenantMiddleware

        app = FastAPI()
        app.add_middleware(
            TenantMiddleware,
            tenant_lookup=my_lookup_function,
            exclude_paths=["/health", "/docs"]
        )
    """

    def __init__(
        self,
        app,
        tenant_lookup: Optional[Callable[[str], Any]] = None,
        header_name: str = "X-Tenant-ID",
        path_prefix: str = "/tenant/",
        exclude_paths: list = None,
        require_tenant: bool = False,
    ):
        """
        Args:
            app: FastAPI/Starlette 앱
            tenant_lookup: 테넌트 ID로 테넌트 정보 조회 함수 (async)
            header_name: 테넌트 ID 헤더 이름
            path_prefix: URL 경로에서 테넌트 ID 추출 시 prefix
            exclude_paths: 테넌트 검증 제외 경로
            require_tenant: True일 경우 테넌트 없으면 401 에러
        """
        super().__init__(app)
        self.tenant_lookup = tenant_lookup
        self.header_name = header_name
        self.path_prefix = path_prefix
        self.exclude_paths = exclude_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/mt/health",
        ]
        self.require_tenant = require_tenant

    async def dispatch(self, request: Request, call_next) -> Response:
        # 제외 경로 확인
        path = request.url.path
        if any(path.startswith(exc) for exc in self.exclude_paths):
            return await call_next(request)

        # 테넌트 ID 추출
        tenant_id = await self._extract_tenant_id(request)

        if tenant_id:
            # 테넌트 컨텍스트 생성
            context = await self._create_context(tenant_id)
            if context:
                set_current_tenant(context)
        elif self.require_tenant:
            raise HTTPException(
                status_code=401,
                detail="Tenant identification required"
            )

        try:
            response = await call_next(request)
            return response
        finally:
            # 요청 완료 후 컨텍스트 정리
            clear_current_tenant()

    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """요청에서 테넌트 ID 추출"""

        # 1. 헤더에서 추출
        tenant_id = request.headers.get(self.header_name)
        if tenant_id:
            return tenant_id

        # 2. URL 경로에서 추출 (예: /tenant/hallym_univ/...)
        path = request.url.path
        if self.path_prefix and path.startswith(self.path_prefix):
            parts = path[len(self.path_prefix):].split("/")
            if parts:
                return parts[0]

        # 3. 쿼리 파라미터에서 추출
        tenant_id = request.query_params.get("tenant_id")
        if tenant_id:
            return tenant_id

        # 4. 서브도메인에서 추출
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            # localhost, www 등은 제외
            if subdomain not in ["localhost", "www", "api", "127"]:
                return subdomain

        return None

    async def _create_context(self, tenant_id: str) -> Optional[TenantContext]:
        """테넌트 컨텍스트 생성"""

        if self.tenant_lookup:
            # 커스텀 조회 함수 사용
            tenant_info = await self.tenant_lookup(tenant_id)
            if tenant_info:
                return TenantContext(
                    tenant_id=tenant_id,
                    plan=getattr(tenant_info, "plan", "basic"),
                    features=getattr(tenant_info, "features", {}),
                    config=getattr(tenant_info, "config", {}),
                )
            return None

        # 기본: 단순 컨텍스트 생성
        return TenantContext(tenant_id=tenant_id)


# FastAPI Dependency로 사용
from fastapi import Depends

def require_tenant() -> TenantContext:
    """
    FastAPI 의존성: 테넌트 필수

    Example:
        @app.get("/data")
        async def get_data(tenant: TenantContext = Depends(require_tenant)):
            return {"tenant_id": tenant.tenant_id}
    """
    ctx = get_current_tenant()
    if not ctx:
        raise HTTPException(
            status_code=401,
            detail="Tenant context required"
        )
    return ctx


def optional_tenant() -> Optional[TenantContext]:
    """
    FastAPI 의존성: 테넌트 선택적

    Example:
        @app.get("/public")
        async def get_public(tenant: Optional[TenantContext] = Depends(optional_tenant)):
            if tenant:
                return {"message": f"Hello {tenant.tenant_id}"}
            return {"message": "Hello guest"}
    """
    return get_current_tenant()
