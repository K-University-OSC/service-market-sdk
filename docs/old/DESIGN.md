# Multi-Tenant PaaS 설계 문서

> keli_tutor + service_market 연동을 위한 공통 멀티테넌트 플랫폼 설계

**작성일**: 2026-01-03
**버전**: 0.1 (Draft)
**검토 상태**: 컨설팅 대기

---

## 1. 배경 및 목표

### 1.1 현재 상황

```
현재 아키텍처:
┌────────────────────────────────────────────────────────────┐
│                    service_market                           │
│                  (market.k-university.ai)                   │
│                                                             │
│  - 테넌트 생성/삭제 API                                      │
│  - 구독 관리                                                 │
│  - Docker-Per-Tenant 프로비저닝                              │
│  - 포트 할당 (10100~10199, 10200~10299, ...)                │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼ (docker-compose 템플릿 기반 프로비저닝)
┌────────────────────────────────────────────────────────────┐
│                      keli_tutor                             │
│               (각 테넌트별 독립 컨테이너)                     │
│                                                             │
│  테넌트 A (hallym_univ)     테넌트 B (snu_univ)             │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │ Frontend: 10100  │      │ Frontend: 10200  │            │
│  │ Backend:  10101  │      │ Backend:  10201  │            │
│  │ DB:       10102  │      │ DB:       10202  │            │
│  │ Redis:    10103  │      │ Redis:    10203  │            │
│  │ Chroma:   10104  │      │ Chroma:   10204  │            │
│  └──────────────────┘      └──────────────────┘            │
└────────────────────────────────────────────────────────────┘
```

**장점**:
- 완전한 격리 (컨테이너 단위)
- 테넌트별 독립 배포 가능
- 장애 격리 우수

**단점**:
- 리소스 오버헤드 (테넌트당 7개 컨테이너)
- 포트 관리 복잡
- 새 서비스 추가 시 동일 구조 반복 필요

### 1.2 목표

1. **공통 플랫폼 모듈 제공**: 새 서비스가 쉽게 멀티테넌트 기능을 사용할 수 있도록
2. **keli_tutor 우선 적용**: 기존 Docker-Per-Tenant 방식 유지하면서 공통 모듈 활용
3. **service_market 연동 강화**: 프로비저닝, 상태 동기화 자동화
4. **포트 범위**: 10100~10200 사용 (multi_tenant_paas 전용)

---

## 2. 제안 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    service_market                            │
│                     (포트: 8505)                             │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Tenant API  │  │ 구독 관리   │  │ 프로비저닝   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ REST API 연동
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  multi_tenant_paas                           │
│                   (라이브러리)                                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ mt_paas 패키지                                        │  │
│  │                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐   │  │
│  │  │ core/       │  │ middleware/ │  │ integrations│   │  │
│  │  │ - manager   │  │ - tenant    │  │ - marketplace│  │  │
│  │  │ - models    │  │ - auth      │  │ - billing   │   │  │
│  │  │ - lifecycle │  │             │  │             │   │  │
│  │  └─────────────┘  └─────────────┘  └────────────┘   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ pip install / import
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      keli_tutor                              │
│              (Docker-Per-Tenant 유지)                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ backend/server.py                                     │  │
│  │                                                       │  │
│  │   from mt_paas import setup_multi_tenant             │  │
│  │   from mt_paas.integrations import MarketplaceClient │  │
│  │                                                       │  │
│  │   # 기존 코드 유지 + 공통 모듈 활용                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 포트 할당 계획

```
multi_tenant_paas 전용 포트: 10100 ~ 10200

┌───────┬─────────────────────────────────────────────────────┐
│ 포트  │ 용도                                                │
├───────┼─────────────────────────────────────────────────────┤
│ 10100 │ PaaS 관리 API (선택적, 필요시)                       │
│ 10101 │ PaaS 헬스체크/모니터링                               │
│ 10102 │ 예약                                                 │
│ ...   │ ...                                                  │
│ 10110 │ 테스트 테넌트 1 - Frontend                           │
│ 10111 │ 테스트 테넌트 1 - Backend                            │
│ 10112 │ 테스트 테넌트 1 - DB                                 │
│ 10113 │ 테스트 테넌트 1 - Redis                              │
│ 10114 │ 테스트 테넌트 1 - Chroma                             │
│ ...   │ ...                                                  │
│ 10120 │ 테스트 테넌트 2 - Frontend                           │
│ ...   │ ...                                                  │
│ 10200 │ 예약 (마지막)                                        │
└───────┴─────────────────────────────────────────────────────┘

기존 keli_tutor 테넌트 포트: 10200~ (기존 service_market 규칙 유지)
```

---

## 3. 핵심 컴포넌트 설계

### 3.1 mt_paas.core.TenantManager

**역할**: 테넌트 생명주기 관리

