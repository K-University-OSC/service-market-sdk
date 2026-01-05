"""
멀티테넌트 핵심 모델 정의

Central DB에 저장되는 테넌트 메타정보 모델
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, Boolean,
    ForeignKey, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class TenantStatus(str, Enum):
    """테넌트 상태"""
    PENDING = "pending"           # 생성됨, 프로비저닝 대기
    PROVISIONING = "provisioning" # 프로비저닝 진행 중
    ACTIVE = "active"             # 서비스 사용 가능
    SUSPENDED = "suspended"       # 일시 중지 (결제 미완료 등)
    DELETED = "deleted"           # 삭제됨


class SubscriptionPlan(str, Enum):
    """구독 요금제"""
    FREE = "free"           # 무료 (데모)
    BASIC = "basic"         # 기본
    STANDARD = "standard"   # 표준
    PREMIUM = "premium"     # 프리미엄
    ENTERPRISE = "enterprise"  # 기업용


class Tenant(Base):
    """
    테넌트 모델

    각 기관(대학, 기업 등)을 나타냅니다.
    """
    __tablename__ = "tenants"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    subdomain = Column(String(50), unique=True, index=True)

    # 상태
    status = Column(
        SQLEnum(TenantStatus),
        default=TenantStatus.PENDING,
        nullable=False
    )

    # 관리자 정보
    admin_email = Column(String(200))
    admin_name = Column(String(100))

    # 설명
    description = Column(Text)

    # 포트 할당 (Docker-Per-Tenant 방식용)
    port_range_start = Column(Integer)
    port_range_end = Column(Integer)

    # 서비스 타입 (keli_tutor, llm_chatbot, advisor 등)
    service_type = Column(String(50), nullable=False, default="generic")

    # 추가 설정 (JSON)
    config = Column(JSON, default=dict)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    provisioned_at = Column(DateTime, nullable=True)

    # 관계
    subscriptions = relationship("Subscription", back_populates="tenant")

    # 인덱스
    __table_args__ = (
        Index('idx_tenant_status', 'status'),
        Index('idx_tenant_service', 'service_type'),
    )

    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE

    @property
    def db_name(self) -> str:
        """테넌트 전용 DB 이름"""
        return f"tenant_{self.id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "subdomain": self.subdomain,
            "status": self.status.value,
            "admin_email": self.admin_email,
            "admin_name": self.admin_name,
            "service_type": self.service_type,
            "config": self.config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "provisioned_at": self.provisioned_at.isoformat() if self.provisioned_at else None,
        }


class Subscription(Base):
    """
    구독 모델

    테넌트의 서비스 구독 정보를 관리합니다.
    """
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False, index=True)

    # 요금제
    plan = Column(
        SQLEnum(SubscriptionPlan),
        default=SubscriptionPlan.FREE,
        nullable=False
    )

    # 상태
    is_active = Column(Boolean, default=True)

    # 기간
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # 제한
    max_users = Column(Integer, default=50)
    max_storage_mb = Column(Integer, default=1000)  # 1GB
    max_api_calls_per_day = Column(Integer, default=1000)

    # 활성화된 기능 (요금제별로 다름)
    features = Column(JSON, default=dict)

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    tenant = relationship("Tenant", back_populates="subscriptions")

    __table_args__ = (
        Index('idx_subscription_active', 'is_active'),
        Index('idx_subscription_dates', 'start_date', 'end_date'),
    )

    def __repr__(self):
        return f"<Subscription(tenant={self.tenant_id}, plan={self.plan})>"

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.end_date

    @classmethod
    def get_default_features(cls, plan: SubscriptionPlan) -> Dict[str, bool]:
        """요금제별 기본 기능 설정"""
        base_features = {
            "ai_chat": True,
            "file_upload": True,
        }

        plan_features = {
            SubscriptionPlan.FREE: {
                **base_features,
                "rag": False,
                "discussion": False,
                "quiz": False,
                "api_integration": False,
            },
            SubscriptionPlan.BASIC: {
                **base_features,
                "rag": False,
                "discussion": False,
                "quiz": False,
                "api_integration": False,
            },
            SubscriptionPlan.STANDARD: {
                **base_features,
                "rag": True,
                "discussion": True,
                "quiz": False,
                "api_integration": False,
            },
            SubscriptionPlan.PREMIUM: {
                **base_features,
                "rag": True,
                "discussion": True,
                "quiz": True,
                "api_integration": True,
            },
            SubscriptionPlan.ENTERPRISE: {
                **base_features,
                "rag": True,
                "discussion": True,
                "quiz": True,
                "api_integration": True,
                "custom_branding": True,
                "priority_support": True,
                "dedicated_resources": True,
            },
        }

        return plan_features.get(plan, base_features)


class UsageLog(Base):
    """
    사용량 로그 모델

    API 호출, 스토리지 사용량 등을 기록합니다.
    """
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(50), ForeignKey("tenants.id"), nullable=False, index=True)

    # 사용량 종류
    usage_type = Column(String(50), nullable=False)  # api_call, storage, llm_token 등

    # 사용량
    amount = Column(Integer, default=1)

    # 메타데이터
    extra_data = Column(JSON, default=dict)

    # 타임스탬프
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_usage_tenant_type', 'tenant_id', 'usage_type'),
        Index('idx_usage_timestamp', 'timestamp'),
    )
