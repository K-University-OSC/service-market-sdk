# Service Market SDK (mt_paas)

> 서비스 마켓 연동을 위한 멀티테넌트 PaaS SDK

## 개요

**mt_paas**는 Service Market과 개별 서비스 간의 연동을 위한 SDK입니다.

다음 3가지를 제공합니다:

| 구성 | 설명 |
|------|------|
| **표준 인터페이스(규약)** | Service Market ↔ 서비스 간 요청/응답 형식 표준화 |
| **샌드박스** | 실제 Service Market 없이 연동을 개발/테스트할 수 있는 환경 |
| **공통 모듈** | 서비스들이 선택적으로 가져다 쓸 수 있는 라이브러리 |

SDK 자체가 테넌트를 생성해주는 것이 아니라, **"어떤 형식으로 요청하고 응답할지"** 를 표준화하고, 개발에 필요한 도구를 함께 제공합니다.

```
service-market-sdk/
│
├── 규약 (standard_api/)          ← 필수: 모든 서비스가 따라야 하는 인터페이스
│
├── 샌드박스 (sandbox/)           ← 개발용: 실제 Service Market 없이 테스트
│
└── 공통 모듈 (core, middleware/)  ← 선택: 가져다 쓰면 편한 라이브러리
```

### 왜 필요한가?

```
문제: 서비스마다 연동 방식이 제각각

  Service Market ──→ Advisor   (POST /webhook, X-Key 인증)
  Service Market ──→ Chatbot   (POST /create, 인증 없음)
                                ↑ 형식, 경로, 인증 방식이 모두 다름

해결: SDK로 표준 규약 통일

  Service Market ──→ Advisor   (POST /mt/tenant/{id}/activate, X-Market-API-Key)
  Service Market ──→ Chatbot   (POST /mt/tenant/{id}/activate, X-Market-API-Key)
                                ↑ 모든 서비스가 같은 형식으로 동작
```

## 설치

```bash
# wheel 파일로 설치
pip install mt_paas-0.1.0-py3-none-any.whl

# 개발 모드 설치
pip install -e /path/to/service-market-sdk
```

**요구 사항:** Python 3.10+

## 빠른 시작

### 1단계: 핸들러 구현

서비스에 맞는 테넌트 관리 로직을 작성합니다.

```python
from mt_paas.standard_api import (
    StandardAPIHandlerV2,
    ActivateRequest, ActivateResponse,
    DeactivateRequest, DeactivateResponse,
    StatusResponse, UsageResponse,
)

class MyHandler(StandardAPIHandlerV2):

    @property
    def base_url(self) -> str:
        return "https://my-service.example.com"

    # 테넌트 활성화 (필수)
    async def activate_tenant(self, request: ActivateRequest) -> ActivateResponse:
        # DB에 테넌트 생성
        return ActivateResponse(
            success=True,
            tenant_id=request.tenant_id,
            access_url=f"{self.base_url}?tenant={request.tenant_id}",
            message="테넌트 생성 완료"
        )

    # 테넌트 비활성화 (필수)
    async def deactivate_tenant(self, tenant_id, request):
        # DB에서 테넌트 비활성화
        ...

    # 상태 조회 (필수)
    async def get_tenant_status(self, tenant_id) -> StatusResponse:
        ...

    # 사용량 조회 (필수)
    async def get_tenant_usage(self, tenant_id, period) -> UsageResponse:
        ...

    # 통계 조회 (필수)
    async def get_tenant_stats(self, tenant_id, period="30d"):
        ...

    # 비용 조회 (필수)
    async def get_tenant_costs(self, tenant_id, period="30d"):
        ...

    # 사용자 관리 (필수)
    async def list_users(self, tenant_id, filters=None):
        ...
    async def create_user(self, tenant_id, request):
        ...
    async def get_user(self, tenant_id, user_id):
        ...
    async def update_user(self, tenant_id, user_id, request):
        ...
    async def delete_user(self, tenant_id, user_id):
        ...

    # 설정 조회 (필수)
    async def get_settings(self, tenant_id):
        ...
```

