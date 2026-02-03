"""
Service Market Simulator - Database Manager

SQLite 데이터베이스 연결 및 테이블 관리를 담당합니다.
"""

import sqlite3
from typing import Optional, List, Any, Tuple
from contextlib import contextmanager
from pathlib import Path
import threading
import logging

logger = logging.getLogger(__name__)


# SQL Statements
CREATE_APPLICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER UNIQUE NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('demo', 'service')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sent', 'completed', 'failed')),

    -- 신청자 정보
    applicant_id INTEGER NOT NULL DEFAULT 1,
    applicant_name TEXT NOT NULL,
    applicant_email TEXT NOT NULL,
    university_name TEXT NOT NULL,

    -- 서비스 정보
    service_id INTEGER NOT NULL DEFAULT 1,
    service_slug TEXT NOT NULL DEFAULT 'test-service',
    service_title TEXT NOT NULL DEFAULT 'Test Service',

    -- 기간
    start_date TEXT,
    end_date TEXT,

    -- 타임스탬프
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_WEBHOOK_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS webhook_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,

    -- 요청 정보
    target_url TEXT NOT NULL,
    request_payload TEXT NOT NULL,
    api_key TEXT,

    -- 응답 정보
    response_status_code INTEGER,
    response_body TEXT,
    response_time_ms REAL,

    -- 상태
    success INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,

    -- 파싱된 응답 필드 (실제 service_market 스펙)
    webhook_success INTEGER,  -- success 필드 (1=true, 0=false, NULL=없음)
    tenant_id TEXT,
    access_url TEXT,  -- tenant_url -> access_url로 변경

    -- 타임스탬프
    created_at TEXT NOT NULL,

    FOREIGN KEY (application_id) REFERENCES applications(id)
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_applications_kind ON applications(kind);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
CREATE INDEX IF NOT EXISTS idx_applications_email ON applications(applicant_email);
CREATE INDEX IF NOT EXISTS idx_applications_app_id ON applications(application_id);
CREATE INDEX IF NOT EXISTS idx_results_application ON webhook_results(application_id);
CREATE INDEX IF NOT EXISTS idx_results_success ON webhook_results(success);
CREATE INDEX IF NOT EXISTS idx_results_created ON webhook_results(created_at);
"""


class SimulatorDatabase:
    """
    SQLite 데이터베이스 매니저

    Usage:
        # 파일 DB
        db = SimulatorDatabase("simulator.db")
        db.init_db()

        # 인메모리 DB (테스트용)
        db = SimulatorDatabase(":memory:")
        db.init_db()

        # Context manager 사용
        with db.connection() as conn:
            cursor = conn.execute("SELECT * FROM applications")
            rows = cursor.fetchall()
    """

    def __init__(self, db_path: str = "simulator.db"):
        """
        Args:
            db_path: 데이터베이스 경로. ":memory:"면 인메모리 DB
        """
        self.db_path = db_path
        self._local = threading.local()
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """스레드별 연결 반환"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    @contextmanager
    def connection(self):
        """연결 컨텍스트 매니저"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def init_db(self) -> None:
        """테이블 및 인덱스 생성"""
        if self._initialized and self.db_path != ":memory:":
            return

        with self.connection() as conn:
            conn.execute(CREATE_APPLICATIONS_TABLE)
            conn.execute(CREATE_WEBHOOK_RESULTS_TABLE)
            conn.executescript(CREATE_INDEXES)

        self._initialized = True
        logger.info(f"Database initialized: {self.db_path}")

    def close(self) -> None:
        """연결 종료"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def execute(
        self,
        sql: str,
        params: Tuple = ()
    ) -> sqlite3.Cursor:
        """SQL 실행"""
        with self.connection() as conn:
            return conn.execute(sql, params)

    def execute_many(
        self,
        sql: str,
        params_list: List[Tuple]
    ) -> sqlite3.Cursor:
        """여러 SQL 실행"""
        with self.connection() as conn:
            return conn.executemany(sql, params_list)

    def fetch_one(
        self,
        sql: str,
        params: Tuple = ()
    ) -> Optional[sqlite3.Row]:
        """단일 행 조회"""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(
        self,
        sql: str,
        params: Tuple = ()
    ) -> List[sqlite3.Row]:
        """전체 행 조회"""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def insert(
        self,
        table: str,
        data: dict
    ) -> int:
        """데이터 삽입 및 ID 반환"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        with self.connection() as conn:
            cursor = conn.execute(sql, tuple(data.values()))
            return cursor.lastrowid

    def update(
        self,
        table: str,
        data: dict,
        where: str,
        where_params: Tuple = ()
    ) -> int:
        """데이터 업데이트 및 영향받은 행 수 반환"""
        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"

        with self.connection() as conn:
            cursor = conn.execute(sql, tuple(data.values()) + where_params)
            return cursor.rowcount

    def delete(
        self,
        table: str,
        where: str,
        where_params: Tuple = ()
    ) -> int:
        """데이터 삭제 및 영향받은 행 수 반환"""
        sql = f"DELETE FROM {table} WHERE {where}"

        with self.connection() as conn:
            cursor = conn.execute(sql, where_params)
            return cursor.rowcount

    def get_next_application_id(self) -> int:
        """다음 application_id 생성"""
        row = self.fetch_one(
            "SELECT MAX(application_id) as max_id FROM applications"
        )
        if row and row["max_id"]:
            return row["max_id"] + 1
        return 1000  # 시작 ID

    def clear_all(self) -> None:
        """모든 데이터 삭제 (테스트용)"""
        with self.connection() as conn:
            conn.execute("DELETE FROM webhook_results")
            conn.execute("DELETE FROM applications")
        logger.info("All data cleared")


def get_database(db_path: str = ":memory:") -> SimulatorDatabase:
    """
    데이터베이스 인스턴스 생성 팩토리

    Args:
        db_path: 데이터베이스 경로. 기본값은 인메모리.

    Returns:
        초기화된 SimulatorDatabase 인스턴스
    """
    db = SimulatorDatabase(db_path)
    db.init_db()
    return db
