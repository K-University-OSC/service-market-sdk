"""
표준 API v2 요청/응답 모델

기존 모델 + 대시보드/사용자관리/리소스 API 모델 확장
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum

# 기존 모델 재사용
from .models import (
    HealthResponse,
    ContactInfo,
    ActivateRequest,
    ActivateResponse,
    DeactivateRequest,
    DeactivateResponse,
    StatusResponse,
    UsageData,
    UsageResponse,
    ErrorResponse,
    ErrorCodes,
)


# =============================================================================
# Dashboard Stats API (신규)
# =============================================================================

class StatsSummary(BaseModel):
    """대시보드 요약 통계"""
    total_users: int = Field(default=0, description="전체 사용자 수")
    active_users: int = Field(default=0, description="활성 사용자 수")
    new_users_this_period: int = Field(default=0, description="기간 내 신규 사용자")
    total_sessions: int = Field(default=0, description="총 세션 수")
    total_messages: int = Field(default=0, description="총 메시지 수")
    total_tokens: int = Field(default=0, description="총 토큰 사용량")
    estimated_cost_usd: float = Field(default=0.0, description="예상 비용 (USD)")


class DailyTrend(BaseModel):
    """일별 트렌드 데이터"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    users: int = Field(default=0, description="활성 사용자 수")
    messages: int = Field(default=0, description="메시지 수")
    tokens: int = Field(default=0, description="토큰 사용량")


class HealthStatus(BaseModel):
    """헬스 상태"""
    status: str = Field(..., description="healthy, degraded, unhealthy")
    last_check: str = Field(..., description="마지막 체크 시각 (ISO 8601)")
    response_time_ms: int = Field(default=0, description="응답 시간 (ms)")


class StatsResponse(BaseModel):
    """대시보드 통계 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    period: str = Field(..., description="조회 기간")
    summary: StatsSummary = Field(..., description="요약 통계")
    trends: Optional[Dict[str, List[DailyTrend]]] = Field(
        default=None,
        description="트렌드 데이터 (daily 등)"
    )
    health: Optional[HealthStatus] = Field(default=None, description="헬스 상태")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "period": "30d",
                "summary": {
                    "total_users": 1250,
                    "active_users": 890,
                    "new_users_this_period": 45,
                    "total_sessions": 15680,
                    "total_messages": 89450,
                    "total_tokens": 12500000,
                    "estimated_cost_usd": 125.50
                },
                "trends": {
                    "daily": [
                        {"date": "2026-01-29", "users": 120, "messages": 3200, "tokens": 450000}
                    ]
                },
                "health": {
                    "status": "healthy",
                    "last_check": "2026-01-30T10:00:00Z",
                    "response_time_ms": 45
                }
            }
        }


# =============================================================================
# Cost Analysis API (신규)
# =============================================================================

class ModelCost(BaseModel):
    """모델별 비용"""
    model: str = Field(..., description="모델명")
    input_tokens: int = Field(default=0, description="입력 토큰 수")
    output_tokens: int = Field(default=0, description="출력 토큰 수")
    cost_usd: float = Field(default=0.0, description="비용 (USD)")


class UserCost(BaseModel):
    """사용자별 비용"""
    user_id: str = Field(..., description="사용자 ID")
    name: str = Field(..., description="사용자 이름")
    cost_usd: float = Field(default=0.0, description="비용 (USD)")
    tokens: int = Field(default=0, description="토큰 사용량")


class DailyCost(BaseModel):
    """일별 비용"""
    date: str = Field(..., description="날짜 (YYYY-MM-DD)")
    cost_usd: float = Field(default=0.0, description="비용 (USD)")


class CostsResponse(BaseModel):
    """비용 분석 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    period: str = Field(..., description="조회 기간")
    total_cost_usd: float = Field(..., description="총 비용 (USD)")
    by_model: List[ModelCost] = Field(default=[], description="모델별 비용")
    by_user_top10: List[UserCost] = Field(default=[], description="사용자별 비용 (상위 10명)")
    daily_trend: List[DailyCost] = Field(default=[], description="일별 비용 트렌드")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "period": "30d",
                "total_cost_usd": 125.50,
                "by_model": [
                    {"model": "gpt-4", "input_tokens": 5000000, "output_tokens": 2000000, "cost_usd": 85.00}
                ],
                "by_user_top10": [
                    {"user_id": "user_123", "name": "김철수", "cost_usd": 15.20, "tokens": 1200000}
                ],
                "daily_trend": [
                    {"date": "2026-01-29", "cost_usd": 4.50}
                ]
            }
        }


# =============================================================================
# Top Users API (신규)
# =============================================================================

class TopUser(BaseModel):
    """활성 사용자"""
    user_id: str = Field(..., description="사용자 ID")
    name: str = Field(..., description="사용자 이름")
    email: str = Field(..., description="이메일")
    sessions: int = Field(default=0, description="세션 수")
    messages: int = Field(default=0, description="메시지 수")
    tokens: int = Field(default=0, description="토큰 사용량")
    last_active: str = Field(..., description="마지막 활동 시각")