### 2단계: 라우터 등록

한 줄로 표준 API 엔드포인트가 자동 생성됩니다.

```python
from fastapi import FastAPI
from mt_paas.standard_api import create_standard_router_v2

app = FastAPI()
handler = MyHandler()

router = create_standard_router_v2(
    handler=handler,
    prefix="/mt",
    api_key_header="X-Market-API-Key",
    api_key_env="MARKET_API_KEY",
    require_auth=True,
)

app.include_router(router, prefix="/api/tenant/webhook")
```

### 3단계: Webhook 엔드포인트 추가

Service Market의 신청 승인 이벤트를 수신합니다.

```python
from fastapi import APIRouter, Header
from mt_paas.standard_api import ActivateRequest, ContactInfo

webhook = APIRouter()

@webhook.post("/application-approved")
async def handle_approved(request: dict, x_api_key: str = Header(...)):
    # 테넌트 생성
    result = await handler.activate_tenant(ActivateRequest(
        tenant_id=generate_tenant_id(request),
        tenant_name=request["applicant"]["university_name"],
        plan="demo",
        features=["ai_chat"],
        contact=ContactInfo(
            email=request["applicant"]["email"],
            name=request["applicant"]["name"]
        )
    ))
    return {"success": True, "tenant_id": result.tenant_id}

app.include_router(webhook, prefix="/api/tenant/webhook")
```

## 자동 생성되는 API 엔드포인트

`create_standard_router_v2()`를 사용하면 아래 엔드포인트가 자동 생성됩니다.

### 기본 API (v1)

| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/mt/health` | 서비스 상태 확인 |
| `POST` | `/mt/tenant/{id}/activate` | 테넌트 활성화 |
| `POST` | `/mt/tenant/{id}/deactivate` | 테넌트 비활성화 |
| `GET` | `/mt/tenant/{id}/status` | 테넌트 상태 조회 |
| `GET` | `/mt/tenant/{id}/usage` | 사용량 조회 |

### 대시보드 API (v2)

| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/mt/tenant/{id}/stats` | 통계 (대시보드용) |
| `GET` | `/mt/tenant/{id}/stats/costs` | 비용 분석 |
| `GET` | `/mt/tenant/{id}/stats/top-users` | 활성 사용자 순위 |

### 사용자 관리 API (v2)

| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/mt/tenant/{id}/users` | 사용자 목록 |
| `POST` | `/mt/tenant/{id}/users` | 사용자 생성 |
| `GET` | `/mt/tenant/{id}/users/{uid}` | 사용자 상세 |
| `PUT` | `/mt/tenant/{id}/users/{uid}` | 사용자 수정 |
| `DELETE` | `/mt/tenant/{id}/users/{uid}` | 사용자 삭제 |

### 설정/리소스 API (v2)

| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/mt/tenant/{id}/settings` | 설정 조회 |
| `PUT` | `/mt/tenant/{id}/settings` | 설정 수정 |
| `GET` | `/mt/tenant/{id}/resources` | 리소스 조회 |

## 주요 모듈

### 1. standard_api - 표준 인터페이스 (필수)

서비스가 구현해야 할 **핸들러 인터페이스**와 **자동 라우터**를 제공합니다.

```python
from mt_paas.standard_api import (
    # 핸들러
    StandardAPIHandlerV2,       # 서비스가 상속하여 구현
    create_standard_router_v2,  # 라우터 자동 생성

    # 요청/응답 모델 (v1)
    ActivateRequest, ActivateResponse,
    DeactivateRequest, DeactivateResponse,
    StatusResponse, UsageResponse, ContactInfo,

    # 대시보드 모델 (v2)
    StatsResponse, CostsResponse,
    TopUsersResponse,

    # 사용자 관리 모델 (v2)
    UserInfo, CreateUserRequest, CreateUserResponse,
    UpdateUserRequest, DeleteUserResponse,

    # 설정 모델 (v2)
    SettingsResponse, TenantConfig, FeatureFlags,
    SubscriptionInfo,

    # 에러
    TenantExistsError, TenantNotFoundError,
    UserExistsError, UserNotFoundError,
)
```

