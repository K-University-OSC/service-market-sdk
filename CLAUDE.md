# Multi-Tenant PaaS (mt_paas) - Claude Code 가이드

> 공통 멀티테넌트 Platform as a Service 모듈

## 프로젝트 개요

mt_paas는 Service Market에서 판매하는 여러 서비스(keli_tutor, llm_chatbot, advisor 등)가
공통으로 사용할 수 있는 멀티테넌트 인프라를 제공하는 Python 라이브러리입니다.

### 핵심 가치
- **코드 중복 제거**: 각 서비스마다 tenant_manager.py 복사 불필요
- **표준화된 인터페이스**: 모든 서비스가 동일한 방식으로 테넌트 관리
- **중앙 집중식 개선**: 한 번 수정하면 모든 서비스에 적용

## 기술 스택

| 구분 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 프레임워크 | FastAPI (미들웨어), SQLAlchemy |
| DB | PostgreSQL, MySQL 지원 |
| AI | LangChain, OpenAI, Anthropic, Google AI |
| Vector DB | ChromaDB, Pinecone, Weaviate |
| 패키징 | Poetry, pyproject.toml |

## 디렉토리 구조

```
multi_tenant_paas/
├── mt_paas/
│   ├── core/               # 핵심 멀티테넌트 로직
│   │   ├── tenant_manager.py    # 테넌트 생성/삭제/조회
│   │   ├── lifecycle.py         # 테넌트 생명주기 관리
│   │   ├── db_pool.py           # DB 커넥션 풀
│   │   └── migration.py         # 스키마 마이그레이션
│   ├── providers/          # AI/ML 프로바이더 추상화
│   │   ├── llm.py               # LLM 팩토리 (OpenAI, Claude, Gemini)
│   │   ├── embedding.py         # 임베딩 프로바이더
│   │   ├── vector_db.py         # 벡터DB 추상화
│   │   └── reranker.py          # 리랭커 프로바이더
│   ├── middleware/         # FastAPI 미들웨어
│   │   ├── tenant.py            # 테넌트 ID 추출/검증
│   │   ├── auth.py              # 인증/인가
│   │   └── rate_limit.py        # 레이트 리밋
│   ├── integrations/       # 서비스별 연동 가이드
│   ├── market/             # Service Market 연동
│   ├── manifest/           # 서비스 매니페스트
│   ├── standard_api/       # 표준 API 엔드포인트
│   └── utils/              # 유틸리티
├── migrations/             # Alembic 마이그레이션
├── examples/               # 사용 예제
└── tests/                  # 테스트
```

## 🚨 중요 규칙 (항상 준수)

### 테넌트 격리
- 테넌트 간 데이터 접근 절대 불가
- DB 쿼리에 항상 `tenant_id` 필터 포함
- 환경변수/설정에서 테넌트 민감 정보 분리

### 프로바이더 추상화
```python
# 올바른 예: 추상 인터페이스 사용
from mt_paas.providers import LLMProvider

llm = LLMProvider.get_provider("openai", model="gpt-4o")
response = await llm.generate(prompt)

# 잘못된 예: 직접 SDK 호출
from openai import OpenAI  # ❌ 직접 사용 금지
```

### API 키 관리
- 테넌트별 API 키는 암호화하여 저장
- 중앙 관리 키와 테넌트 자체 키 구분
- 키 로테이션 메커니즘 제공

## 📋 코딩 규칙

### Python
```python
# 비동기 우선
async def create_tenant(tenant_id: str, config: TenantConfig) -> Tenant:
    """테넌트를 생성합니다.

    Args:
        tenant_id: 고유 테넌트 식별자
        config: 테넌트 설정

    Returns:
        생성된 Tenant 객체

    Raises:
        TenantExistsError: 이미 존재하는 테넌트
    """
    pass

# Type hints 필수
from typing import Optional, List, Dict

# Pydantic 모델 사용
from pydantic import BaseModel

class TenantConfig(BaseModel):
    name: str
    db_url: Optional[str] = None
    features: List[str] = []
```

### Import 구조
```python
# 1. 표준 라이브러리
import os
from typing import Optional

# 2. 서드파티
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# 3. 로컬 (mt_paas 내부)
from mt_paas.core import TenantManager
from mt_paas.providers import LLMProvider
```