class TopUsersResponse(BaseModel):
    """활성 사용자 목록 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    period: str = Field(..., description="조회 기간")
    users: List[TopUser] = Field(default=[], description="활성 사용자 목록")


# =============================================================================
# User Management API (신규)
# =============================================================================

class UserRole(str, Enum):
    """사용자 역할"""
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


class UserStatus(str, Enum):
    """사용자 상태"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class UserUsage(BaseModel):
    """사용자 사용량"""
    sessions: int = Field(default=0, description="세션 수")
    messages: int = Field(default=0, description="메시지 수")
    tokens: int = Field(default=0, description="토큰 사용량")


class UserInfo(BaseModel):
    """사용자 정보"""
    user_id: str = Field(..., description="사용자 ID")
    email: str = Field(..., description="이메일")
    name: str = Field(..., description="이름")
    role: UserRole = Field(..., description="역할")
    status: UserStatus = Field(..., description="상태")
    created_at: str = Field(..., description="생성 시각 (ISO 8601)")
    last_login: Optional[str] = Field(default=None, description="마지막 로그인")
    usage: Optional[UserUsage] = Field(default=None, description="사용량")


class UsersListResponse(BaseModel):
    """사용자 목록 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    total: int = Field(..., description="전체 사용자 수")
    limit: int = Field(..., description="페이지 크기")
    offset: int = Field(..., description="오프셋")
    users: List[UserInfo] = Field(default=[], description="사용자 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "total": 1250,
                "limit": 20,
                "offset": 0,
                "users": [
                    {
                        "user_id": "user_123",
                        "email": "admin@hallym.ac.kr",
                        "name": "관리자",
                        "role": "admin",
                        "status": "active",
                        "created_at": "2025-09-01T00:00:00Z",
                        "last_login": "2026-01-30T09:00:00Z",
                        "usage": {"sessions": 150, "messages": 2340, "tokens": 350000}
                    }
                ]
            }
        }


class UserFilters(BaseModel):
    """사용자 필터"""
    role: Optional[UserRole] = Field(default=None, description="역할 필터")
    status: Optional[UserStatus] = Field(default=None, description="상태 필터")
    search: Optional[str] = Field(default=None, description="검색어 (이름, 이메일)")
    limit: int = Field(default=20, description="페이지 크기", ge=1, le=100)
    offset: int = Field(default=0, description="오프셋", ge=0)


class CreateUserRequest(BaseModel):
    """사용자 생성 요청"""
    email: str = Field(..., description="이메일")
    name: str = Field(..., description="이름")
    role: UserRole = Field(default=UserRole.USER, description="역할")
    password: Optional[str] = Field(default=None, description="비밀번호 (없으면 임시 생성)")
    send_welcome_email: bool = Field(default=True, description="환영 이메일 발송 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "newuser@hallym.ac.kr",
                "name": "신규 사용자",
                "role": "user",
                "password": None,
                "send_welcome_email": True
            }
        }


class CreateUserResponse(BaseModel):
    """사용자 생성 응답"""
    user_id: str = Field(..., description="생성된 사용자 ID")
    email: str = Field(..., description="이메일")
    name: str = Field(..., description="이름")
    role: UserRole = Field(..., description="역할")
    status: UserStatus = Field(..., description="상태")
    created_at: str = Field(..., description="생성 시각")
    temporary_password: bool = Field(..., description="임시 비밀번호 여부")


class UpdateUserRequest(BaseModel):
    """사용자 수정 요청"""
    name: Optional[str] = Field(default=None, description="이름")
    role: Optional[UserRole] = Field(default=None, description="역할")
    status: Optional[UserStatus] = Field(default=None, description="상태")


class DeleteUserResponse(BaseModel):
    """사용자 삭제 응답"""
    success: bool = Field(..., description="성공 여부")
    user_id: str = Field(..., description="삭제된 사용자 ID")
    message: str = Field(..., description="결과 메시지")


# =============================================================================
# Resource API (신규)
# =============================================================================

class ResourceType(str, Enum):
    """리소스 타입"""
    COURSE = "course"
    DISCUSSION = "discussion"
    DOCUMENT = "document"
    SESSION = "session"


class ResourceStats(BaseModel):
    """리소스 통계"""
    participants: Optional[int] = Field(default=None, description="참여자 수")
    discussions: Optional[int] = Field(default=None, description="토론 수")
    documents: Optional[int] = Field(default=None, description="문서 수")
    messages: Optional[int] = Field(default=None, description="메시지 수")


class ResourceItem(BaseModel):
    """리소스 항목"""
    id: str = Field(..., description="리소스 ID")
    title: str = Field(..., description="제목")
    type: ResourceType = Field(..., description="타입")
    created_by: Optional[str] = Field(default=None, description="생성자 ID")
    created_at: str = Field(..., description="생성 시각")
    updated_at: Optional[str] = Field(default=None, description="수정 시각")
    stats: Optional[ResourceStats] = Field(default=None, description="통계")

    class Config:
        extra = "allow"  # 서비스별 추가 필드 허용


class ResourceFilters(BaseModel):
    """리소스 필터"""
    type: Optional[ResourceType] = Field(default=None, description="타입 필터")
    search: Optional[str] = Field(default=None, description="검색어")
    limit: int = Field(default=20, description="페이지 크기", ge=1, le=100)
    offset: int = Field(default=0, description="오프셋", ge=0)


class ResourcesResponse(BaseModel):
    """리소스 목록 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    resource_type: Optional[str] = Field(default=None, description="리소스 타입")
    total: int = Field(..., description="전체 개수")
    items: List[ResourceItem] = Field(default=[], description="리소스 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "resource_type": "course",
                "total": 45,
                "items": [
                    {
                        "id": "course_001",
                        "title": "AI 개론",
                        "type": "course",
                        "created_by": "user_123",
                        "created_at": "2025-10-01T00:00:00Z",
                        "stats": {"participants": 35, "discussions": 120, "documents": 15}
                    }
                ]
            }
        }


