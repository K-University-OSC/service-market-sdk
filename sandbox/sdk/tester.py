"""
Webhook Tester

종합 테스트 실행기
"""

import json
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from .client import ServiceMarketClient, WebhookResponse
from .validator import WebhookValidator, ValidationResult


@dataclass
class TestReport:
    """테스트 리포트"""
    timestamp: str
    service_url: str
    total_tests: int
    passed: int
    failed: int
    score: int
    tests: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "service_url": self.service_url,
            "summary": {
                "total": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "score": self.score
            },
            "tests": self.tests
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def print_report(self):
        """콘솔에 리포트 출력"""
        print("\n" + "=" * 60)
        print("Service Market Webhook 테스트 리포트")
        print("=" * 60)
        print(f"테스트 시간: {self.timestamp}")
        print(f"서비스 URL: {self.service_url}")
        print("-" * 60)
        print(f"총 테스트: {self.total_tests}")
        print(f"통과: {self.passed}")
        print(f"실패: {self.failed}")
        print(f"점수: {self.score}/100")
        print("-" * 60)

        for test in self.tests:
            status = "PASS" if test["passed"] else "FAIL"
            print(f"[{status}] {test['name']}")
            if test.get("error"):
                print(f"      오류: {test['error']}")
            if test.get("response_time_ms"):
                print(f"      응답시간: {test['response_time_ms']:.2f}ms")

        print("=" * 60)


class WebhookTester:
    """종합 Webhook 테스터"""

    def __init__(
        self,
        service_url: str,
        api_key: str = "mt_dev_key_12345",
        webhook_path: str = "/api/tenant/webhook/auto-provision"
    ):
        self.client = ServiceMarketClient(
            service_url=service_url,
            api_key=api_key,
            webhook_path=webhook_path
        )
        self.validator = WebhookValidator()

    def run_all_tests(self) -> TestReport:
        """모든 테스트 실행"""
        tests = []
        passed = 0

        # 1. 헬스체크 테스트
        health_result = self._test_health()
        tests.append(health_result)
        if health_result["passed"]:
            passed += 1

        # 2. Webhook 기본 테스트
        webhook_result = self._test_webhook_basic()
        tests.append(webhook_result)
        if webhook_result["passed"]:
            passed += 1

        # 3. API Key 검증 테스트
        apikey_result = self._test_api_key()
        tests.append(apikey_result)
        if apikey_result["passed"]:
            passed += 1

        # 4. 응답 형식 검증
        format_result = self._test_response_format()
        tests.append(format_result)
        if format_result["passed"]:
            passed += 1

        # 5. 테넌트 재사용 테스트
        reuse_result = self._test_tenant_reuse()
        tests.append(reuse_result)
        if reuse_result["passed"]:
            passed += 1

        total = len(tests)
        score = int((passed / total) * 100)

        return TestReport(
            timestamp=datetime.now().isoformat(),
            service_url=self.client.service_url,
            total_tests=total,
            passed=passed,
            failed=total - passed,
            score=score,
            tests=tests
        )

    def _test_health(self) -> Dict[str, Any]:
        """헬스체크 테스트"""
        result = self.client.test_health()
        return {
            "name": "헬스체크 (/health)",
            "passed": result.success,
            "response_time_ms": result.response_time_ms,
            "error": result.error
        }

    def _test_webhook_basic(self) -> Dict[str, Any]:
        """Webhook 기본 호출 테스트"""
        result = self.client.test_webhook(
            application_id=9001,
            kind="demo",
            applicant_email="basic_test@test.com",
            university_name="기본테스트대학"
        )
        return {
            "name": "Webhook 기본 호출",
            "passed": result.success and result.status_code == 200,
            "response_time_ms": result.response_time_ms,
            "status_code": result.status_code,
            "error": result.error
        }

    def _test_api_key(self) -> Dict[str, Any]:
        """API Key 검증 테스트"""
        result = self.client.test_api_key_validation()
        return {
            "name": "API Key 검증 (잘못된 키 거부)",
            "passed": result.status_code == 401,
            "response_time_ms": result.response_time_ms,
            "status_code": result.status_code,
            "error": None if result.status_code == 401 else "401 응답 예상"
        }

    def _test_response_format(self) -> Dict[str, Any]:
        """응답 형식 검증"""
        result = self.client.test_webhook(
            application_id=9002,
            applicant_email="format_test@test.com"
        )

        if not result.success or not result.data:
            return {
                "name": "응답 형식 검증",
                "passed": False,
                "error": result.error or "응답 데이터 없음"
            }

        validation = self.validator.validate_response(result.data)
        return {
            "name": "응답 형식 검증",
            "passed": validation.valid,
            "score": validation.score,
            "errors": validation.errors,
            "warnings": validation.warnings
        }

    def _test_tenant_reuse(self) -> Dict[str, Any]:
        """테넌트 재사용 테스트"""
        results = self.client.test_tenant_reuse(
            email="reuse_sdk_test@test.com"
        )

        reuse_success = results.get("reuse_success", False)
        return {
            "name": "테넌트 재사용 (동일 이메일)",
            "passed": reuse_success,
            "first_tenant": results["first"].data.get("tenant_id") if results["first"].success else None,
            "second_tenant": results["second"].data.get("tenant_id") if results["second"].success else None,
            "error": None if reuse_success else "테넌트 재사용 실패"
        }
