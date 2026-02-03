"""
Service Market Simulator - Result Store

웹훅 실행 결과를 저장하고 조회합니다.
"""

from typing import Optional, List
from datetime import datetime
import json

from .database import SimulatorDatabase
from .models import WebhookResult, StatisticsResponse


class ResultStore:
    """
    웹훅 결과 저장소

    Usage:
        db = SimulatorDatabase(":memory:")
        db.init_db()

        store = ResultStore(db)

        # 결과 저장 (실제 service_market 스펙)
        result = store.save_result(
            application_id=1,
            target_url="http://localhost:8000/api/tenant/webhook/application-approved",
            request_payload={
                "application": {"id": 1000, "kind": "demo", ...},
                "applicant": {...},
                "service": {...}
            },
            response_code=200,
            response_body={"success": True, "tenant_id": "demo_1000", "access_url": "..."},
            response_time_ms=150.5
        )

        # 조회
        results = store.get_results_for_application(1)
        stats = store.get_statistics()
    """

    def __init__(self, db: SimulatorDatabase):
        self.db = db

    def save_result(
        self,
        application_id: int,
        target_url: str,
        request_payload: dict,
        response_code: Optional[int],
        response_body: Optional[dict],
        response_time_ms: float,
        api_key: str = "",
        error: Optional[str] = None
    ) -> WebhookResult:
        """
        웹훅 실행 결과 저장

        Args:
            application_id: 신청 내부 ID
            target_url: 대상 서비스 URL
            request_payload: 요청 페이로드
            response_code: HTTP 응답 코드 (실패시 None)
            response_body: 응답 본문 (실패시 None)
            response_time_ms: 응답 시간 (ms)
            api_key: 사용된 API 키
            error: 에러 메시지 (실패시)

        Returns:
            저장된 WebhookResult
        """
        success = response_code == 200 and error is None
        now = datetime.now().isoformat()

        # 응답에서 필드 파싱 (실제 service_market 스펙: success, access_url 사용)
        webhook_success = None
        tenant_id = None
        access_url = None

        if response_body and isinstance(response_body, dict):
            webhook_success = response_body.get("success")
            tenant_id = response_body.get("tenant_id")
            access_url = response_body.get("access_url")

        data = {
            "application_id": application_id,
            "target_url": target_url,
            "request_payload": json.dumps(request_payload, ensure_ascii=False),
            "api_key": api_key,
            "response_status_code": response_code,
            "response_body": json.dumps(response_body, ensure_ascii=False) if response_body else None,
            "response_time_ms": response_time_ms,
            "success": 1 if success else 0,
            "error_message": error,
            "webhook_success": 1 if webhook_success else (0 if webhook_success is False else None),
            "tenant_id": tenant_id,
            "access_url": access_url,
            "created_at": now
        }

        row_id = self.db.insert("webhook_results", data)
        return self.get_result(row_id)

    def get_result(self, id: int) -> Optional[WebhookResult]:
        """
        ID로 결과 조회

        Args:
            id: 결과 ID

        Returns:
            WebhookResult 또는 None
        """
        row = self.db.fetch_one(
            "SELECT * FROM webhook_results WHERE id = ?",
            (id,)
        )
        if row:
            return self._row_to_result(row)
        return None

    def get_results_for_application(
        self,
        application_id: int
    ) -> List[WebhookResult]:
        """
        특정 신청의 모든 결과 조회

        Args:
            application_id: 신청 내부 ID

        Returns:
            WebhookResult 리스트
        """
        rows = self.db.fetch_all(
            "SELECT * FROM webhook_results WHERE application_id = ? ORDER BY created_at DESC",
            (application_id,)
        )
        return [self._row_to_result(row) for row in rows]

    def get_latest_results(self, limit: int = 50) -> List[WebhookResult]:
        """
        최신 결과 조회

        Args:
            limit: 최대 개수

        Returns:
            WebhookResult 리스트 (최신순)
        """
        rows = self.db.fetch_all(
            "SELECT * FROM webhook_results ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_result(row) for row in rows]

    def get_successful_results(self, limit: int = 50) -> List[WebhookResult]:
        """
        성공한 결과만 조회

        Args:
            limit: 최대 개수

        Returns:
            WebhookResult 리스트
        """
        rows = self.db.fetch_all(
            "SELECT * FROM webhook_results WHERE success = 1 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_result(row) for row in rows]

    def get_failed_results(self, limit: int = 50) -> List[WebhookResult]:
        """
        실패한 결과만 조회

        Args:
            limit: 최대 개수

        Returns:
            WebhookResult 리스트
        """
        rows = self.db.fetch_all(
            "SELECT * FROM webhook_results WHERE success = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_result(row) for row in rows]

    def get_statistics(self) -> StatisticsResponse:
        """
        통계 정보 조회

        Returns:
            StatisticsResponse
        """
        # 신청 통계
        app_stats = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN kind = 'demo' THEN 1 ELSE 0 END) as demo,
                SUM(CASE WHEN kind = 'service' THEN 1 ELSE 0 END) as service,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM applications
        """)

        # 웹훅 통계
        webhook_stats = self.db.fetch_one("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
                AVG(response_time_ms) as avg_time
            FROM webhook_results
        """)

        total_webhooks = webhook_stats["total"] or 0
        successful_webhooks = webhook_stats["successful"] or 0
        success_rate = (successful_webhooks / total_webhooks * 100) if total_webhooks > 0 else 0.0

        return StatisticsResponse(
            total_applications=app_stats["total"] or 0,
            demo_applications=app_stats["demo"] or 0,
            service_applications=app_stats["service"] or 0,
            pending_applications=app_stats["pending"] or 0,
            sent_applications=app_stats["sent"] or 0,
            completed_applications=app_stats["completed"] or 0,
            failed_applications=app_stats["failed"] or 0,
            total_webhook_calls=total_webhooks,
            successful_calls=successful_webhooks,
            failed_calls=webhook_stats["failed"] or 0,
            success_rate=round(success_rate, 2),
            average_response_time_ms=round(webhook_stats["avg_time"] or 0, 2)
        )

    def delete_result(self, id: int) -> bool:
        """
        결과 삭제

        Args:
            id: 결과 ID

        Returns:
            삭제 성공 여부
        """
        affected = self.db.delete("webhook_results", "id = ?", (id,))
        return affected > 0

    def delete_results_for_application(self, application_id: int) -> int:
        """
        특정 신청의 모든 결과 삭제

        Args:
            application_id: 신청 내부 ID

        Returns:
            삭제된 결과 수
        """
        return self.db.delete(
            "webhook_results",
            "application_id = ?",
            (application_id,)
        )

    def clear_all(self) -> int:
        """
        모든 결과 삭제

        Returns:
            삭제된 결과 수
        """
        row = self.db.fetch_one("SELECT COUNT(*) as cnt FROM webhook_results")
        count = row["cnt"] if row else 0
        self.db.delete("webhook_results", "1=1")
        return count

    def _row_to_result(self, row) -> WebhookResult:
        """SQLite 행을 WebhookResult로 변환"""
        # sqlite3.Row는 .get()을 지원하지 않으므로 dict로 변환
        row_dict = dict(row)

        # webhook_success 필드 처리 (None, 0, 1)
        ws = row_dict.get("webhook_success")
        webhook_success = None if ws is None else bool(ws)

        return WebhookResult(
            id=row_dict["id"],
            application_id=row_dict["application_id"],
            target_url=row_dict["target_url"],
            request_payload=row_dict["request_payload"] or "{}",
            api_key=row_dict["api_key"] or "",
            response_status_code=row_dict["response_status_code"],
            response_body=row_dict["response_body"],
            response_time_ms=row_dict["response_time_ms"] or 0.0,
            success=bool(row_dict["success"]),
            error_message=row_dict["error_message"],
            webhook_success=webhook_success,
            tenant_id=row_dict["tenant_id"],
            access_url=row_dict.get("access_url"),
            created_at=row_dict["created_at"]
        )