```python
class TenantManager:
    """
    테넌트 관리의 핵심 클래스

    주요 기능:
    1. 테넌트 CRUD
    2. 테넌트별 DB 세션 관리
    3. 상태 전이 관리
    4. Marketplace 동기화
    """

    async def onboard_tenant(
        self,
        tenant_id: str,
        name: str,
        service_type: str = "keli_tutor",
        config: dict = None
    ) -> Tenant:
        """
        새 테넌트 온보딩

        1. Central DB에 테넌트 레코드 생성
        2. 상태: PENDING
        3. (Docker-Per-Tenant의 경우) 포트 할당 요청
        """
        pass

    async def provision_tenant(self, tenant_id: str) -> bool:
        """
        테넌트 프로비저닝

        1. 상태: PENDING → PROVISIONING
        2. service_market API 호출하여 Docker 컨테이너 생성
        3. 헬스체크 대기
        4. 상태: PROVISIONING → ACTIVE
        """
        pass

    async def get_tenant_session(self, tenant_id: str) -> AsyncSession:
        """
        테넌트 전용 DB 세션 반환

        Docker-Per-Tenant: 해당 테넌트 컨테이너의 DB에 연결
        Database-Per-Tenant: 해당 테넌트 DB에 연결
        """
        pass
```

### 3.2 mt_paas.middleware.TenantMiddleware

**역할**: 요청에서 테넌트 식별

```python
class TenantMiddleware:
    """
    FastAPI 미들웨어 - 모든 요청에서 테넌트 정보 추출

    추출 순서:
    1. HTTP 헤더 (X-Tenant-ID)
    2. JWT 토큰의 tenant_id 클레임
    3. 요청 URL의 서브도메인
    4. 쿼리 파라미터 (?tenant_id=xxx)
    """

    def __init__(
        self,
        tenant_manager: TenantManager,
        header_name: str = "X-Tenant-ID",
        extract_from_jwt: bool = True,
        extract_from_subdomain: bool = True,
    ):
        pass

    async def dispatch(self, request: Request, call_next):
        """
        1. 테넌트 ID 추출
        2. 테넌트 정보 로드
        3. request.state.tenant에 저장
        4. 다음 핸들러 호출
        """
        pass
```

### 3.3 mt_paas.integrations.MarketplaceClient

**역할**: service_market과의 API 연동

```python
class MarketplaceClient:
    """
    Service Marketplace API 클라이언트

    service_market의 API를 호출하여:
    - 테넌트 상태 동기화
    - 프로비저닝 요청
    - 사용량 보고
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8505/api/v1",
        api_key: str = None,
    ):
        self.api_url = api_url
        self.api_key = api_key

    async def get_tenant(self, tenant_id: str) -> dict:
        """GET /tenants/{tenant_id}"""
        pass

    async def request_provisioning(self, tenant_id: str) -> dict:
        """POST /tenants/{tenant_id}/provision"""
        pass

    async def sync_tenant_status(
        self,
        tenant_id: str,
        status: TenantStatus
    ) -> bool:
        """PATCH /tenants/{tenant_id}/status"""
        pass

    async def report_usage(
        self,
        tenant_id: str,
        usage: dict
    ) -> bool:
        """POST /tenants/{tenant_id}/usage"""
        pass
```

---

## 4. keli_tutor 연동 방안

### 4.1 현재 keli_tutor 구조

```
keli_tutor/
├── backend/
│   ├── server.py          # FastAPI 앱
│   ├── routers/           # API 라우터
│   ├── config.py          # 설정 (환경변수 기반)
│   └── ...
├── frontend/
│   └── ...
└── docker/
    └── docker-compose.yml
```

### 4.2 연동 후 변경 사항

**최소 변경 원칙**: 기존 코드 최대한 유지

#### 4.2.1 backend/server.py 변경

```python
# 기존 코드
from fastapi import FastAPI
app = FastAPI()

# 추가 (선택적)
from mt_paas.integrations import MarketplaceClient

# Marketplace 클라이언트 초기화 (선택적)
marketplace = MarketplaceClient(
    api_url=os.getenv("MARKETPLACE_API_URL", "http://localhost:8505/api/v1"),
    api_key=os.getenv("MARKETPLACE_TENANT_API_KEY")
)

# 헬스체크에 Marketplace 동기화 추가
@app.get("/health")
async def health():
    # 기존 헬스체크 로직
    status = await check_services()

    # Marketplace에 상태 보고 (선택적)
    if marketplace:
        await marketplace.sync_tenant_status(
            tenant_id=os.getenv("TENANT_ID"),
            status="active" if status["healthy"] else "unhealthy"
        )

    return status
```

#### 4.2.2 환경변수 추가

```bash
# .env 파일에 추가
MARKETPLACE_API_URL=http://localhost:8505/api/v1
MARKETPLACE_TENANT_API_KEY=xxx
TENANT_ID=hallym_univ
```

### 4.3 변경 없이 사용 가능한 기능

mt_paas의 일부 기능은 keli_tutor 코드 변경 없이도 활용 가능:

1. **service_market에서 사용**:
   - 프로비저닝 로직에서 mt_paas 활용
   - 테넌트 상태 관리

2. **모니터링 도구**:
   - mt_paas CLI로 테넌트 상태 조회
   - 헬스체크 자동화

---

## 5. service_market 연동 방안

### 5.1 현재 service_market 구조