### 2. sandbox - 개발/테스트 환경

실제 Service Market 없이 연동을 개발하고 검증할 수 있는 환경입니다.

```
┌───────────────────────────────────────────────────────────────┐
│  sandbox/ (개발자의 로컬 환경)                                  │
│                                                                 │
│  ┌───────────────┐     ① Webhook 전송    ┌───────────────┐    │
│  │  시뮬레이터    │ ──────────────────→   │  내 서비스     │    │
│  │ (가짜 Service │   (실제와 동일한      │  (개발 중)     │    │
│  │  Market)      │    형식의 페이로드)   │                │    │
│  └───────┬───────┘                       └───────┬───────┘    │
│          │                                       │             │
│   ② 결과 저장                             ③ 응답 반환         │
│   (SQLite)                                (200 + JSON)        │
│          │                                       │             │
│          ▼                                       ▼             │
│  ┌───────────────┐                       ┌───────────────┐    │
│  │ 통계 대시보드  │                       │  SDK 테스터    │    │
│  │ - 성공률      │                       │ - 규약 검증    │    │
│  │ - 응답시간    │                       │ - 5개 항목     │    │
│  │ - 실패 원인   │                       │ - PASS/FAIL   │    │
│  └───────────────┘                       └───────────────┘    │
│                                                                 │
│  ┌───────────────┐                                             │
│  │ 예제 서비스    │  ← 참고용: 복사 후 자기 로직으로 교체       │
│  │(sample_service)│                                             │
│  └───────────────┘                                             │
└───────────────────────────────────────────────────────────────┘
```

#### Webhook 시뮬레이터 (`sandbox/simulator/`)

**실제 Service Market이 보내는 것과 동일한 Webhook을 대신 보내주는 가짜 Service Market**입니다.

```
실제 운영:     Service Market ──webhook──→ 서비스
개발/테스트:   시뮬레이터     ──webhook──→ 서비스  (동일한 형식)
```

- CLI/HTTP로 데모 신청, 서비스 신청 Webhook 전송
- 응답 결과(성공/실패, 응답시간)를 SQLite에 기록
- 통계 조회 (성공률, 평균 응답시간 등)

#### SDK 테스터 (`sandbox/sdk/`)

서비스가 **규약에 맞게 구현했는지 자동으로 검증**합니다.

| 테스트 | 검증 내용 |
|--------|----------|
| Health Check | `/health` 응답하는지 |
| 기본 Webhook | 데모 신청 보내면 200 응답하는지 |
| API Key 검증 | 잘못된 키로 보내면 401 거부하는지 |
| 응답 형식 | `status`, `tenant_id`, `tenant_url` 필드가 있는지 |
| 테넌트 재사용 | 같은 이메일로 두 번 보내면 같은 tenant_id 반환하는지 |

#### 예제 서비스 (`sandbox/sample_service/`)

**"이렇게 만들면 됩니다"** 를 보여주는 참고용 서비스입니다. 복사 후 자기 로직으로 교체하면 됩니다.

### 3. 공통 모듈 (선택)

서비스가 직접 만들기 번거로운 것들을 **가져다 쓸 수 있는** 라이브러리입니다. 사용 여부는 자유입니다.

#### 모듈 분류 및 대상

| 모듈 | 한줄 설명 | 누가 필요한가? | 언제 필요한가? |
|------|----------|--------------|--------------|
| **core** | 테넌트 DB 생성/관리/상태 전환 | 서비스 개발자 | 테넌트별 DB를 자동으로 만들고 관리하고 싶을 때 |
| **middleware** | 요청이 어느 대학교 것인지 자동 판별 | 서비스 개발자 | 하나의 서버에서 여러 대학교 요청을 구분해야 할 때 |
| **market** | 서비스의 표준 API를 호출하는 클라이언트 | Service Market 운영자 | Service Market에서 각 서비스를 제어할 때 |
| **config/setup** | 위 모듈들을 한 줄로 연결 | 서비스 개발자 | 위 공통 모듈들을 쓰기로 했을 때 |

