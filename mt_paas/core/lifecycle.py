"""
테넌트 생명주기 관리

테넌트의 프로비저닝, 활성화, 비활성화, 삭제 등을 관리합니다.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable, List
from enum import Enum

from .models import Tenant, TenantStatus, Subscription, SubscriptionPlan
from .database import DatabaseManager

logger = logging.getLogger(__name__)


class LifecycleEvent(str, Enum):
    """생명주기 이벤트"""
    BEFORE_CREATE = "before_create"
    AFTER_CREATE = "after_create"
    BEFORE_PROVISION = "before_provision"
    AFTER_PROVISION = "after_provision"
    BEFORE_ACTIVATE = "before_activate"
    AFTER_ACTIVATE = "after_activate"
    BEFORE_SUSPEND = "before_suspend"
    AFTER_SUSPEND = "after_suspend"
    BEFORE_DELETE = "before_delete"
    AFTER_DELETE = "after_delete"


class TenantLifecycle:
    """
    테넌트 생명주기 관리자

    테넌트의 전체 생명주기를 관리하고 이벤트 훅을 제공합니다.

    Example:
        lifecycle = TenantLifecycle(db_manager)

        # 이벤트 훅 등록
        lifecycle.on(LifecycleEvent.AFTER_CREATE, my_handler)

        # 테넌트 생성
        tenant = await lifecycle.create(
            tenant_id="hallym_univ",
            name="한림대학교",
            plan="premium"
        )
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._hooks: Dict[LifecycleEvent, List[Callable]] = {
            event: [] for event in LifecycleEvent
        }

    def on(self, event: LifecycleEvent, handler: Callable) -> None:
        """이벤트 훅 등록"""
        self._hooks[event].append(handler)

    def off(self, event: LifecycleEvent, handler: Callable) -> None:
        """이벤트 훅 제거"""
        if handler in self._hooks[event]:
            self._hooks[event].remove(handler)

    async def _emit(self, event: LifecycleEvent, **kwargs) -> None:
        """이벤트 발생"""
        for handler in self._hooks[event]:
            try:
                result = handler(**kwargs)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"Hook error for {event}: {e}")

    # =========================================================================
    # 생성 (Create)
    # =========================================================================

    async def create(
        self,
        tenant_id: str,
        name: str,
        plan: str = "basic",
        features: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
        admin_email: Optional[str] = None,
        admin_name: Optional[str] = None,
        service_type: str = "generic",
        auto_provision: bool = False,
    ) -> Tenant:
        """
        테넌트 생성

        Args:
            tenant_id: 테넌트 고유 ID
            name: 테넌트 이름
            plan: 구독 요금제
            features: 활성화할 기능 목록
            config: 추가 설정
            admin_email: 관리자 이메일
            admin_name: 관리자 이름
            service_type: 서비스 타입
            auto_provision: True면 생성 후 자동 프로비저닝
        """
        await self._emit(
            LifecycleEvent.BEFORE_CREATE,
            tenant_id=tenant_id,
            name=name,
            plan=plan
        )

        async with self.db.get_central_session() as session:
            # 테넌트 생성
            tenant = Tenant(
                id=tenant_id,
                name=name,
                subdomain=tenant_id.replace("_", "-"),
                status=TenantStatus.PENDING,
                admin_email=admin_email,
                admin_name=admin_name,
                service_type=service_type,
                config=config or {},
            )
            session.add(tenant)

            # 구독 생성
            subscription_plan = SubscriptionPlan(plan) if plan in [p.value for p in SubscriptionPlan] else SubscriptionPlan.BASIC
            subscription = Subscription(
                tenant_id=tenant_id,
                plan=subscription_plan,
                is_active=True,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=365),
                features=Subscription.get_default_features(subscription_plan),
            )

            # 사용자 지정 기능 병합
            if features:
                for feature in features:
                    subscription.features[feature] = True

            session.add(subscription)
            await session.commit()
            await session.refresh(tenant)

        await self._emit(
            LifecycleEvent.AFTER_CREATE,
            tenant=tenant
        )

        logger.info(f"Tenant created: {tenant_id}")

        if auto_provision:
            await self.provision(tenant_id)

        return tenant

    # =========================================================================
    # 프로비저닝 (Provision)
    # =========================================================================

    async def provision(self, tenant_id: str) -> Tenant:
        """
        테넌트 프로비저닝

        - 테넌트 전용 데이터베이스 생성
        - 필요한 리소스 할당
        """
        await self._emit(LifecycleEvent.BEFORE_PROVISION, tenant_id=tenant_id)

        async with self.db.get_central_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant not found: {tenant_id}")

            tenant.status = TenantStatus.PROVISIONING
            await session.commit()

        # 테넌트 DB 생성
        try:
            await self.db.create_tenant_database(tenant_id)

            async with self.db.get_central_session() as session:
                result = await session.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )
                tenant = result.scalar_one()
                tenant.status = TenantStatus.ACTIVE
                tenant.provisioned_at = datetime.utcnow()
                await session.commit()
                await session.refresh(tenant)

        except Exception as e:
            logger.error(f"Provisioning failed for {tenant_id}: {e}")
            async with self.db.get_central_session() as session:
                result = await session.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )
                tenant = result.scalar_one()
                tenant.status = TenantStatus.PENDING
                await session.commit()
            raise

        await self._emit(LifecycleEvent.AFTER_PROVISION, tenant=tenant)
        logger.info(f"Tenant provisioned: {tenant_id}")

        return tenant

    # =========================================================================
    # 활성화 (Activate)
    # =========================================================================

    async def activate(self, tenant_id: str) -> Tenant:
        """테넌트 활성화 (일시중지 상태에서 복원)"""
        await self._emit(LifecycleEvent.BEFORE_ACTIVATE, tenant_id=tenant_id)

        async with self.db.get_central_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant not found: {tenant_id}")

            if tenant.status == TenantStatus.DELETED:
                raise ValueError("Cannot activate deleted tenant")

            tenant.status = TenantStatus.ACTIVE
            await session.commit()
            await session.refresh(tenant)

        await self._emit(LifecycleEvent.AFTER_ACTIVATE, tenant=tenant)
        logger.info(f"Tenant activated: {tenant_id}")

        return tenant

    # =========================================================================
    # 일시중지 (Suspend)
    # =========================================================================

    async def suspend(
        self,
        tenant_id: str,
        reason: Optional[str] = None
    ) -> Tenant:
        """테넌트 일시중지 (결제 미완료, 정책 위반 등)"""
        await self._emit(
            LifecycleEvent.BEFORE_SUSPEND,
            tenant_id=tenant_id,
            reason=reason
        )

        async with self.db.get_central_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant not found: {tenant_id}")

            tenant.status = TenantStatus.SUSPENDED
            if reason:
                tenant.config = tenant.config or {}
                tenant.config["suspend_reason"] = reason
                tenant.config["suspended_at"] = datetime.utcnow().isoformat()

            await session.commit()
            await session.refresh(tenant)

        await self._emit(LifecycleEvent.AFTER_SUSPEND, tenant=tenant)
        logger.info(f"Tenant suspended: {tenant_id}, reason: {reason}")

        return tenant

    # =========================================================================
    # 삭제 (Delete)
    # =========================================================================

    async def delete(
        self,
        tenant_id: str,
        hard_delete: bool = False,
        preserve_data_days: int = 30
    ) -> None:
        """
        테넌트 삭제

        Args:
            tenant_id: 테넌트 ID
            hard_delete: True면 즉시 물리 삭제
            preserve_data_days: 데이터 보존 기간 (soft delete 시)
        """
        await self._emit(
            LifecycleEvent.BEFORE_DELETE,
            tenant_id=tenant_id,
            hard_delete=hard_delete
        )

        async with self.db.get_central_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()

            if not tenant:
                raise ValueError(f"Tenant not found: {tenant_id}")

            if hard_delete:
                # 물리 삭제
                await session.delete(tenant)
            else:
                # 논리 삭제
                tenant.status = TenantStatus.DELETED
                tenant.config = tenant.config or {}
                tenant.config["deleted_at"] = datetime.utcnow().isoformat()
                tenant.config["data_retention_until"] = (
                    datetime.utcnow() + timedelta(days=preserve_data_days)
                ).isoformat()

            await session.commit()

        await self._emit(
            LifecycleEvent.AFTER_DELETE,
            tenant_id=tenant_id,
            hard_delete=hard_delete
        )
        logger.info(f"Tenant deleted: {tenant_id}, hard_delete={hard_delete}")

    # =========================================================================
    # 조회
    # =========================================================================

    async def get(self, tenant_id: str) -> Optional[Tenant]:
        """테넌트 조회"""
        async with self.db.get_central_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            return result.scalar_one_or_none()

    async def list(
        self,
        status: Optional[TenantStatus] = None,
        service_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Tenant]:
        """테넌트 목록 조회"""
        async with self.db.get_central_session() as session:
            from sqlalchemy import select
            query = select(Tenant)

            if status:
                query = query.where(Tenant.status == status)
            if service_type:
                query = query.where(Tenant.service_type == service_type)

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            return result.scalars().all()
