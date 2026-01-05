# Multi-Tenant PaaS

> Service Market에서 제공하는 공통 멀티테넌트 Platform as a Service

## 개요

이 모듈은 service_market에서 판매하는 여러 서비스(keli_tutor, llm_chatbot, advisor 등)가
공통으로 사용할 수 있는 멀티테넌트 인프라를 제공합니다.

### 왜 필요한가?

**기존 문제점:**
- 각 서비스마다 멀티테넌트 코드를 중복 구현
- llm_chatbot, advisor가 동일한 tenant_manager.py를 각각 보유
- 새 서비스 추가 시 복사-붙여넣기 필요
- 버그 수정이나 기능 개선 시 모든 서비스에 적용해야 함

**해결책:**
```
multi_tenant_paas/     ← 공통 PaaS 모듈
├── core/              ← 핵심 멀티테넌트 로직
├── providers/         ← LLM, Embedding 등 추상화
└── integrations/      ← 서비스별 연동 가이드

각 서비스는 이 모듈을 import해서 사용
```

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Marketplace                       │
│                  (market.k-university.ai)                   │
│         - 테넌트 생성/삭제, 구독 관리, 결제                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ API 연동
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Tenant PaaS                         │
│                   (이 모듈이 제공하는 것)                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Tenant Core  │  │  Providers   │  │  Middleware  │      │
│  │              │  │              │  │              │      │
│  │ - Manager    │  │ - LLM        │  │ - Auth       │      │
│  │ - Lifecycle  │  │ - Embedding  │  │ - Tenant ID  │      │
│  │ - DB Pool    │  │ - VectorDB   │  │ - Rate Limit │      │
│  │ - Migration  │  │ - Reranker   │  │ - Logging    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │ keli_tutor  │     │ llm_chatbot │     │   advisor   │
   │             │     │             │     │             │
   │ import      │     │ import      │     │ import      │
   │ multi_tenant│     │ multi_tenant│     │ multi_tenant│
   └─────────────┘     └─────────────┘     └─────────────┘
```

## 설치 및 사용

### 1. 설치 (pip)

```bash
# 로컬 개발용 (editable mode)
pip install -e /home/aiedu/workspace/multi_tenant_paas

# 또는 requirements.txt에 추가
# -e /home/aiedu/workspace/multi_tenant_paas
```

### 2. 서비스에서 사용

```python
# 기존 방식 (각 서비스마다 구현)
from database.tenant_manager import TenantManager  # ❌ 중복

# 새로운 방식 (공통 모듈 사용)
from multi_tenant.core import TenantManager        # ✅ 통일
from multi_tenant.middleware import TenantMiddleware
from multi_tenant.providers import LLMProvider, EmbeddingProvider
```

### 3. FastAPI 앱에 적용

```python
from fastapi import FastAPI
from multi_tenant import setup_multi_tenant

app = FastAPI()

# 한 줄로 멀티테넌트 설정 완료
setup_multi_tenant(
    app,
    central_db_url="postgresql://localhost/service_market",
    tenant_db_prefix="tenant_",
    enable_marketplace_sync=True  # service_market과 자동 동기화
)
```

## 주요 기능

### 1. Tenant Manager (테넌트 생명주기 관리)

```python
from multi_tenant.core import TenantManager

manager = TenantManager(central_db_url="...")

# 테넌트 온보딩
await manager.onboard_tenant(
    tenant_id="hallym_univ",
    name="한림대학교",
    config={"plan": "premium", "max_users": 500}
)

# 테넌트 DB 세션 가져오기
async with manager.get_tenant_session("hallym_univ") as session:
    result = await session.execute(select(User))
```

### 2. Middleware (요청별 테넌트 식별)

```python
from multi_tenant.middleware import TenantMiddleware

app.add_middleware(
    TenantMiddleware,
    header_name="X-Tenant-ID",      # 헤더에서 추출
    query_param="tenant_id",        # 또는 쿼리 파라미터
    extract_from_jwt=True           # 또는 JWT 토큰에서
)

# 라우터에서 사용
@router.get("/data")
async def get_data(tenant: Tenant = Depends(get_current_tenant)):
    # tenant.id, tenant.config 등 사용 가능
    pass
```

### 3. Provider Pattern (외부 서비스 추상화)

```python
from multi_tenant.providers import get_llm_provider, get_embedding_provider

# 테넌트 설정에 따라 자동으로 적절한 Provider 선택
llm = get_llm_provider(tenant_config)
embedding = get_embedding_provider(tenant_config)