### 명명 규칙
| 대상 | 규칙 | 예시 |
|------|------|------|
| 모듈/파일 | snake_case | `tenant_manager.py` |
| 클래스 | PascalCase | `TenantManager` |
| 함수/변수 | snake_case | `get_tenant_config()` |
| 상수 | UPPER_SNAKE | `DEFAULT_POOL_SIZE` |
| 프로바이더 | Provider 접미사 | `LLMProvider`, `EmbeddingProvider` |

## 💡 아키텍처 패턴

### 프로바이더 팩토리
```python
class LLMProvider:
    @classmethod
    def get_provider(cls, provider_type: str, **kwargs):
        providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "google": GoogleProvider,
        }
        return providers[provider_type](**kwargs)
```

### 테넌트 컨텍스트
```python
from contextvars import ContextVar

_current_tenant: ContextVar[str] = ContextVar('current_tenant')

def get_current_tenant() -> str:
    return _current_tenant.get()

def set_current_tenant(tenant_id: str):
    _current_tenant.set(tenant_id)
```

### 미들웨어 체인
```
Request → TenantMiddleware → AuthMiddleware → RateLimitMiddleware → Handler
          (tenant_id 추출)   (JWT 검증)        (요청 제한)
```

## 서비스 연동 방법

### 1. 설치
```bash
# 로컬 개발용
pip install -e /home/aiedu/workspace/multi_tenant_paas

# requirements.txt
-e /home/aiedu/workspace/multi_tenant_paas
```

### 2. FastAPI 앱에 적용
```python
from fastapi import FastAPI
from mt_paas import setup_multi_tenant

app = FastAPI()

setup_multi_tenant(
    app,
    central_db_url="postgresql://localhost/service_market",
    tenant_db_prefix="tenant_",
    providers=["llm", "embedding", "vectordb"]
)
```

### 3. 테넌트 생성 API
```python
from mt_paas.core import TenantManager

@app.post("/tenants")
async def create_tenant(config: TenantConfig):
    tenant = await TenantManager.create(config)
    return {"tenant_id": tenant.id, "url": tenant.url}
```

## 표준 API 엔드포인트

모든 서비스가 구현해야 하는 표준 API:

| 엔드포인트 | 설명 |
|------------|------|
| `GET /api/health` | 헬스체크 |
| `GET /api/tenant/info` | 현재 테넌트 정보 |
| `POST /api/tenant/webhook/auto-provision` | 자동 프로비저닝 |
| `DELETE /api/tenant/{tenant_id}` | 테넌트 삭제 |

## Service Market 연동

### Webhook 수신
```python
@app.post("/api/tenant/webhook/auto-provision")
async def auto_provision(
    request: ProvisionRequest,
    api_key: str = Header(..., alias="X-API-Key")
):
    # API 키 검증
    if not verify_api_key(api_key):
        raise HTTPException(401, "Invalid API key")

    # 테넌트 생성
    tenant = await TenantManager.create(request.to_config())

    return {
        "success": True,
        "tenant_url": tenant.url,
        "admin_credentials": tenant.admin_credentials
    }
```

## 테스트

```bash
# 전체 테스트
pytest tests/

# 특정 모듈 테스트
pytest tests/test_tenant_manager.py -v

# 커버리지
pytest --cov=mt_paas tests/
```

## 자주 발생하는 이슈

### 테넌트 DB 연결 실패
1. `tenant_db_prefix` 설정 확인
2. 테넌트 DB가 실제로 존재하는지 확인
3. 커넥션 풀 크기 (`DEFAULT_POOL_SIZE`) 조정

### 프로바이더 초기화 실패
1. 환경변수 (`OPENAI_API_KEY` 등) 확인
2. 네트워크 연결 확인
3. API 할당량 확인

### 미들웨어 순서 문제
- `TenantMiddleware`가 가장 먼저 적용되어야 함
- `AuthMiddleware`는 테넌트 컨텍스트 설정 후 실행

## 버전 관리

```
major.minor.patch

- major: 호환성 깨지는 변경
- minor: 새 기능 추가 (하위 호환)
- patch: 버그 수정
```

## 기여 가이드

1. 새 프로바이더 추가 시 `providers/` 디렉토리에 구현
2. 추상 인터페이스 (`BaseProvider`) 상속 필수
3. 테스트 코드 필수 (`tests/test_providers/`)
4. docstring 필수 (Google 스타일)
