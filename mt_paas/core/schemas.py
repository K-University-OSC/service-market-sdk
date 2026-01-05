"""
Pydantic 스키마 정의

API 요청/응답 스키마
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    """테넌트 생성 요청"""
    id: str = Field(..., description="테넌트 고유 ID")
    name: str = Field(..., description="테넌트 이름")
    plan: str = Field(default="basic", description="구독 요금제")
    features: Optional[List[str]] = Field(default=None, description="활성화할 기능 목록")
    config: Optional[Dict[str, Any]] = Field(default=None, description="추가 설정")
    admin_email: Optional[str] = Field(default=None, description="관리자 이메일")
    admin_name: Optional[str] = Field(default=None, description="관리자 이름")
    service_type: str = Field(default="generic", description="서비스 타입")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "hallym_univ",
                "name": "한림대학교",
                "plan": "premium",
                "features": ["ai_chat", "rag", "quiz"],
                "admin_email": "admin@hallym.ac.kr",
                "admin_name": "홍길동"
            }
        }


class TenantUpdate(BaseModel):
    """테넌트 수정 요청"""
    name: Optional[str] = None
    admin_email: Optional[str] = None
    admin_name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class TenantResponse(BaseModel):
    """테넌트 응답"""
    id: str
    name: str
    subdomain: Optional[str] = None
    status: str
    admin_email: Optional[str] = None
    admin_name: Optional[str] = None
    service_type: str
    config: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    provisioned_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    """구독 생성 요청"""
    plan: str = Field(default="basic", description="구독 요금제")
    duration_days: int = Field(default=365, description="구독 기간 (일)")
    max_users: Optional[int] = Field(default=None, description="최대 사용자 수")
    max_storage_mb: Optional[int] = Field(default=None, description="최대 저장 용량 (MB)")
    features: Optional[Dict[str, Any]] = Field(default=None, description="활성화할 기능")


class SubscriptionResponse(BaseModel):
    """구독 응답"""
    id: str
    tenant_id: str
    plan: str
    is_active: bool
    start_date: datetime
    end_date: datetime
    max_users: int
    max_storage_mb: int
    features: Dict[str, Any]

    class Config:
        from_attributes = True