```
┌─────────────────────────────────────────────────────────┐
│  공통 모듈 전체 구조                                      │
│                                                           │
│  서비스 개발자가 쓰는 것              SM 운영자가 쓰는 것  │
│  ┌─────────────────────┐            ┌─────────────────┐  │
│  │  config / setup      │            │  market          │  │
│  │  (한 줄 초기화)      │            │  (HTTP 클라이언트)│  │
│  └────────┬────────────┘            └────────┬────────┘  │
│           │ 내부에서 사용                      │           │
│     ┌─────┴─────┐                             │           │
│     ▼           ▼                             ▼           │
│  ┌──────┐  ┌────────────┐           ┌─────────────────┐  │
│  │ core │  │ middleware  │           │ ServiceClient    │  │
│  │      │  │             │           │ - health_check() │  │
│  │ DB   │  │ 요청에서    │           │ - activate()     │  │
│  │ 관리 │  │ 테넌트 식별 │           │ - deactivate()   │  │
│  └──────┘  └────────────┘           │ - get_status()   │  │
│                                      │ - get_usage()    │  │
│                                      └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

#### core - 테넌트 DB 관리

서비스가 여러 대학교(테넌트)를 운영할 때, **테넌트별 DB를 자동으로 생성하고 관리**하는 모듈입니다.

**누가 쓰나?** → 서비스 개발자 (Advisor, LLM-chatbot 등)
**언제 쓰나?** → 대학교마다 별도 DB를 만들어서 데이터를 완전히 분리하고 싶을 때

```
┌─────────────────────────────────────────────────────────────────┐
│  core 모듈 동작 흐름                                              │
│                                                                    │
│  ┌──────────────────┐                                             │
│  │  DatabaseManager  │  "DB 연결을 관리하는 관리자"                │
│  │                   │                                             │
│  │  - 중앙 DB 연결    │  ← 테넌트 목록, 구독 정보 저장             │
│  │  - 테넌트 DB 생성  │  ← CREATE DATABASE tenant_한림대            │
│  │  - 테넌트 DB 연결  │  ← 대학교별 DB에 자동 연결                  │
│  └────────┬─────────┘                                             │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────┐     ┌──────────────────┐                    │
│  │  TenantManager    │     │  TenantLifecycle  │                    │
│  │  "테넌트 CRUD"    │     │  "상태 전환 + 훅" │                    │
│  │                   │     │                   │                    │
│  │  - 생성 (create)  │     │  상태 흐름:       │                    │
│  │  - 조회 (get)     │     │  PENDING          │                    │
│  │  - 수정 (update)  │     │    ↓ provision()  │                    │
│  │  - 삭제 (delete)  │     │  PROVISIONING     │                    │
│  │  - 목록 (list)    │     │    ↓              │                    │
│  └──────────────────┘     │  ACTIVE ←─────┐  │                    │
│                            │    ↓          │  │                    │
│                            │  SUSPENDED ───┘  │                    │
│                            │    ↓  activate() │                    │
│                            │  DELETED         │                    │
│                            │                   │                    │
│                            │  이벤트 훅:       │                    │
│                            │  상태 변경 시     │                    │
│                            │  → 이메일 발송    │                    │
│                            │  → 로그 기록      │                    │
│                            │  → 알림 전송      │                    │
│                            └──────────────────┘                    │
│                                                                    │
│  DB 구조:                                                          │
│  ┌─────────────┐    ┌────────────┐  ┌────────────┐  ┌──────────┐ │
│  │  중앙 DB      │    │ tenant_한림 │  │ tenant_광주 │  │ tenant_N │ │
│  │ (테넌트 목록) │    │ (한림대 전용)│  │ (광서대 전용)│  │ (N대 전용)│ │
│  │ - tenants    │    │ - 채팅 기록 │  │ - 채팅 기록 │  │ - ...    │ │
│  │ - 구독 정보  │    │ - 문서      │  │ - 문서      │  │          │ │
│  │ - 사용 로그  │    │ - 사용자    │  │ - 사용자    │  │          │ │
│  └─────────────┘    └────────────┘  └────────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**주요 구성:**

