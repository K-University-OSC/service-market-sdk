"""
Service Market Simulator - Data Models

SQLAlchemy 모델과 Pydantic 스키마를 정의합니다.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Literal, Any
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel, Field
import json


# ============================================================================
# Pydantic Request/Response Models
# ============================================================================

class ApplicantInfo(BaseModel):
    """신청자 정보"""
    id: int = Field(default=1)
    name: str = Field(default="Test User")
    email: str
    university_name: str


class ServiceInfo(BaseModel):
    """서비스 정보"""
    id: int = Field(default=1)
    slug: str = Field(default="test-service")
    title: str = Field(default="Test Service")


class DemoApplicationRequest(BaseModel):
    """데모 신청 요청"""
    applicant_email: str
    applicant_name: str = "Test User"
    university_name: str = "Test University"
    service_slug: str = "test-service"
    service_title: str = "Test Service"


class ServiceApplicationRequest(BaseModel):
    """서비스 신청 요청"""
    applicant_email: str
    applicant_name: str
    university_name: str
    service_slug: str = "test-service"
    service_title: str = "Test Service"
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD


class ApplicationCreate(BaseModel):
    """신청 생성 (내부용)"""
    kind: Literal["demo", "service"]
    applicant: ApplicantInfo
    service: ServiceInfo
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class WebhookResponseModel(BaseModel):
    """
    웹훅 응답 (멀티 테넌트 서비스에서 반환)

    실제 service_market 스펙에 맞춘 포맷
    """
    success: bool
    tenant_id: Optional[str] = None
    message: str
    access_url: Optional[str] = None
    admin_credentials: Optional[dict] = None
    created_at: Optional[str] = None


class ApplicationResponse(BaseModel):
    """신청 응답"""
    id: int
    application_id: int
    kind: str
    status: str
    applicant_email: str
    applicant_name: str
    university_name: str
    service_slug: str
    service_title: str
    start_date: str
    end_date: str
    created_at: str
    updated_at: str


class WebhookResultResponse(BaseModel):
    """웹훅 결과 응답"""
    id: int
    application_id: int
    target_url: str
    request_payload: dict
    response_status_code: Optional[int]
    response_body: Optional[dict]
    response_time_ms: float
    success: bool
    error_message: Optional[str]
    webhook_success: Optional[bool]  # 실제 service_market 응답의 success 필드
    tenant_id: Optional[str]
    access_url: Optional[str]  # tenant_url -> access_url로 변경
    created_at: str


class StatisticsResponse(BaseModel):
    """통계 응답"""
    total_applications: int
    demo_applications: int
    service_applications: int
    pending_applications: int
    sent_applications: int
    completed_applications: int
    failed_applications: int
    total_webhook_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    average_response_time_ms: float


# ============================================================================
# Dataclass Models (for SQLite storage)
# ============================================================================

@dataclass
class Application:
    """신청 데이터 모델"""
    id: int = 0
    application_id: int = 0
    kind: str = "demo"  # "demo" or "service"
    status: str = "pending"  # "pending", "sent", "completed", "failed"

    # 신청자 정보
    applicant_id: int = 1
    applicant_name: str = ""
    applicant_email: str = ""
    university_name: str = ""

    # 서비스 정보
    service_id: int = 1
    service_slug: str = "test-service"
    service_title: str = "Test Service"

    # 기간
    start_date: str = ""
    end_date: str = ""

    # 타임스탬프
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if not self.start_date:
            self.start_date = date.today().isoformat()
        if not self.end_date:
            if self.kind == "demo":
                self.end_date = (date.today() + timedelta(days=30)).isoformat()
            else:
                self.end_date = (date.today() + timedelta(days=365)).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_webhook_payload(self, contact: str = "", reason: str = "") -> dict:
        """
        웹훅 페이로드로 변환

        실제 service_market 스펙에 맞춘 포맷:
        - application 객체 안에 id, kind, contact, reason 포함
        - applicant, service는 별도 객체
        """
        if not contact:
            contact = f"02-{1000 + self.application_id % 9000}-{1000 + (self.application_id * 7) % 9000}"
        if not reason:
            reason = f"{self.university_name} {self.kind} 신청"

        return {
            "application": {
                "id": self.application_id,
                "kind": self.kind,
                "contact": contact,
                "reason": reason
            },
            "applicant": {
                "id": self.applicant_id,
                "name": self.applicant_name,
                "email": self.applicant_email,
                "university_name": self.university_name
            },
            "service": {
                "id": self.service_id,
                "slug": self.service_slug,
                "title": self.service_title
            }
        }

    def to_response(self) -> ApplicationResponse:
        """API 응답으로 변환"""
        return ApplicationResponse(
            id=self.id,
            application_id=self.application_id,
            kind=self.kind,
            status=self.status,
            applicant_email=self.applicant_email,
            applicant_name=self.applicant_name,
            university_name=self.university_name,
            service_slug=self.service_slug,
            service_title=self.service_title,
            start_date=self.start_date,
            end_date=self.end_date,
            created_at=self.created_at,
            updated_at=self.updated_at
        )


@dataclass
class WebhookResult:
    """웹훅 결과 데이터 모델"""
    id: int = 0
    application_id: int = 0

    # 요청 정보
    target_url: str = ""
    request_payload: str = "{}"  # JSON string
    api_key: str = ""

    # 응답 정보
    response_status_code: Optional[int] = None
    response_body: str = "{}"  # JSON string
    response_time_ms: float = 0.0

    # 상태
    success: bool = False
    error_message: Optional[str] = None

    # 파싱된 응답 필드 (실제 service_market 스펙)
    webhook_success: Optional[bool] = None  # success 필드
    tenant_id: Optional[str] = None
    access_url: Optional[str] = None

    # 타임스탬프
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    def get_request_payload(self) -> dict:
        """요청 페이로드를 dict로 반환"""
        try:
            return json.loads(self.request_payload)
        except:
            return {}

    def get_response_body(self) -> Optional[dict]:
        """응답 본문을 dict로 반환"""
        try:
            return json.loads(self.response_body) if self.response_body else None
        except:
            return None

    def to_response(self) -> WebhookResultResponse:
        """API 응답으로 변환"""
        return WebhookResultResponse(
            id=self.id,
            application_id=self.application_id,
            target_url=self.target_url,
            request_payload=self.get_request_payload(),
            response_status_code=self.response_status_code,
            response_body=self.get_response_body(),
            response_time_ms=self.response_time_ms,
            success=self.success,
            error_message=self.error_message,
            webhook_success=self.webhook_success,
            tenant_id=self.tenant_id,
            access_url=self.access_url,
            created_at=self.created_at
        )
