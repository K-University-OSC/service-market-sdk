"""
Webhook Validator

Webhook 응답이 Service Market 규격에 맞는지 검증
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """검증 결과"""
    valid: bool
    score: int  # 0-100
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


class WebhookValidator:
    """Webhook 응답 검증기"""

    REQUIRED_FIELDS = ["status", "tenant_id", "tenant_url", "message"]
    OPTIONAL_FIELDS = ["expires_at"]
    VALID_STATUSES = ["approved", "processing", "rejected", "error"]

    def validate_response(self, response: Dict[str, Any]) -> ValidationResult:
        """
        Webhook 응답 검증

        Args:
            response: Webhook 응답 데이터

        Returns:
            ValidationResult: 검증 결과
        """
        errors = []
        warnings = []
        details = {}
        score = 100

        # 1. 필수 필드 검증
        for field in self.REQUIRED_FIELDS:
            if field not in response:
                errors.append(f"필수 필드 누락: {field}")
                score -= 25
            else:
                details[field] = "OK"

        # 2. status 값 검증
        status = response.get("status")
        if status and status not in self.VALID_STATUSES:
            errors.append(f"잘못된 status 값: {status} (허용: {self.VALID_STATUSES})")
            score -= 10

        # 3. tenant_id 형식 검증
        tenant_id = response.get("tenant_id")
        if tenant_id:
            if not isinstance(tenant_id, str):
                errors.append("tenant_id는 문자열이어야 합니다")
                score -= 10
            elif len(tenant_id) > 50:
                warnings.append("tenant_id가 50자를 초과합니다")
                score -= 5

        # 4. tenant_url 검증
        tenant_url = response.get("tenant_url")
        if tenant_url:
            if not tenant_url.startswith(("http://", "https://")):
                errors.append("tenant_url은 http:// 또는 https://로 시작해야 합니다")
                score -= 10

        # 5. expires_at 형식 검증 (선택)
        expires_at = response.get("expires_at")
        if expires_at:
            try:
                from datetime import datetime
                # ISO 8601 형식 검증
                datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                details["expires_at"] = "OK"
            except ValueError:
                warnings.append("expires_at이 ISO 8601 형식이 아닙니다")
                score -= 5

        # 6. error 상태일 때 추가 검증
        if status == "error":
            if response.get("tenant_id") is not None and response.get("tenant_id") != "":
                warnings.append("error 상태에서는 tenant_id가 null이어야 합니다")

        score = max(0, score)

        return ValidationResult(
            valid=len(errors) == 0,
            score=score,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_payload(self, payload: Dict[str, Any]) -> ValidationResult:
        """
        Webhook 요청 페이로드 검증 (Service Market이 보내는 형식)

        개발 업체가 테스트 페이로드를 만들 때 사용
        """
        errors = []
        warnings = []
        details = {}
        score = 100

        # 필수 필드
        required = {
            "application_id": int,
            "kind": str,
            "applicant": dict,
            "service": dict
        }

        for field, expected_type in required.items():
            if field not in payload:
                errors.append(f"필수 필드 누락: {field}")
                score -= 20
            elif not isinstance(payload[field], expected_type):
                errors.append(f"{field}의 타입이 잘못됨 (예상: {expected_type.__name__})")
                score -= 10

        # applicant 하위 필드
        applicant = payload.get("applicant", {})
        applicant_required = ["id", "name", "email", "university_name"]
        for field in applicant_required:
            if field not in applicant:
                errors.append(f"applicant.{field} 누락")
                score -= 5

        # service 하위 필드
        service = payload.get("service", {})
        service_required = ["id", "slug", "title"]
        for field in service_required:
            if field not in service:
                errors.append(f"service.{field} 누락")
                score -= 5

        # kind 값 검증
        kind = payload.get("kind")
        if kind and kind not in ["demo", "service"]:
            errors.append(f"kind는 'demo' 또는 'service'이어야 합니다: {kind}")
            score -= 10

        score = max(0, score)

        return ValidationResult(
            valid=len(errors) == 0,
            score=score,
            errors=errors,
            warnings=warnings,
            details=details
        )
