"""
Service Market 데이터 모델
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    """서비스 정보"""
    id: str
    name: str
    version: str
    description: str
    category: str
    base_url: str
    status: str = "active"
    plans: List[Dict[str, Any]] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)


class TenantActivation(BaseModel):
    """테넌트 활성화 요청"""
    tenant_id: str
    tenant_name: str
    service_id: str
    plan: str
    features: List[str]
    config: Optional[Dict[str, Any]] = None
    contact_email: str
    contact_name: str


class TenantDeactivation(BaseModel):
    """테넌트 비활성화 요청"""
    tenant_id: str
    service_id: str
    reason: str
    preserve_data: bool = True


class UsageMetric(BaseModel):
    """사용량 메트릭"""
    name: str
    value: float
    unit: str


class UsageReport(BaseModel):
    """사용량 보고서"""
    tenant_id: str
    service_id: str
    period: str
    metrics: List[UsageMetric]
    total_cost: Optional[float] = None


class BillingItem(BaseModel):
    """빌링 항목"""
    name: str
    unit: str
    quantity: float
    unit_price: float
    amount: float


class BillingInfo(BaseModel):
    """빌링 정보"""
    tenant_id: str
    service_id: str
    period: str
    items: List[BillingItem]
    subtotal: float
    tax: float
    total: float
    currency: str = "KRW"
