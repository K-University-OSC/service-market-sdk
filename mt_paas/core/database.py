"""
데이터베이스 연결 및 세션 관리

Central DB와 Tenant DB 연결을 관리합니다.
"""

import os
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from .models import Base


class DatabaseManager:
    """
    데이터베이스 매니저

    Central DB와 테넌트별 DB 연결을 관리합니다.
    """

    def __init__(self, central_db_url: Optional[str] = None):
        self.central_db_url = central_db_url or os.getenv(
            "CENTRAL_DATABASE_URL",
            "postgresql+asyncpg://postgres:password@localhost:5432/central_db"
        )

        # Central DB 엔진
        self._central_engine = None
        self._central_session_factory = None

        # 테넌트 DB 엔진 캐시
        self._tenant_engines: Dict[str, Any] = {}
        self._tenant_session_factories: Dict[str, Any] = {}

    async def init_central_db(self):
        """Central DB 초기화"""
        self._central_engine = create_async_engine(
            self.central_db_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            pool_pre_ping=True,
        )

        self._central_session_factory = async_sessionmaker(
            self._central_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_central_tables(self):
        """Central DB 테이블 생성"""
        async with self._central_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def get_central_session(self):
        """Central DB 세션 획득"""
        if not self._central_session_factory:
            await self.init_central_db()

        async with self._central_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def get_tenant_db_url(self, tenant_id: str) -> str:
        """테넌트 DB URL 생성"""
        # Central DB URL에서 호스트/포트 추출
        base_url = self.central_db_url.rsplit("/", 1)[0]
        return f"{base_url}/tenant_{tenant_id}"

    async def get_tenant_engine(self, tenant_id: str):
        """테넌트 DB 엔진 획득"""
        if tenant_id not in self._tenant_engines:
            tenant_db_url = self.get_tenant_db_url(tenant_id)
            self._tenant_engines[tenant_id] = create_async_engine(
                tenant_db_url,
                echo=os.getenv("SQL_ECHO", "false").lower() == "true",
                poolclass=NullPool,  # 테넌트별로 연결 풀 관리
            )
        return self._tenant_engines[tenant_id]

    @asynccontextmanager
    async def get_tenant_session(self, tenant_id: str):
        """테넌트 DB 세션 획득"""
        if tenant_id not in self._tenant_session_factories:
            engine = await self.get_tenant_engine(tenant_id)
            self._tenant_session_factories[tenant_id] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

        async with self._tenant_session_factories[tenant_id]() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tenant_database(self, tenant_id: str):
        """
        테넌트 전용 데이터베이스 생성

        PostgreSQL에서 새 데이터베이스를 생성합니다.
        """
        import asyncpg

        # 연결 URL 파싱
        url_parts = self.central_db_url.replace("postgresql+asyncpg://", "")
        if "@" in url_parts:
            auth, host_db = url_parts.split("@")
            user, password = auth.split(":")
            host_port, _ = host_db.split("/")
            if ":" in host_port:
                host, port = host_port.split(":")
            else:
                host, port = host_port, "5432"
        else:
            user, password, host, port = "postgres", "password", "localhost", "5432"

        db_name = f"tenant_{tenant_id}"

        # 데이터베이스 생성
        conn = await asyncpg.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database="postgres",
        )

        try:
            # DB 존재 여부 확인
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                db_name
            )

            if not exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()

    async def close(self):
        """모든 연결 종료"""
        if self._central_engine:
            await self._central_engine.dispose()

        for engine in self._tenant_engines.values():
            await engine.dispose()


# 전역 인스턴스
db_manager = DatabaseManager()
