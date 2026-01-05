"""
표준 API 요청/응답 모델

LTI 스타일 표준 인터페이스에서 사용하는 Pydantic 모델
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# =============================================================================
# Health Check
# =============================================================================

class HealthResponse(BaseModel):
    """헬스체크 응답"""
    status: str = Field(..., description="healthy, degraded, unhealthy")
    version: str = Field(..., description="서비스 버전")
    timestamp: str = Field(..., description="ISO 8601 형식 타임스탬프")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "1.0.0",
                "timestamp": "2026-01-03T12:00:00Z"
            }
        }


# =============================================================================
# Tenant Activate
# =============================================================================

class ContactInfo(BaseModel):
    """담당자 정보"""
    email: str = Field(..., description="담당자 이메일")
    name: str = Field(..., description="담당자 이름")


class ActivateRequest(BaseModel):
    """테넌트 활성화 요청"""
    tenant_id: str = Field(..., description="테넌트 고유 ID")
    tenant_name: str = Field(..., description="테넌트 표시명")
    plan: str = Field(..., description="구독 요금제 (basic, standard, premium 등)")
    features: List[str] = Field(..., description="활성화할 기능 목록")
    config: Optional[Dict[str, Any]] = Field(default={}, description="추가 설정")
    contact: ContactInfo = Field(..., description="담당자 정보")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "tenant_name": "한림대학교",
                "plan": "premium",
                "features": ["ai_chat", "rag", "quiz"],
                "config": {"max_users": 500},
                "contact": {
                    "email": "admin@hallym.ac.kr",
                    "name": "홍길동"
                }
            }
        }


class ActivateResponse(BaseModel):
    """테넌트 활성화 응답"""
    success: bool = Field(..., description="성공 여부")
    tenant_id: str = Field(..., description="테넌트 ID")
    access_url: str = Field(..., description="사용자 접속 URL")
    message: str = Field(..., description="결과 메시지")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "tenant_id": "hallym_univ",
                "access_url": "https://service.example.com/hallym",
                "message": "Tenant activated successfully"
            }
        }


# =============================================================================
# Tenant Deactivate
# =============================================================================

class DeactivateRequest(BaseModel):
    """테넌트 비활성화 요청"""
    reason: str = Field(
        ...,
        description="비활성화 사유: subscription_expired, admin_request, violation"
    )
    preserve_data: bool = Field(
        default=True,
        description="데이터 보존 여부"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "reason": "subscription_expired",
                "preserve_data": True
            }
        }


class DeactivateResponse(BaseModel):
    """테넌트 비활성화 응답"""
    success: bool = Field(..., description="성공 여부")
    tenant_id: str = Field(..., description="테넌트 ID")
    status: str = Field(..., description="변경된 상태")
    data_preserved: bool = Field(..., description="데이터 보존 여부")
    data_retention_until: Optional[str] = Field(
        default=None,
        description="데이터 보존 만료일 (ISO 8601)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "tenant_id": "hallym_univ",
                "status": "deactivated",
                "data_preserved": True,
                "data_retention_until": "2026-04-03T00:00:00Z"
            }
        }


# =============================================================================
# Tenant Status
# =============================================================================

class StatusResponse(BaseModel):
    """테넌트 상태 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    status: str = Field(..., description="상태: active, suspended, deactivated")
    plan: str = Field(..., description="현재 요금제")
    features: List[str] = Field(..., description="활성화된 기능 목록")
    created_at: str = Field(..., description="생성 시각 (ISO 8601)")
    updated_at: str = Field(..., description="최종 수정 시각 (ISO 8601)")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "status": "active",
                "plan": "premium",
                "features": ["ai_chat", "rag", "quiz"],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-03T12:00:00Z"
            }
        }


# =============================================================================
# Usage
# =============================================================================

class UsageData(BaseModel):
    """사용량 데이터"""
    active_users: Optional[int] = Field(default=0, description="활성 사용자 수")
    total_sessions: Optional[int] = Field(default=0, description="총 세션 수")
    api_calls: Optional[int] = Field(default=0, description="API 호출 횟수")
    ai_tokens: Optional[int] = Field(default=0, description="AI 토큰 사용량")
    storage_mb: Optional[int] = Field(default=0, description="스토리지 사용량 (MB)")

    class Config:
        extra = "allow"  # 서비스별 추가 메트릭 허용


class UsageResponse(BaseModel):
    """사용량 조회 응답"""
    tenant_id: str = Field(..., description="테넌트 ID")
    period: str = Field(..., description="조회 기간 (YYYY-MM)")
    usage: UsageData = Field(..., description="사용량 데이터")

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "hallym_univ",
                "period": "2026-01",
                "usage": {
                    "active_users": 150,
                    "total_sessions": 3500,
                    "api_calls": 15000,
                    "ai_tokens": 500000,
                    "storage_mb": 25600
                }
            }
        }


# =============================================================================
# Error Response
# =============================================================================

class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = Field(default=False, description="항상 False")
    error: str = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="추가 에러 정보"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "TENANT_NOT_FOUND",
                "message": "Tenant hallym_univ not found",
                "details": None
            }
        }


# =============================================================================
# Error Codes
# =============================================================================

class ErrorCodes:
    """표준 에러 코드"""
    TENANT_EXISTS = "TENANT_EXISTS"
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