| 클래스 | 역할 | 주요 기능 |
|--------|------|----------|
| **DatabaseManager** | DB 연결 관리자 | 중앙 DB 연결, 테넌트별 DB 자동 생성 (`CREATE DATABASE`), 테넌트별 DB 연결 풀 관리 |
| **TenantManager** | 테넌트 CRUD | 테넌트 생성/조회/수정/삭제, 구독 정보 관리, 목록 필터링/페이징 |
| **TenantLifecycle** | 상태 전환 + 이벤트 | 상태 전환 (PENDING→ACTIVE→SUSPENDED→DELETED), 상태 변경 시 이벤트 훅 실행 |

```python
from mt_paas.core import TenantManager, TenantLifecycle, DatabaseManager, LifecycleEvent

# 상태 전환 시 자동으로 이메일 발송 (이벤트 훅)
lifecycle.on(LifecycleEvent.AFTER_ACTIVATE,
    lambda tenant: send_email(tenant.admin_email, "서비스가 활성화되었습니다"))

lifecycle.on(LifecycleEvent.AFTER_SUSPEND,
    lambda tenant: send_email(tenant.admin_email, "서비스가 일시 중단되었습니다"))
```

---

#### middleware - 요청에서 테넌트 자동 식별

하나의 서버에서 여러 대학교 요청을 처리할 때, **"이 요청이 어느 대학교 것인지"** 자동으로 판별해주는 모듈입니다.

**누가 쓰나?** → 서비스 개발자
**언제 쓰나?** → 하나의 서버(하나의 코드)로 여러 대학교를 동시에 서비스할 때

```
┌──────────────────────────────────────────────────────────────┐
│  middleware 동작 흐름                                          │
│                                                                │
│  한림대 사용자 ──→ GET /data                                   │
│                    헤더: X-Tenant-ID: hallym                   │
│                         │                                      │
│  광서대 사용자 ──→ GET /data                                   │
│                    URL: /tenant/gwangju/data                   │
│                         │                                      │
│  울서대 사용자 ──→ GET /data                                   │
│                    URL: seoul.service.com/data                 │
│                         │                                      │
│                         ▼                                      │
│              ┌─────────────────────┐                           │
│              │  TenantMiddleware    │                           │
│              │                     │                           │
│              │  식별 순서:          │                           │
│              │  ① X-Tenant-ID 헤더 │ ← 가장 우선               │
│              │  ② URL 경로 분석    │ ← /tenant/{id}/...        │
│              │  ③ 쿼리 파라미터    │ ← ?tenant_id=xxx          │
│              │  ④ 서브도메인 분석  │ ← xxx.service.com         │
│              └────────┬────────────┘                           │
│                       │                                        │
│                       ▼                                        │
│              ┌─────────────────────┐                           │
│              │  TenantContext 생성  │                           │
│              │                     │                           │
│              │  tenant_id: "hallym"│                           │
│              │  plan: "standard"   │                           │
│              │  features:          │                           │
│              │    rag: true        │                           │
│              │    chat: true       │                           │
│              └────────┬────────────┘                           │
│                       │                                        │
│                       ▼                                        │
│              ┌─────────────────────┐                           │
│              │  API 핸들러에서 사용  │                           │
│              │                     │                           │
│              │  @router.get("/data")│                           │
│              │  async def get_data( │                           │
│              │    tenant = Depends( │                           │
│              │      require_tenant) │                           │
│              │  ):                  │                           │
│              │    # tenant.id       │                           │
│              │    # → "hallym"      │                           │
│              └─────────────────────┘                           │
└──────────────────────────────────────────────────────────────┘
```