# =============================================================================
# Settings API (신규)
# =============================================================================

class FeatureFlags(BaseModel):
    """기능 플래그"""
    rag: bool = Field(default=True, description="RAG 기능")
    chat: bool = Field(default=True, description="채팅 기능")
    quiz: bool = Field(default=False, description="퀴즈 기능")
    api_integration: bool = Field(default=False, description="API 연동")
    custom_branding: bool = Field(default=False, description="커스텀 브랜딩")

    class Config:
        extra = "allow"  # 서비스별 추가 기능 허용


class UsageLimits(BaseModel):
    """사용 한도"""
    daily_tokens: int = Field(default=1000000, description="일일 토큰 한도")
    monthly_tokens: int = Field(default=20000000, description="월간 토큰 한도")
    max_file_size_mb: int = Field(default=50, description="최대 파일 크기 (MB)")
    max_users: int = Field(default=1000, description="최대 사용자 수")
    max_storage_mb: int = Field(default=10240, description="최대 저장 용량 (MB)")


class Branding(BaseModel):
    """브랜딩 설정"""
    logo_url: Optional[str] = Field(default=None, description="로고 URL")
    primary_color: Optional[str] = Field(default=None, description="주요 색상")
    custom_css: Optional[str] = Field(default=None, description="커스텀 CSS")


class SubscriptionInfo(BaseModel):
    """구독 정보"""
    plan: str = Field(..., description="요금제")
    start_date: str = Field(..., description="시작일")
    end_date: Optional[str] = Field(default=None, description="종료일")
    auto_renew: bool = Field(default=False, description="자동 갱신")


class TenantConfig(BaseModel):
    """테넌트 설정"""
    max_users: Optional[int] = Field(default=None, description="최대 사용자 수")
    max_storage_mb: Optional[int] = Field(default=None, description="최대 저장 용량")
    features: FeatureFlags = Field(default_factory=FeatureFlags, description="기능 플래그")
    limits: UsageLimits = Field(default_factory=UsageLimits, description="사용 한도")
    branding: Optional[Branding] = Field(default=None, description="브랜딩")


class SettingsResponse(BaseModel):
    """테넌트 설정 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    config: TenantConfig = Field(..., description="설정")
    subscription: SubscriptionInfo = Field(..., description="구독 정보")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "config": {
                    "max_users": 2000,
                    "max_storage_mb": 10240,
                    "features": {
                        "rag": True,
                        "chat": True,
                        "quiz": False,
                        "api_integration": True
                    },
                    "limits": {
                        "daily_tokens": 1000000,
                        "monthly_tokens": 20000000,
                        "max_file_size_mb": 50
                    },
                    "branding": {
                        "logo_url": "https://...",
                        "primary_color": "#003366"
                    }
                },
                "subscription": {
                    "plan": "premium",
                    "start_date": "2025-09-01",
                    "end_date": "2026-08-31",
                    "auto_renew": True
                }
            }
        }


class UpdateSettingsRequest(BaseModel):
    """설정 수정 요청"""
    features: Optional[FeatureFlags] = Field(default=None, description="기능 플래그")
    limits: Optional[UsageLimits] = Field(default=None, description="사용 한도")
    branding: Optional[Branding] = Field(default=None, description="브랜딩")


# =============================================================================
# Extended Error Codes (기존 확장)
# =============================================================================

class ErrorCodesV2(ErrorCodes):
    """확장 에러 코드"""
    USER_EXISTS = "USER_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    FEATURE_DISABLED = "FEATURE_DISABLED"