```
service_market/
├── backend/
│   └── app/
│       ├── api/v1/
│       │   ├── tenants.py      # 테넌트 API
│       │   └── subscriptions.py
│       ├── services/
│       │   └── tenant_provisioner.py  # 프로비저닝
│       └── ...
├── tenant-templates/
│   └── keli_tutor/
│       ├── docker-compose.template.yml
│       └── .env.template
└── ...
```

### 5.2 연동 후 변경 사항

#### 5.2.1 TenantProvisioner 개선

```python
# 기존: service_market/backend/app/services/tenant_provisioner.py
class TenantProvisioner:
    async def provision(self, tenant_id: str):
        # 템플릿 복사
        # docker-compose.yml 생성
        # docker-compose up -d
        pass

# 개선: mt_paas 활용
from mt_paas.core import TenantManager, TenantLifecycle
from mt_paas.core.models import TenantStatus

class TenantProvisioner:
    def __init__(self, tenant_manager: TenantManager):
        self.tenant_manager = tenant_manager
        self.lifecycle = TenantLifecycle(tenant_manager)

    async def provision(self, tenant_id: str):
        # 상태 전이 관리 (mt_paas)
        async with self.lifecycle.provisioning(tenant_id):
            # 기존 프로비저닝 로직
            await self._create_docker_env(tenant_id)
            await self._start_containers(tenant_id)
            await self._wait_for_health(tenant_id)
```

### 5.3 API 변경 없음

- 기존 service_market API는 그대로 유지
- 내부 구현만 mt_paas 활용으로 개선

---

## 6. 구현 단계

### Phase 1: 기반 구축 (현재)

- [x] 프로젝트 구조 생성 (`~/workspace/multi_tenant_paas`)
- [x] pyproject.toml 설정
- [ ] 핵심 모델 구현 (Tenant, Subscription)
- [ ] TenantManager 기본 구현
- [ ] MarketplaceClient 구현

### Phase 2: service_market 연동

- [ ] service_market의 TenantProvisioner에 mt_paas 적용
- [ ] 테넌트 상태 동기화 구현
- [ ] 포트 할당 로직 통합

### Phase 3: keli_tutor 연동 (선택)

- [ ] keli_tutor에서 mt_paas import 테스트
- [ ] 헬스체크에 Marketplace 동기화 추가
- [ ] 사용량 보고 기능 추가

### Phase 4: 테스트 및 검증

- [ ] 10100~10200 포트로 테스트 테넌트 생성
- [ ] 프로비저닝 테스트
- [ ] 상태 동기화 테스트

---

## 7. 검토 요청 사항

### Q1: 아키텍처 방향

현재 Docker-Per-Tenant 방식을 유지하면서 공통 모듈을 추가하는 방향인데,
이 접근이 적절한가요? 아니면 다른 방식을 고려해야 할까요?

**옵션들**:
1. **현재 제안**: Docker-Per-Tenant 유지 + 공통 모듈 (최소 변경)
2. **Database-Per-Tenant 전환**: 리소스 효율적이나 대규모 변경 필요
3. **하이브리드**: 서비스별로 다른 방식 적용

### Q2: 포트 할당

10100~10200 범위가 적절한가요?
- 현재 10020~10033이 AI_TA_Phase2에서 사용 중
- 기존 keli_tutor 테넌트는 10200~에서 시작

### Q3: keli_tutor 변경 범위

keli_tutor 코드 변경을 최소화하고 싶은데,
어느 수준까지 연동하면 좋을까요?

**옵션들**:
1. **변경 없음**: service_market에서만 mt_paas 사용
2. **최소 변경**: 헬스체크에 상태 보고만 추가
3. **전체 연동**: 미들웨어, 인증 등 mt_paas 활용

### Q4: 우선순위

어떤 기능을 먼저 구현해야 할까요?
1. TenantManager (테넌트 생명주기)
2. MarketplaceClient (service_market 연동)
3. Middleware (요청 처리)
4. 기타

---

## 8. 첨부: 파일 구조

```
~/workspace/multi_tenant_paas/
├── README.md
├── pyproject.toml
├── docs/
│   └── DESIGN.md              ← 현재 문서
│
└── mt_paas/
    ├── __init__.py
    ├── setup.py
    │
    ├── core/
    │   ├── __init__.py
    │   ├── manager.py         # TenantManager
    │   ├── models.py          # Tenant, Subscription
    │   ├── schemas.py         # Pydantic 스키마
    │   ├── database.py        # DB 연결 관리
    │   └── lifecycle.py       # 상태 전이
    │
    ├── middleware/
    │   ├── __init__.py
    │   ├── tenant.py          # TenantMiddleware
    │   ├── auth.py            # 인증
    │   └── rate_limit.py      # 요금제별 제한
    │
    ├── integrations/
    │   ├── __init__.py
    │   ├── marketplace.py     # MarketplaceClient
    │   └── billing.py         # 과금
    │
    └── utils/
        ├── __init__.py
        ├── config.py          # 설정
        └── security.py        # 보안
```

---

**문서 끝**

피드백 및 질문은 이 문서에 코멘트해주세요.