**주요 구성:**

| 클래스/함수 | 역할 |
|------------|------|
| **TenantMiddleware** | 모든 HTTP 요청을 가로채서 테넌트 ID를 추출하고 컨텍스트에 저장 |
| **TenantContext** | 식별된 테넌트 정보 (ID, 요금제, 기능 목록, 설정) |
| **get_current_tenant()** | 현재 요청의 테넌트 정보를 가져오는 함수 |
| **require_tenant()** | 테넌트 정보가 없으면 401 에러를 반환하는 FastAPI 의존성 |
| **optional_tenant()** | 테넌트 정보가 없어도 통과하는 FastAPI 의존성 |

```python
from mt_paas.middleware import TenantMiddleware, get_current_tenant

app.add_middleware(TenantMiddleware, header_name="X-Tenant-ID")

@router.get("/data")
async def get_data(tenant = Depends(get_current_tenant)):
    print(tenant.id)       # "hallym"
    print(tenant.plan)     # "standard"
    if tenant.has_feature("rag"):
        # RAG 기능이 활성화된 대학교만 사용 가능
        ...
```

---

#### market - Service Market 호출 클라이언트

**Service Market이 각 서비스의 표준 API를 호출**할 때 사용하는 HTTP 클라이언트입니다.

**누가 쓰나?** → **Service Market 운영자** (서비스 개발자가 아님!)
**언제 쓰나?** → Service Market에서 여러 서비스의 상태 확인, 테넌트 활성화/비활성화, 사용량 조회 등을 할 때

```
┌──────────────────────────────────────────────────────────────┐
│  market 모듈 동작 흐름                                        │
│                                                                │
│  ┌──────────────────────────────────────┐                     │
│  │  Service Market (운영 시스템)          │                     │
│  │                                       │                     │
│  │  ┌──────────────────────────────┐    │                     │
│  │  │  ServiceMarketClient          │    │                     │
│  │  │  (여러 서비스를 한번에 관리)    │    │                     │
│  │  │                               │    │                     │
│  │  │  등록된 서비스:                │    │                     │
│  │  │   ├─ advisor (ServiceClient)  │    │                     │
│  │  │   └─ chatbot (ServiceClient)  │    │                     │
│  │  └──────────┬───────────────────┘    │                     │
│  └─────────────┼────────────────────────┘                     │
│                │                                               │
│       ┌────────┼────────┐                                     │
│       ▼        ▼        ▼                                     │
│  ┌────────┐  ┌────────┐                                      │
│  │Advisor │  │Chatbot │    ← 각 서비스                        │
│  │        │  │        │                                        │
│  │/mt/    │  │/mt/    │    ← 표준 API (규약대로)              │
│  │health  │  │health  │                                        │
│  │tenant/ │  │tenant/ │                                        │
│  │activate│  │...     │                                        │
│  └────────┘  └────────┘                                      │
│                                                                │
│  호출 가능한 기능:                                             │
│  ┌────────────────────────────────────────────────┐           │
│  │ health_check_all()  → 모든 서비스 상태 한번에 확인 │           │
│  │ activate_tenant()   → 특정 서비스에 테넌트 생성   │           │
│  │ deactivate_tenant() → 특정 서비스에서 테넌트 제거 │           │
│  │ get_all_usage()     → 모든 서비스의 사용량 수집   │           │
│  │ get_billing_usage() → 과금 데이터 조회            │           │
│  │ get_billing_detail()→ 상세 청구 내역              │           │
│  └────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────┘
```

**주요 구성:**

| 클래스 | 역할 | 누가 쓰나 |
|--------|------|----------|
| **ServiceClient** | 개별 서비스 1개의 표준 API를 호출하는 클라이언트 | Service Market |
| **ServiceMarketClient** | 여러 ServiceClient를 등록하고 한번에 관리 | Service Market |

