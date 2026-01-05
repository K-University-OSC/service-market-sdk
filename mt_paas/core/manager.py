"""
테넌트 관리자

테넌트 CRUD 및 라이프사이클 관리
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Tenant, TenantStatus, Subscription, SubscriptionPlan
from .database import db_manager


class TenantManager:
    """
    테넌트 관리자

    테넌트의 생성, 조회, 수정, 삭제 및 라이프사이클을 관리합니다.
    """

    def __init__(self):
        self.db = db_manager

    async def create_tenant(
        self,
        tenant_id: str,
        name: str,
        plan: str = "basic",
        features: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        admin_email: Optional[str] = None,
        admin_name: Optional[str] = None,
        service_type: str = "generic",
    ) -> Tenant:
        """
        새 테넌트 생성

        Args:
            tenant_id: 테넌트 고유 ID
            name: 테넌트 이름
            plan: 구독 요금제
            features: 활성화할 기능 목록
            config: 추가 설정
            admin_email: 관리자 이메일
            admin_name: 관리자 이름
            service_type: 서비스 타입

        Returns:
            생성된 Tenant 객체
        """
        async with self.db.get_central_session() as session:
            # 중복 확인
            existing = await session.get(Tenant, tenant_id)
            if existing:
                from ..standard_api.handler import TenantExistsError
                raise TenantExistsError(tenant_id)

            # 테넌트 생성
            tenant = Tenant(
                id=tenant_id,
                name=name,
                subdomain=tenant_id,
                status=TenantStatus.PENDING,
                admin_email=admin_email,
                admin_name=admin_name,
                service_type=service_type,
                config=config or {},
            )
            session.add(tenant)

            # 구독 생성
            plan_enum = SubscriptionPlan(plan) if plan in [p.value for p in SubscriptionPlan] else SubscriptionPlan.BASIC

            subscription = Subscription(
                tenant_id=tenant_id,
                plan=plan_enum,
                start_date=datetime.utcnow(),
                end_date=datetime(2099, 12, 31),  # 무기한
                features=features or Subscription.get_default_features(plan_enum),
            )
            session.add(subscription)

            await session.commit()
            await session.refresh(tenant)

            return tenant

    async def activate_tenant(self, tenant_id: str) -> Tenant:
        """
        테넌트 활성화

        프로비저닝 완료 후 활성화 상태로 변경
        """
        async with self.db.get_central_session() as session:
            tenant = await session.get(Tenant, tenant_id)
            if not tenant:
                from ..standard_api.handler import TenantNotFoundError
                raise TenantNotFoundError(tenant_id)

            tenant.status = TenantStatus.ACTIVE
            tenant.provisioned_at = datetime.utcnow()

            await session.commit()
            await session.refresh(tenant)

            return tenant

    async def deactivate_tenant(
        self,
        tenant_id: str,
        reason: str = "admin_request",
        preserve_data: bool = True,
    ) -> Tenant:
        """
        테넌트 비활성화

        Args:
            tenant_id: 테넌트 ID
            reason: 비활성화 사유
            preserve_data: 데이터 보존 여부

        Returns:
            업데이트된 Tenant 객체
        """
        async with self.db.get_central_session() as session:
            tenant = await session.get(Tenant, tenant_id)
            if not tenant:
                from ..standard_api.handler import TenantNotFoundError
                raise TenantNotFoundError(tenant_id)

            if preserve_data:
                tenant.status = TenantStatus.SUSPENDED
            else:
                tenant.status = TenantStatus.DELETED

            # 메타데이터에 사유 기록
            config = tenant.config or {}
            config["deactivation_reason"] = reason
            config["deactivation_date"] = datetime.utcnow().isoformat()
            config["data_preserved"] = preserve_data
            tenant.config = config

            await session.commit()
            await session.refresh(tenant)

            return tenant

    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """테넌트 조회"""
        async with self.db.get_central_session() as session:
            return await session.get(Tenant, tenant_id)

    async def get_tenant_with_subscription(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """테넌트 및 구독 정보 조회"""
        async with self.db.get_central_session() as session:
            tenant = await session.get(Tenant, tenant_id)
            if not tenant:
                return None

            # 활성 구독 조회
            result = await session.execute(
                select(Subscription)
                .where(Subscription.tenant_id == tenant_id)
                .where(Subscription.is_active == True)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
            subscription = result.scalar_one_or_none()

            return {
                "tenant": tenant,
                "subscription": subscription,
            }

    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        service_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Tenant]:
        """테넌트 목록 조회"""
        async with self.db.get_central_session() as session:
            query = select(Tenant)

            if status:
                query = query.where(Tenant.status == status)
            if service_type:
                query = query.where(Tenant.service_type == service_type)

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)

            return list(result.scalars().all())

    async def update_tenant_status(
        self,
        tenant_id: str,
        status: TenantStatus,
    ) -> Tenant:
        """테넌트 상태 업데이트"""
        async with self.db.get_central_session() as session:
            tenant = await session.get(Tenant, tenant_id)
            if not tenant:
                from ..standard_api.handler import TenantNotFoundError
                raise TenantNotFoundError(tenant_id)

            tenant.status = status

            await session.commit()
            await session.refresh(tenant)

            return tenant

    async def delete_tenant(self, tenant_id: str) -> bool:
        """테넌트 삭제 (영구 삭제)"""
        async with self.db.get_central_session() as session:
            tenant = await session.get(Tenant, tenant_id)
            if not tenant:
                return False

            # 구독 삭제
            await session.execute(
                delete(Subscription).where(Subscription.tenant_id == tenant_id)
            )

            # 테넌트 삭제
            await session.delete(tenant)
            await session.commit()

            return True
