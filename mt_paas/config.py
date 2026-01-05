"""
MT-PaaS 설정

포트, 데이터베이스 등 설정 관리
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = ""
    database: str = "mt_paas_central"

    # Connection Pool
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800

    @property
    def url(self) -> str:
        """SQLAlchemy 연결 URL"""
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def sync_url(self) -> str:
        """동기 연결 URL"""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """환경변수에서 설정 로드"""
        return cls(
            host=os.getenv("MT_DB_HOST", "localhost"),
            port=int(os.getenv("MT_DB_PORT", "5432")),
            username=os.getenv("MT_DB_USER", "postgres"),
            password=os.getenv("MT_DB_PASSWORD", ""),
            database=os.getenv("MT_DB_NAME", "mt_paas_central"),
            pool_size=int(os.getenv("MT_DB_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("MT_DB_MAX_OVERFLOW", "10")),
        )


@dataclass
class RedisConfig:
    """Redis 설정"""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0

    @property
    def url(self) -> str:
        """Redis 연결 URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"

    @classmethod
    def from_env(cls) -> "RedisConfig":
        """환경변수에서 설정 로드"""
        return cls(
            host=os.getenv("MT_REDIS_HOST", "localhost"),
            port=int(os.getenv("MT_REDIS_PORT", "6379")),
            password=os.getenv("MT_REDIS_PASSWORD"),
            db=int(os.getenv("MT_REDIS_DB", "0")),
        )


@dataclass
class PortConfig:
    """포트 설정 (11000-12000 범위 사용)"""

    # 서비스 포트
    api_port: int = 11000           # MT-PaaS API 서버
    admin_port: int = 11001         # 관리자 대시보드

    # 테넌트 서비스용 포트 범위
    tenant_port_start: int = 11100  # 테넌트 서비스 시작 포트
    tenant_port_end: int = 11999    # 테넌트 서비스 종료 포트

    # 포트당 할당 간격 (테넌트별 여러 포트 필요시)
    ports_per_tenant: int = 5

    @property
    def max_tenants(self) -> int:
        """최대 테넌트 수"""
        available = self.tenant_port_end - self.tenant_port_start
        return available // self.ports_per_tenant

    def get_tenant_ports(self, tenant_index: int) -> tuple:
        """테넌트별 포트 범위 반환"""
        start = self.tenant_port_start + (tenant_index * self.ports_per_tenant)
        end = start + self.ports_per_tenant - 1

        if end > self.tenant_port_end:
            raise ValueError(f"Port range exceeded. Max tenants: {self.max_tenants}")

        return (start, end)

    @classmethod
    def from_env(cls) -> "PortConfig":
        """환경변수에서 설정 로드"""
        return cls(
            api_port=int(os.getenv("MT_API_PORT", "11000")),
            admin_port=int(os.getenv("MT_ADMIN_PORT", "11001")),
            tenant_port_start=int(os.getenv("MT_TENANT_PORT_START", "11100")),
            tenant_port_end=int(os.getenv("MT_TENANT_PORT_END", "11999")),
            ports_per_tenant=int(os.getenv("MT_PORTS_PER_TENANT", "5")),
        )


@dataclass
class MTPaaSConfig:
    """MT-PaaS 전체 설정"""

    # 서비스 정보
    service_name: str = "mt_paas"
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    # 하위 설정
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    ports: PortConfig = field(default_factory=PortConfig)

    # 보안
    api_key: Optional[str] = None
    jwt_secret: Optional[str] = None

    # 제한
    default_max_users: int = 50
    default_max_storage_mb: int = 1000
    default_max_api_calls: int = 1000

    @classmethod
    def from_env(cls) -> "MTPaaSConfig":
        """환경변수에서 전체 설정 로드"""
        return cls(
            service_name=os.getenv("MT_SERVICE_NAME", "mt_paas"),
            version=os.getenv("MT_VERSION", "0.1.0"),
            environment=os.getenv("MT_ENVIRONMENT", "development"),
            debug=os.getenv("MT_DEBUG", "true").lower() == "true",
            database=DatabaseConfig.from_env(),
            redis=RedisConfig.from_env(),
            ports=PortConfig.from_env(),
            api_key=os.getenv("MARKET_API_KEY"),
            jwt_secret=os.getenv("MT_JWT_SECRET"),
            default_max_users=int(os.getenv("MT_DEFAULT_MAX_USERS", "50")),
            default_max_storage_mb=int(os.getenv("MT_DEFAULT_MAX_STORAGE_MB", "1000")),
            default_max_api_calls=int(os.getenv("MT_DEFAULT_MAX_API_CALLS", "1000")),
        )


# 전역 설정 인스턴스
_config: Optional[MTPaaSConfig] = None


def get_config() -> MTPaaSConfig:
    """전역 설정 반환"""
    global _config
    if _config is None:
        _config = MTPaaSConfig.from_env()
    return _config


def set_config(config: MTPaaSConfig) -> None:
    """전역 설정 지정"""
    global _config
    _config = config


# 포트 정보 상수 (11000-12000 범위)
class Ports:
    """MT-PaaS 포트 할당 (11000-12000)"""

    # Core 서비스
    MT_PAAS_API = 11000          # MT-PaaS 메인 API
    MT_PAAS_ADMIN = 11001        # MT-PaaS 관리자 UI

    # Service Market
    SERVICE_MARKET_API = 11010   # Service Market API
    SERVICE_MARKET_WEB = 11011   # Service Market Web UI

    # 개별 서비스 (예시)
    KELI_TUTOR_BASE = 11100      # KELI Tutor 시작 포트

    # 테넌트 동적 할당 범위
    TENANT_RANGE_START = 11200
    TENANT_RANGE_END = 11999