```python
from mt_paas.market import ServiceMarketClient

# Service Market에서 여러 서비스를 등록
smc = ServiceMarketClient()
smc.register_service("advisor", base_url="http://...:10300", api_key="key1")
smc.register_service("chatbot", base_url="http://...:10200", api_key="key2")

# 모든 서비스 상태 확인
results = await smc.health_check_all()
# → {"advisor": {"status": "healthy"}, "chatbot": {"status": "healthy"}}

# 특정 서비스에 테넌트 활성화
await smc.activate_tenant("advisor", TenantActivation(
    tenant_id="hallym", tenant_name="한림대학교", plan="standard"
))
```

---

#### config / setup - 설정 및 한 줄 초기화

위의 core + middleware 모듈을 **한 줄로 FastAPI 앱에 연결**하는 헬퍼입니다.

**누가 쓰나?** → 서비스 개발자 (core, middleware를 쓰기로 했을 때)

```
┌──────────────────────────────────────────────────────────────┐
│  setup_multi_tenant() 이 한 줄이 하는 일                      │
│                                                                │
│  setup_multi_tenant(app, central_db_url="postgresql://...")    │
│       │                                                        │
│       ├─→ ① DatabaseManager 생성 (DB 연결 설정)               │
│       ├─→ ② TenantManager 생성 (테넌트 CRUD 준비)             │
│       ├─→ ③ TenantLifecycle 생성 (상태 전환 준비)              │
│       ├─→ ④ TenantMiddleware 추가 (요청별 테넌트 식별)         │
│       └─→ ⑤ app.state에 저장 (어디서든 꺼내 쓸 수 있게)       │
│                                                                │
│  config (환경 변수):                                           │
│  ┌────────────────────────────────────────────┐               │
│  │ MT_DB_HOST=localhost    DB 접속 정보        │               │
│  │ MT_DB_PORT=5432                             │               │
│  │ MT_DB_USER=postgres                         │               │
│  │ MT_DB_PASSWORD=secret                       │               │
│  │ MT_DB_NAME=central_db                       │               │
│  │ MT_REDIS_HOST=localhost  Redis 접속 정보     │               │
│  │ MT_API_PORT=11000        포트 설정           │               │
│  │ MARKET_API_KEY=xxx       인증 키             │               │
│  └────────────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────────┘
```

```python
from mt_paas import setup_multi_tenant

app = FastAPI()

# 이 한 줄로 core + middleware 전체 연결
mt = setup_multi_tenant(app, central_db_url="postgresql://...")

@app.on_event("startup")
async def startup():
    await mt.init()      # DB 연결 시작

@app.on_event("shutdown")
async def shutdown():
    await mt.close()     # DB 연결 정리
```

---

#### 공통 모듈 사용 판단 가이드

```
"우리 서비스에 공통 모듈이 필요한가?"

Q1. 대학교마다 별도 DB를 만들어야 하나?
    ├─ YES → core 모듈 사용
    └─ NO  → core 불필요 (자체 DB 관리)

Q2. 하나의 서버에서 여러 대학교를 구분해야 하나?
    ├─ YES → middleware 모듈 사용
    └─ NO  → middleware 불필요

Q3. Service Market에서 여러 서비스를 제어해야 하나?
    ├─ YES → market 모듈 사용 (SM 운영자용)
    └─ NO  → market 불필요

Q4. 위에서 core나 middleware를 쓰기로 했나?
    ├─ YES → config/setup으로 한 줄 초기화
    └─ NO  → config/setup 불필요

※ 표준 인터페이스(규약)만 필수이고, 공통 모듈은 모두 선택입니다.
※ 자체 구현이 이미 있다면 공통 모듈 대신 자체 구현을 사용해도 됩니다.
```

## 연동 흐름

