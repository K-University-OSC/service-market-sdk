"""
Service Market Client

Service Market API와 통신하는 클라이언트
"""

import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WebhookResponse:
    """Webhook 응답 결과"""
    success: bool
    status_code: int
    response_time_ms: float
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ServiceMarketClient:
    """Service Market API 클라이언트"""

    def __init__(
        self,
        service_url: str,
        api_key: str = "mt_dev_key_12345",
        webhook_path: str = "/api/tenant/webhook/auto-provision",
        timeout: float = 30.0
    ):
        """
        Args:
            service_url: AI 서비스의 기본 URL (예: http://localhost:8000)
            api_key: API Key
            webhook_path: Webhook 엔드포인트 경로
            timeout: 요청 타임아웃 (초)
        """
        self.service_url = service_url.rstrip("/")
        self.api_key = api_key
        self.webhook_path = webhook_path
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더 생성"""
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

    def test_health(self) -> WebhookResponse:
        """헬스체크 테스트"""
        start = datetime.now()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.service_url}/health"
                )
                elapsed = (datetime.now() - start).total_seconds() * 1000

                return WebhookResponse(
                    success=response.status_code == 200,
                    status_code=response.status_code,
                    response_time_ms=elapsed,
                    data=response.json() if response.status_code == 200 else None,
                    error=None if response.status_code == 200 else response.text
                )
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return WebhookResponse(
                success=False,
                status_code=0,
                response_time_ms=elapsed,
                error=str(e)
            )

    def test_webhook(
        self,
        application_id: int = 999,
        kind: str = "demo",
        applicant_email: str = "test@university.ac.kr",
        applicant_name: str = "테스트",
        university_name: str = "테스트대학교",
        service_id: int = 1,
        service_slug: str = "test-service",
        service_title: str = "Test Service",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> WebhookResponse:
        """
        Webhook 테스트

        Service Market이 보내는 것과 동일한 페이로드로 Webhook을 호출합니다.
        """
        payload = {
            "application_id": application_id,
            "kind": kind,
            "contact": "02-000-0000",
            "reason": "SDK 테스트",
            "applicant": {
                "id": 1,
                "name": applicant_name,
                "email": applicant_email,
                "university_name": university_name
            },
            "service": {
                "id": service_id,
                "slug": service_slug,
                "title": service_title
            }
        }

        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        start = datetime.now()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.service_url}{self.webhook_path}",
                    json=payload,
                    headers=self._get_headers()
                )
                elapsed = (datetime.now() - start).total_seconds() * 1000

                return WebhookResponse(
                    success=response.status_code == 200,
                    status_code=response.status_code,
                    response_time_ms=elapsed,
                    data=response.json() if response.status_code == 200 else None,
                    error=None if response.status_code == 200 else response.text
                )
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds() * 1000
            return WebhookResponse(
                success=False,
                status_code=0,
                response_time_ms=elapsed,
                error=str(e)
            )

    def test_api_key_validation(self) -> WebhookResponse:
        """잘못된 API Key로 테스트 (401 예상)"""
        original_key = self.api_key
        self.api_key = "invalid_key"

        result = self.test_webhook(application_id=998)

        self.api_key = original_key

        # 401이면 성공 (API Key 검증이 작동함)
        result.success = result.status_code == 401
        return result

    def test_tenant_reuse(self, email: str = "reuse_test@university.ac.kr") -> Dict[str, WebhookResponse]:
        """테넌트 재사용 테스트"""
        results = {}

        # 첫 번째 신청
        results["first"] = self.test_webhook(
            application_id=1001,
            kind="demo",
            applicant_email=email,
            university_name="재사용테스트대학"
        )

        # 두 번째 신청 (같은 이메일)
        results["second"] = self.test_webhook(
            application_id=1002,
            kind="service",
            applicant_email=email,
            university_name="재사용테스트대학"
        )

        # 테넌트 ID가 같으면 재사용 성공
        if results["first"].success and results["second"].success:
            first_tenant = results["first"].data.get("tenant_id")
            second_tenant = results["second"].data.get("tenant_id")
            results["reuse_success"] = first_tenant == second_tenant
        else:
            results["reuse_success"] = False

        return results

    def test_all(self) -> Dict[str, Any]:
        """모든 테스트 실행"""
        results = {
            "health": self.test_health(),
            "webhook": self.test_webhook(),
            "api_key_validation": self.test_api_key_validation(),
            "tenant_reuse": self.test_tenant_reuse()
        }

        # 요약
        passed = sum([
            results["health"].success,
            results["webhook"].success,
            results["api_key_validation"].success,
            results["tenant_reuse"].get("reuse_success", False) if isinstance(results["tenant_reuse"], dict) else False
        ])

        results["summary"] = {
            "total": 4,
            "passed": passed,
            "failed": 4 - passed,
            "score": f"{passed}/4 ({passed * 25}%)"
        }

        return results
