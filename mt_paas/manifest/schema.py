"""
manifest.yaml 스키마 정의

서비스의 manifest.yaml 구조를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ServiceInfo:
    """서비스 기본 정보"""
    name: str
    version: str
    description: str = ""
    category: str = "education"
    icon_url: Optional[str] = None
    homepage_url: Optional[str] = None
    support_email: Optional[str] = None


@dataclass
class Endpoints:
    """서비스 엔드포인트"""
    base_url: str
    health_check: str = "/mt/health"
    activate: str = "/mt/tenant/{tenant_id}/activate"
    deactivate: str = "/mt/tenant/{tenant_id}/deactivate"
    status: str = "/mt/tenant/{tenant_id}/status"
    usage: str = "/mt/tenant/{tenant_id}/usage"
    # 데이터 API
    users: Optional[str] = None
    activities: Optional[str] = None
    learning_records: Optional[str] = None
    analytics: Optional[str] = None
    # 빌링 API
    billing_usage: Optional[str] = None
    billing_detail: Optional[str] = None
    billing_estimate: Optional[str] = None


@dataclass
class AuthConfig:
    """인증 설정"""
    type: str = "api_key"  # api_key, oauth2, jwt
    header_name: str = "X-Market-API-Key"
    oauth2_config: Optional[Dict[str, Any]] = None


@dataclass
class UsageMetric:
    """사용량 측정 항목"""
    name: str
    type: str  # counter, gauge
    unit: str
    description: str = ""


@dataclass
class PricingTier:
    """가격 티어"""
    name: str
    price_per_unit: float
    min_units: int = 0
    max_units: Optional[int] = None


@dataclass
class PlanConfig:
    """요금제 설정"""
    name: str
    display_name: str
    max_users: int
    max_storage_mb: int
    features: List[str] = field(default_factory=list)
    price_monthly: float = 0.0
    price_yearly: float = 0.0
    api_rate_limit: int = 1000


@dataclass
class PricingConfig:
    """가격 설정"""
    currency: str = "KRW"
    billing_cycle: str = "monthly"  # monthly, yearly
    api_cost_per_1k: float = 0.0
    storage_cost_per_gb: float = 0.0
    llm_token_cost_per_1k: float = 0.0
    custom_pricing: Optional[Dict[str, PricingTier]] = None


@dataclass
class Manifest:
    """서비스 매니페스트"""
    service: ServiceInfo
    endpoints: Endpoints
    auth: AuthConfig = field(default_factory=AuthConfig)
    usage_metrics: List[UsageMetric] = field(default_factory=list)
    plans: List[PlanConfig] = field(default_factory=list)
    pricing: Optional[PricingConfig] = None
    required_env_vars: List[str] = field(default_factory=list)
    optional_env_vars: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Manifest":
        """딕셔너리에서 Manifest 생성"""
        service_data = data.get("service", {})
        service = ServiceInfo(
            name=service_data.get("name", "unknown"),
            version=service_data.get("version", "0.0.0"),
            description=service_data.get("description", ""),
            category=service_data.get("category", "education"),
            icon_url=service_data.get("icon_url"),
            homepage_url=service_data.get("homepage_url"),
            support_email=service_data.get("support_email"),
        )

        endpoints_data = data.get("endpoints", {})
        endpoints = Endpoints(
            base_url=endpoints_data.get("base_url", ""),
            health_check=endpoints_data.get("health_check", "/mt/health"),
            activate=endpoints_data.get("activate", "/mt/tenant/{tenant_id}/activate"),
            deactivate=endpoints_data.get("deactivate", "/mt/tenant/{tenant_id}/deactivate"),
            status=endpoints_data.get("status", "/mt/tenant/{tenant_id}/status"),
            usage=endpoints_data.get("usage", "/mt/tenant/{tenant_id}/usage"),
            users=endpoints_data.get("users"),
            activities=endpoints_data.get("activities"),
            learning_records=endpoints_data.get("learning_records"),
            analytics=endpoints_data.get("analytics"),
            billing_usage=endpoints_data.get("billing_usage"),
            billing_detail=endpoints_data.get("billing_detail"),
            billing_estimate=endpoints_data.get("billing_estimate"),
        )

        auth_data = data.get("auth", {})
        auth = AuthConfig(
            type=auth_data.get("type", "api_key"),
            header_name=auth_data.get("header_name", "X-Market-API-Key"),
            oauth2_config=auth_data.get("oauth2_config"),
        )

        usage_metrics = [
            UsageMetric(**m) for m in data.get("usage_metrics", [])
        ]

        plans = [
            PlanConfig(**p) for p in data.get("plans", [])
        ]

        pricing_data = data.get("pricing")
        pricing = None
        if pricing_data:
            pricing = PricingConfig(
                currency=pricing_data.get("currency", "KRW"),
                billing_cycle=pricing_data.get("billing_cycle", "monthly"),
                api_cost_per_1k=pricing_data.get("api_cost_per_1k", 0.0),
                storage_cost_per_gb=pricing_data.get("storage_cost_per_gb", 0.0),
                llm_token_cost_per_1k=pricing_data.get("llm_token_cost_per_1k", 0.0),
            )

        return cls(
            service=service,
            endpoints=endpoints,
            auth=auth,
            usage_metrics=usage_metrics,
            plans=plans,
            pricing=pricing,
            required_env_vars=data.get("required_env_vars", []),
            optional_env_vars=data.get("optional_env_vars", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "service": {
                "name": self.service.name,
                "version": self.service.version,
                "description": self.service.description,
                "category": self.service.category,
                "icon_url": self.service.icon_url,
                "homepage_url": self.service.homepage_url,
                "support_email": self.service.support_email,
            },
            "endpoints": {
                "base_url": self.endpoints.base_url,
                "health_check": self.endpoints.health_check,
                "activate": self.endpoints.activate,
                "deactivate": self.endpoints.deactivate,
                "status": self.endpoints.status,
                "usage": self.endpoints.usage,
            },
            "auth": {
                "type": self.auth.type,
                "header_name": self.auth.header_name,
            },
            "usage_metrics": [
                {"name": m.name, "type": m.type, "unit": m.unit, "description": m.description}
                for m in self.usage_metrics
            ],
            "plans": [
                {
                    "name": p.name,
                    "display_name": p.display_name,
                    "max_users": p.max_users,
                    "max_storage_mb": p.max_storage_mb,
                    "features": p.features,
                    "price_monthly": p.price_monthly,
                }
                for p in self.plans
            ],
            "required_env_vars": self.required_env_vars,
            "optional_env_vars": self.optional_env_vars,
        }