```
┌──────────────┐     ① 서비스 신청      ┌──────────────┐
│  대학 담당자  │ ──────────────────────→ │Service Market│
│  (광서대학교) │                         │  (8501 포트)  │
└──────────────┘                         └──────┬───────┘
                                                │
                                         ② 관리자 승인
                                                │
                                                ▼
                                    ③ Webhook 호출 (HTTP POST)
                                    payload: {applicant, service, ...}
                                                │
                                                ▼
                                  ┌─────────────────────────┐
                                  │     서비스 (Advisor)      │
                                  │     (10300 포트)          │
                                  │                           │
                                  │  ④ SDK 핸들러 실행        │
                                  │    → 테넌트 DB 생성       │
                                  │    → 관리자 계정 생성     │
                                  │    → 접속 URL 반환        │
                                  └─────────────────────────┘
                                                │
                                         ⑤ 결과 콜백
                                                │
                                                ▼
┌──────────────┐     ⑥ 접속 정보 전달    ┌──────────────┐
│  대학 담당자  │ ←────────────────────── │Service Market│
│  (광서대학교) │                         │              │
└──────────────┘                         └──────────────┘
```

## 디렉토리 구조

```
service-market-sdk/
│
├── mt_paas/                        # 메인 패키지
│   │
│   ├── standard_api/               # [필수] 표준 인터페이스 (규약)
│   │   ├── handler.py / handler_v2.py   # 서비스가 구현할 핸들러 인터페이스
│   │   ├── router.py / router_v2.py     # 핸들러 → API 엔드포인트 자동 생성
│   │   └── models.py / models_v2.py     # 요청/응답 데이터 형식 정의
│   │
│   ├── core/                       # [선택] 공통 모듈 - 테넌트 DB 관리
│   │   ├── manager.py              #   테넌트 CRUD
│   │   ├── lifecycle.py            #   상태 전환 + 이벤트 훅
│   │   ├── database.py             #   중앙DB + 테넌트별 DB 연결 풀
│   │   ├── models.py               #   Tenant, Subscription ORM 모델
│   │   └── schemas.py              #   Pydantic 스키마
│   │
│   ├── middleware/                  # [선택] 공통 모듈 - 요청별 테넌트 식별
│   │   └── tenant.py               #   헤더/URL/서브도메인에서 테넌트 판별
│   │
│   ├── market/                     # [선택] 공통 모듈 - HTTP 클라이언트
│   │   ├── client.py               #   ServiceClient, ServiceMarketClient
│   │   └── models.py               #   ServiceInfo, UsageReport
│   │
│   ├── config.py                   # [선택] 환경 변수 기반 설정
│   └── setup.py                    # [선택] FastAPI 한 줄 초기화 헬퍼
│
├── sandbox/                        # 개발/테스트 환경
│   ├── simulator/                  #   가짜 Service Market (Webhook 전송)
│   ├── sdk/                        #   규약 준수 자동 검증 (5개 항목)
│   └── sample_service/             #   참고용 예제 서비스
│
├── tests/                          # 테스트
├── docs/                           # 문서
├── dist/                           # 빌드 산출물 (.whl)
└── pyproject.toml                  # 패키지 설정
```

## 테스트

```bash
# 전체 테스트 실행
pytest tests/

# 특정 테스트
pytest tests/test_standard_api_v2.py -v

# 커버리지
pytest --cov=mt_paas tests/
```

## 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `MARKET_API_KEY` | Service Market 인증 API Key | - |
| `MT_DB_HOST` | 중앙 DB 호스트 | `localhost` |
| `MT_DB_PORT` | 중앙 DB 포트 | `5432` |
| `MT_DB_USER` | DB 사용자 | - |
| `MT_DB_PASSWORD` | DB 비밀번호 | - |
| `MT_DB_NAME` | 중앙 DB 이름 | - |

## 관련 문서

- [Service Market 연동 흐름](docs/SERVICE_MARKET_INTEGRATION_FLOW_20260204.md)

## 문의

- **Email:** aios@hallym.ac.kr
- **Managed by:** 한림대학교 AI 에듀테크 센터

---
© 2026 Hallym University AI EdTech Center. Licensed under MIT.