# 사용
response = await llm.generate("질문입니다")
vectors = await embedding.embed(["텍스트1", "텍스트2"])
```

### 4. Service Marketplace 연동

```python
from multi_tenant.integrations import MarketplaceClient

client = MarketplaceClient(
    api_url="https://market.k-university.ai/api",
    api_key="..."
)

# 테넌트 상태 동기화
await client.sync_tenant_status("hallym_univ", status="active")

# 사용량 보고
await client.report_usage("hallym_univ", {
    "api_calls": 1500,
    "storage_mb": 250
})
```

## 디렉토리 구조

```
multi_tenant_paas/
├── README.md
├── pyproject.toml              # 패키지 설정
├── setup.py
│
├── mt_paas/                    # 메인 패키지
│   ├── __init__.py
│   │
│   ├── core/                   # 핵심 모듈
│   │   ├── __init__.py
│   │   ├── manager.py          # TenantManager
│   │   ├── lifecycle.py        # 온보딩/오프보딩
│   │   ├── models.py           # Tenant, Subscription 모델
│   │   ├── schemas.py          # Pydantic 스키마
│   │   └── database.py         # DB 연결 풀 관리
│   │
│   ├── middleware/             # FastAPI 미들웨어
│   │   ├── __init__.py
│   │   ├── tenant.py           # 테넌트 식별 미들웨어
│   │   ├── auth.py             # 인증 미들웨어
│   │   └── rate_limit.py       # 요금제별 Rate Limit
│   │
│   ├── providers/              # Provider 추상화
│   │   ├── __init__.py
│   │   ├── base.py             # 기본 인터페이스
│   │   ├── llm/                # LLM Providers
│   │   │   ├── openai.py
│   │   │   ├── claude.py
│   │   │   └── gemini.py
│   │   ├── embedding/          # Embedding Providers
│   │   │   ├── openai.py
│   │   │   └── local.py
│   │   ├── vectordb/           # Vector DB Providers
│   │   │   ├── qdrant.py
│   │   │   └── chroma.py
│   │   └── reranker/           # Reranker Providers
│   │       └── bge.py
│   │
│   ├── integrations/           # 외부 연동
│   │   ├── __init__.py
│   │   ├── marketplace.py      # Service Marketplace 연동
│   │   └── billing.py          # 과금 연동
│   │
│   └── utils/                  # 유틸리티
│       ├── __init__.py
│       ├── config.py           # 설정 관리
│       ├── logging.py          # 로깅
│       └── security.py         # 암호화, 키 관리
│
├── migrations/                 # Alembic 마이그레이션
│   └── versions/
│
├── tests/                      # 테스트
│   ├── test_manager.py
│   ├── test_middleware.py
│   └── test_providers.py
│
└── examples/                   # 사용 예제
    ├── basic_usage.py
    ├── fastapi_integration.py
    └── service_migration.py    # 기존 서비스 마이그레이션 가이드
```

## 기존 서비스 마이그레이션

### llm_chatbot 마이그레이션 예시

**Before (기존):**
```python
# llm_chatbot/backend/database/tenant_manager.py (자체 구현)
class TenantManager:
    ...

# llm_chatbot/backend/core/middleware/tenant.py (자체 구현)
class TenantMiddleware:
    ...
```

**After (마이그레이션 후):**
```python
# llm_chatbot/backend/database/tenant_manager.py
from multi_tenant.core import TenantManager  # 공통 모듈 사용

# llm_chatbot/backend/core/middleware/tenant.py
from multi_tenant.middleware import TenantMiddleware  # 공통 모듈 사용
```

## 로드맵

### Phase 1: Core 모듈 (현재)
- [x] 프로젝트 구조 설계
- [ ] TenantManager 구현
- [ ] Middleware 구현
- [ ] 기본 Provider 구현

### Phase 2: 서비스 연동
- [ ] llm_chatbot 마이그레이션
- [ ] advisor 마이그레이션
- [ ] keli_tutor 연동

### Phase 3: 고급 기능
- [ ] Service Marketplace 자동 동기화
- [ ] 사용량 기반 과금
- [ ] 테넌트별 리소스 제한

## 관련 문서

- [Service Marketplace 개발자 가이드](../service_market/docs/developer-guide-complete.md)
- [테넌트 온보딩 프로세스](../service_market/docs/tenant-onboarding-process.md)
