"""
Service Market Simulator - Application Manager

데모/서비스 신청의 CRUD 작업을 담당합니다.
"""

from typing import Optional, List
from datetime import datetime, date, timedelta
import random

from .database import SimulatorDatabase
from .models import Application


class ApplicationManager:
    """
    신청(Application) 관리자

    Usage:
        db = SimulatorDatabase(":memory:")
        db.init_db()

        manager = ApplicationManager(db)

        # 데모 신청 생성
        app = manager.create_demo_application(
            applicant_email="test@univ.ac.kr",
            applicant_name="Test User",
            university_name="Test University"
        )

        # 서비스 신청 생성
        app = manager.create_service_application(
            applicant_email="admin@univ.ac.kr",
            applicant_name="Admin User",
            university_name="Admin University",
            start_date="2026-02-01",
            end_date="2026-12-31"
        )

        # 조회
        app = manager.get_application(1)
        apps = manager.list_applications(kind="demo")
    """

    def __init__(self, db: SimulatorDatabase):
        self.db = db

    def create_demo_application(
        self,
        applicant_email: str,
        applicant_name: str = "Test User",
        university_name: str = "Test University",
        service_slug: str = "test-service",
        service_title: str = "Test Service"
    ) -> Application:
        """
        데모 신청 생성 (30일)

        Args:
            applicant_email: 신청자 이메일
            applicant_name: 신청자 이름
            university_name: 대학명
            service_slug: 서비스 슬러그
            service_title: 서비스 제목

        Returns:
            생성된 Application
        """
        application_id = self.db.get_next_application_id()
        now = datetime.now().isoformat()
        start = date.today().isoformat()
        end = (date.today() + timedelta(days=30)).isoformat()

        data = {
            "application_id": application_id,
            "kind": "demo",
            "status": "pending",
            "applicant_id": random.randint(1, 1000),
            "applicant_name": applicant_name,
            "applicant_email": applicant_email,
            "university_name": university_name,
            "service_id": random.randint(1, 100),
            "service_slug": service_slug,
            "service_title": service_title,
            "start_date": start,
            "end_date": end,
            "created_at": now,
            "updated_at": now
        }

        row_id = self.db.insert("applications", data)
        return self.get_application(row_id)

    def create_service_application(
        self,
        applicant_email: str,
        applicant_name: str,
        university_name: str,
        start_date: str,
        end_date: str,
        service_slug: str = "test-service",
        service_title: str = "Test Service"
    ) -> Application:
        """
        서비스 신청 생성 (커스텀 기간)

        Args:
            applicant_email: 신청자 이메일
            applicant_name: 신청자 이름
            university_name: 대학명
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
            service_slug: 서비스 슬러그
            service_title: 서비스 제목

        Returns:
            생성된 Application
        """
        application_id = self.db.get_next_application_id()
        now = datetime.now().isoformat()

        data = {
            "application_id": application_id,
            "kind": "service",
            "status": "pending",
            "applicant_id": random.randint(1, 1000),
            "applicant_name": applicant_name,
            "applicant_email": applicant_email,
            "university_name": university_name,
            "service_id": random.randint(1, 100),
            "service_slug": service_slug,
            "service_title": service_title,
            "start_date": start_date,
            "end_date": end_date,
            "created_at": now,
            "updated_at": now
        }

        row_id = self.db.insert("applications", data)
        return self.get_application(row_id)

    def get_application(self, id: int) -> Optional[Application]:
        """
        ID로 신청 조회

        Args:
            id: 내부 ID (application_id가 아님)

        Returns:
            Application 또는 None
        """
        row = self.db.fetch_one(
            "SELECT * FROM applications WHERE id = ?",
            (id,)
        )
        if row:
            return self._row_to_application(row)
        return None

    def get_by_application_id(self, application_id: int) -> Optional[Application]:
        """
        application_id로 신청 조회

        Args:
            application_id: 외부 신청 ID

        Returns:
            Application 또는 None
        """
        row = self.db.fetch_one(
            "SELECT * FROM applications WHERE application_id = ?",
            (application_id,)
        )
        if row:
            return self._row_to_application(row)
        return None

    def list_applications(
        self,
        kind: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Application]:
        """
        신청 목록 조회

        Args:
            kind: 필터 - "demo" 또는 "service"
            status: 필터 - "pending", "sent", "completed", "failed"
            limit: 최대 개수
            offset: 시작 위치

        Returns:
            Application 리스트
        """
        sql = "SELECT * FROM applications WHERE 1=1"
        params = []

        if kind:
            sql += " AND kind = ?"
            params.append(kind)

        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.db.fetch_all(sql, tuple(params))
        return [self._row_to_application(row) for row in rows]

    def update_status(
        self,
        id: int,
        status: str
    ) -> Optional[Application]:
        """
        신청 상태 업데이트

        Args:
            id: 내부 ID
            status: 새 상태

        Returns:
            업데이트된 Application 또는 None
        """
        now = datetime.now().isoformat()
        affected = self.db.update(
            "applications",
            {"status": status, "updated_at": now},
            "id = ?",
            (id,)
        )
        if affected > 0:
            return self.get_application(id)
        return None

    def delete_application(self, id: int) -> bool:
        """
        신청 삭제

        Args:
            id: 내부 ID

        Returns:
            삭제 성공 여부
        """
        affected = self.db.delete("applications", "id = ?", (id,))
        return affected > 0

    def count_applications(
        self,
        kind: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """
        신청 개수 조회

        Args:
            kind: 필터 - "demo" 또는 "service"
            status: 필터

        Returns:
            신청 개수
        """
        sql = "SELECT COUNT(*) as cnt FROM applications WHERE 1=1"
        params = []

        if kind:
            sql += " AND kind = ?"
            params.append(kind)

        if status:
            sql += " AND status = ?"
            params.append(status)

        row = self.db.fetch_one(sql, tuple(params))
        return row["cnt"] if row else 0

    def _row_to_application(self, row) -> Application:
        """SQLite 행을 Application으로 변환"""
        return Application(
            id=row["id"],
            application_id=row["application_id"],
            kind=row["kind"],
            status=row["status"],
            applicant_id=row["applicant_id"],
            applicant_name=row["applicant_name"],
            applicant_email=row["applicant_email"],
            university_name=row["university_name"],
            service_id=row["service_id"],
            service_slug=row["service_slug"],
            service_title=row["service_title"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
