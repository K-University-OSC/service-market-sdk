"""
Service Market 클라이언트

서비스들의 표준 API를 호출하는 클라이언트
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import httpx

from .models import (
    ServiceInfo,
    TenantActivation,
    TenantDeactivation,
    UsageReport,
    UsageMetric,
    BillingInfo,
    BillingItem,
)

logger = logging.getLogger(__name__)


@dataclass
class ServiceEndpoints:
    """서비스 엔드포인트"""
    base_url: str
    health: str = "/mt/health"
    activate: str = "/mt/tenant/{tenant_id}/activate"
    deactivate: str = "/mt/tenant/{tenant_id}/deactivate"
    status: str = "/mt/tenant/{tenant_id}/status"
    usage: str = "/mt/tenant/{tenant_id}/usage"
    billing_usage: str = "/mt/tenant/{tenant_id}/billing/usage"
    billing_detail: str = "/mt/tenant/{tenant_id}/billing/detail"


class ServiceClient:
    """
    개별 서비스 클라이언트

    특정 서비스의 표준 API를 호출합니다.

    Example:
        client = ServiceClient(
            base_url="https://keli.k-university.ai",
            api_key="your-api-key"
        )

        # 헬스체크
        health = await client.health_check()

        # 테넌트 활성화
        result = await client.activate_tenant(
            tenant_id="hallym_univ",
            tenant_name="한림대학교",
            plan="premium",
            features=["ai_chat", "rag"],
            contact_email="admin@hallym.ac.kr",
            contact_name="홍길동"
        )
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_key_header: str = "X-Market-API-Key",
        timeout: float = 30.0,
        endpoints: Optional[ServiceEndpoints] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.timeout = timeout
        self.endpoints = endpoints or ServiceEndpoints(base_url=self.base_url)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 반환"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={self.api_key_header: self.api_key}
            )
        return self._client

    async def close(self):
        """클라이언트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _url(self, endpoint: str, **kwargs) -> str:
        """URL 생성"""
        path = endpoint.format(**kwargs)
        if path.startswith("http"):
            return path
        return f"{self.base_url}{path}"

    # =========================================================================
    # 기본 API (5개)
    # =========================================================================

    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        client = await self._get_client()
        url = self._url(self.endpoints.health)

        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def activate_tenant(
        self,
        tenant_id: str,
        tenant_name: str,
        plan: str,
        features: List[str],
        contact_email: str,
        contact_name: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """테넌트 활성화"""
        client = await self._get_client()
        url = self._url(self.endpoints.activate, tenant_id=tenant_id)

        payload = {
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "plan": plan,
            "features": features,
            "config": config or {},
            "contact": {
                "email": contact_email,
                "name": contact_name
            }
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Tenant activated: {tenant_id}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Activate failed: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Activate failed: {e}")
            raise

    async def deactivate_tenant(
        self,
        tenant_id: str,
        reason: str,
        preserve_data: bool = True,
    ) -> Dict[str, Any]:
        """테넌트 비활성화"""
        client = await self._get_client()
        url = self._url(self.endpoints.deactivate, tenant_id=tenant_id)

        payload = {
            "reason": reason,
            "preserve_data": preserve_data
        }

        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Tenant deactivated: {tenant_id}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Deactivate failed: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Deactivate failed: {e}")
            raise

    async def get_tenant_status(self, tenant_id: str) -> Dict[str, Any]:
        """테넌트 상태 조회"""
        client = await self._get_client()
        url = self._url(self.endpoints.status, tenant_id=tenant_id)

        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"error": "not_found", "tenant_id": tenant_id}
            raise
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            raise

    async def get_tenant_usage(
        self,
        tenant_id: str,
        period: str
    ) -> Dict[str, Any]:
        """테넌트 사용량 조회"""
        client = await self._get_client()
        url = self._url(self.endpoints.usage, tenant_id=tenant_id)

        try:
            response = await client.get(url, params={"period": period})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Usage check failed: {e}")
            raise

    # =========================================================================
    # 빌링 API (3개)
    # =========================================================================

    async def get_billing_usage(
        self,
        tenant_id: str,
        period: str
    ) -> UsageReport:
        """빌링용 사용량 조회"""
        client = await self._get_client()
        url = self._url(self.endpoints.billing_usage, tenant_id=tenant_id)

        try:
            response = await client.get(url, params={"period": period})
            response.raise_for_status()
            data = response.json()

            return UsageReport(
                tenant_id=tenant_id,
                service_id="",  # 호출자가 설정
                period=period,
                metrics=[UsageMetric(**m) for m in data.get("metrics", [])],
                total_cost=data.get("total_cost")
            )
        except Exception as e:
            logger.error(f"Billing usage failed: {e}")
            raise

    async def get_billing_detail(
        self,
        tenant_id: str,
        period: str
    ) -> BillingInfo:
        """상세 빌링 정보 조회"""
        client = await self._get_client()
        url = self._url(self.endpoints.billing_detail, tenant_id=tenant_id)

        try:
            response = await client.get(url, params={"period": period})
            response.raise_for_status()
            data = response.json()

            return BillingInfo(
                tenant_id=tenant_id,
                service_id="",
                period=period,
                items=[BillingItem(**i) for i in data.get("items", [])],
                subtotal=data.get("subtotal", 0),
                tax=data.get("tax", 0),
                total=data.get("total", 0),
                currency=data.get("currency", "KRW")
            )
        except Exception as e:
            logger.error(f"Billing detail failed: {e}")
            raise


class ServiceMarketClient:
    """
    Service Market 통합 클라이언트

    여러 서비스를 관리하고 호출합니다.

    Example:
        market = ServiceMarketClient()

        # 서비스 등록
        market.register_service(
            service_id="keli_tutor",
            base_url="https://keli.k-university.ai",
            api_key="your-api-key"
        )

        # 테넌트 활성화
        await market.activate_tenant(
            service_id="keli_tutor",
            tenant_id="hallym_univ",
            ...
        )
    """

    def __init__(self):
        self._services: Dict[str, ServiceClient] = {}
        self._service_info: Dict[str, ServiceInfo] = {}

    def register_service(
        self,
        service_id: str,
        base_url: str,
        api_key: str,
        info: Optional[ServiceInfo] = None,
        **kwargs
    ) -> None:
        """서비스 등록"""
        self._services[service_id] = ServiceClient(
            base_url=base_url,
            api_key=api_key,
            **kwargs
        )
        if info:
            self._service_info[service_id] = info

        logger.info(f"Service registered: {service_id} -> {base_url}")

    def get_service(self, service_id: str) -> ServiceClient:
        """서비스 클라이언트 반환"""
        if service_id not in self._services:
            raise ValueError(f"Service not registered: {service_id}")
        return self._services[service_id]

    async def close_all(self):
        """모든 서비스 클라이언트 종료"""
        for client in self._services.values():
            await client.close()
        self._services.clear()

    # =========================================================================
    # 통합 API
    # =========================================================================

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """모든 서비스 헬스체크"""
        results = {}
        for service_id, client in self._services.items():
            results[service_id] = await client.health_check()
        return results

    async def activate_tenant(
        self,
        service_id: str,
        activation: TenantActivation
    ) -> Dict[str, Any]:
        """테넌트 활성화"""
        client = self.get_service(service_id)
        return await client.activate_tenant(
            tenant_id=activation.tenant_id,
            tenant_name=activation.tenant_name,
            plan=activation.plan,
            features=activation.features,
            contact_email=activation.contact_email,
            contact_name=activation.contact_name,
            config=activation.config,
        )

    async def deactivate_tenant(
        self,
        service_id: str,
        deactivation: TenantDeactivation
    ) -> Dict[str, Any]:
        """테넌트 비활성화"""
        client = self.get_service(service_id)
        return await client.deactivate_tenant(
            tenant_id=deactivation.tenant_id,
            reason=deactivation.reason,
            preserve_data=deactivation.preserve_data,
        )

    async def get_all_usage(
        self,
        tenant_id: str,
        period: str
    ) -> Dict[str, UsageReport]:
        """모든 서비스의 사용량 조회"""
        results = {}
        for service_id, client in self._services.items():
            try:
                data = await client.get_tenant_usage(tenant_id, period)
                results[service_id] = UsageReport(
                    tenant_id=tenant_id,
                    service_id=service_id,
                    period=period,
                    metrics=[],
                    total_cost=data.get("usage", {}).get("total_cost")
                )
            except Exception as e:
                logger.warning(f"Usage fetch failed for {service_id}: {e}")
        return results
