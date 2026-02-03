# AI 서비스 멀티테넌트 연동 Quick Start

> AI 서비스를 Multi-Tenant PaaS를 이용해 Service Market에 연동하는 단계별 가이드

**예상 소요 시간**: 1~2시간

**검증된 실제 구현 예시**: llm_chatbot (2026-01-10)

---

## 목차

1. [사전 요구사항](#1-사전-요구사항)
2. [mt_paas 설치](#2-mt_paas-설치)
3. [FastAPI 통합](#3-fastapi-통합)
4. [Webhook 엔드포인트 구현](#4-webhook-엔드포인트-구현)
5. [미들웨어 설정 (중요!)](#5-미들웨어-설정-중요)
6. [테넌트 격리 구현](#6-테넌트-격리-구현)
7. [Service Market 등록](#7-service-market-등록)
8. [Docker 네트워크 연결](#8-docker-네트워크-연결)
9. [테스트 및 검증](#9-테스트-및-검증)
10. [체크리스트](#10-체크리스트)
11. [Service Market ↔ AI Service 데이터 흐름](#11-service-market--ai-service-데이터-흐름)

---

## 1. 사전 요구사항

### 1.1 필수 조건

| 항목 | 요구사항 |
|------|----------|
| Python | 3.10 이상 |
| FastAPI | 0.100.0 이상 |
| PostgreSQL | 12 이상 |
| Docker | 설치됨 |

### 1.2 프로젝트 구조 확인

```
your_ai_service/
├── backend/
│   ├── server.py          # FastAPI 앱
│   ├── routers/
│   │   └── tenant.py      # (신규 생성) 테넌트 관리 라우터
│   ├── requirements.txt
│   └── .env
├── frontend/
└── docker-compose.yml
```

---

## 2. mt_paas 설치

### 2.1 pip 설치 (개발 모드)

```bash
# requirements.txt에 추가
echo "-e /home/aiedu/workspace/multi_tenant_paas" >> requirements.txt

# 또는 직접 설치
pip install -e /home/aiedu/workspace/multi_tenant_paas
```

### 2.2 선택적 의존성 설치

```bash
# LLM 프로바이더 포함
pip install -e "/home/aiedu/workspace/multi_tenant_paas[llm]"

# 전체 기능
pip install -e "/home/aiedu/workspace/multi_tenant_paas[all]"
```

### 2.3 설치 확인

```python
# Python에서 확인
from mt_paas import setup_multi_tenant
print("mt_paas 설치 완료!")
```

---

## 3. FastAPI 통합

### 3.1 환경변수 설정

`.env` 파일에 추가:

```bash
# MT-PaaS 데이터베이스 설정
MT_DB_HOST=localhost
MT_DB_PORT=5432
MT_DB_USER=postgres
MT_DB_PASSWORD=your_password
MT_DB_NAME=your_service_central

# Service Market 연동
MARKET_API_KEY=mt_dev_key_12345
SERVICE_BASE_URL=http://220.66.157.70:8XXX

# JWT 설정 (선택)
JWT_SECRET_KEY=your_jwt_secret
```

### 3.2 FastAPI 앱에 MT-PaaS 통합

```python
# server.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
from mt_paas import setup_multi_tenant
from mt_paas.config import MTPaaSConfig
import os

# MT-PaaS 설정
mt_config = MTPaaSConfig(
    central_db_url=f"postgresql+asyncpg://{os.getenv('MT_DB_USER')}:{os.getenv('MT_DB_PASSWORD')}@{os.getenv('MT_DB_HOST')}:{os.getenv('MT_DB_PORT')}/{os.getenv('MT_DB_NAME')}",
    market_api_key=os.getenv("MARKET_API_KEY", "mt_dev_key_12345"),
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 초기화
    await app.state.mt.init()
    yield
    # 종료 시 정리
    await app.state.mt.close()

app = FastAPI(
    title="Your AI Service",
    lifespan=lifespan
)

# MT-PaaS 통합 (미들웨어 + 라우터 자동 등록)
mt = setup_multi_tenant(app, config=mt_config)
app.state.mt = mt
```

### 3.3 간단한 통합 (최소 설정)

```python
# 최소 설정으로 빠르게 시작
from fastapi import FastAPI
from mt_paas import setup_multi_tenant

app = FastAPI()

# 한 줄로 통합
mt = setup_multi_tenant(
    app,
    central_db_url="postgresql+asyncpg://postgres:postgres@localhost:5432/my_service"
)
```

---

## 4. Webhook 엔드포인트 구현

Service Market에서 신청 승인 시 호출되는 Webhook을 구현합니다.

### 4.1 테넌트 라우터 생성

```python
# routers/tenant.py

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
import re

router = APIRouter()

# API Key (Service Market과 동일해야 함)
MT_PAAS_API_KEY = os.getenv("MARKET_API_KEY", "mt_dev_key_12345")


class WebhookPayload(BaseModel):
    """Service Market에서 전송하는 Webhook 페이로드"""
    application: dict
    applicant: dict
    service: dict


class TenantResponse(BaseModel):
    """테넌트 생성 응답"""
    success: bool
    tenant_id: str
    message: str
    access_url: Optional[str] = None
    admin_credentials: Optional[dict] = None
    created_at: str


def verify_api_key(x_api_key: str = Header(None)):
    """API Key 검증"""
    if not x_api_key or x_api_key != MT_PAAS_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


def generate_tenant_id(university_name: str, application_id: int) -> str:
    """테넌트 ID 생성"""
    # 한글 제거, 특수문자를 언더스코어로 변환
    slug = re.sub(r'[^a-zA-Z0-9]', '_', university_name.lower())[:20]
    return f"{slug}_{application_id}"


@router.post("/webhook/application-approved", response_model=TenantResponse)
async def handle_application_approved(
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    서비스 마켓에서 신청 승인 시 호출되는 Webhook

    1. API Key 검증
    2. 페이로드 파싱
    3. 테넌트 생성
    4. 접속 URL 반환
    """
    verify_api_key(x_api_key)

    body = await request.json()

    application = body.get("application", {})
    applicant = body.get("applicant", {})
    service = body.get("service", {})

    # 테넌트 ID 생성
    university_name = applicant.get("university_name", "unknown")
    application_id = application.get("id", 0)
    tenant_id = generate_tenant_id(university_name, application_id)

    try:
        # MT-PaaS를 통한 테넌트 생성
        mt = request.app.state.mt

        tenant = await mt.lifecycle.create_tenant(
            tenant_id=tenant_id,
            name=university_name,
            admin_email=applicant.get("email"),
            config={
                "application_id": application_id,
                "application_kind": application.get("kind", "service"),
                "admin_name": applicant.get("name"),
                "contact": application.get("contact"),
                "university_name": university_name,
            }
        )

        # 접속 URL 생성
        base_url = os.getenv("SERVICE_BASE_URL", "http://localhost:8000")
        access_url = f"{base_url}?tenant={tenant_id}"

        return TenantResponse(
            success=True,
            tenant_id=tenant_id,
            message=f"테넌트 '{university_name}' 생성 완료",
            access_url=access_url,
            admin_credentials={
                "email": applicant.get("email"),
                "note": "서비스 마켓 계정으로 로그인하세요."
            },
            created_at=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"테넌트 생성 실패: {str(e)}"
        )


@router.get("/status/{tenant_id}")
async def get_tenant_status(tenant_id: str, request: Request):
    """테넌트 상태 조회"""
    mt = request.app.state.mt

    tenant = await mt.manager.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다")

    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None
    }


@router.get("/list")
async def list_tenants(request: Request, status: Optional[str] = None):
    """테넌트 목록 조회"""
    mt = request.app.state.mt

    tenants = await mt.manager.list_tenants(status=status)

    return {
        "count": len(tenants),
        "tenants": [
            {
                "tenant_id": t.tenant_id,
                "name": t.name,
                "status": t.status,
            }
            for t in tenants
        ]
    }
```

### 4.2 라우터 등록

```python
# server.py에 추가

from routers import tenant

# 테넌트 관리 API 등록
app.include_router(
    tenant.router,
    prefix="/api/tenant",
    tags=["Tenant Management"]
)
```

---

## 5. 미들웨어 설정 (중요!)

> ⚠️ **이 섹션은 llm_chatbot 연동 시 발견된 중요한 이슈를 반영합니다.**

### 5.1 Webhook 경로를 공개 경로로 설정 (필수!)

테넌트 미들웨어가 Webhook 요청을 가로채지 않도록 **반드시** 공개 경로에 추가해야 합니다.

```python
# core/middleware/tenant.py

class TenantMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_tenant: str = None):
        super().__init__(app)
        self.default_tenant = default_tenant

        # ⚠️ 중요: Webhook 경로를 공개 경로에 추가!
        self.public_paths = [
            "/",
            "/health",
            "/api/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/super",           # 슈퍼 관리자 (별도 인증)
            "/api/tenant",          # ✅ Service Market Webhook (별도 API Key 인증)
            "/api/marketplace",     # ✅ Marketplace API (별도 API Key 인증)
        ]

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path

        # 공개 경로는 테넌트 검증 스킵
        is_public = (path == "/") or any(
            path.startswith(p) for p in self.public_paths if p != "/"
        )
        if is_public:
            return await call_next(request)

        # 비공개 경로: 테넌트 식별 로직 수행
        # ...
```

### 5.2 왜 이 설정이 필요한가?

**문제 상황**:
1. Service Market이 `POST /api/tenant/webhook/auto-provision` 호출
2. 테넌트 미들웨어가 먼저 요청을 가로챔
3. `X-Tenant-ID` 헤더가 없어서 401 에러 반환
4. Webhook 핸들러까지 요청이 도달하지 못함

**해결책**:
- `/api/tenant` 경로를 `public_paths`에 추가
- Webhook 핸들러에서 `X-API-Key`로 별도 인증 수행

### 5.3 검증된 실제 구현 (llm_chatbot)

```python
# /home/aiedu/workspace/llm_chatbot/backend/core/middleware/tenant.py

self.public_paths = [
    "/",
    "/health",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/super",       # 슈퍼 관리자 API는 별도 인증
    "/api/tenant",      # Service Market Webhook (별도 API Key 인증)
    "/api/marketplace", # Marketplace 연동 API (별도 API Key 인증)
]
```

---

## 6. 테넌트 격리 구현

### 6.1 미들웨어를 통한 테넌트 식별

```python
# 자동으로 요청에서 테넌트 ID 추출
from mt_paas.middleware import require_tenant, optional_tenant
from fastapi import Depends

@app.get("/api/data")
async def get_data(tenant = Depends(require_tenant)):
    """
    테넌트 필수 API
    - Header: X-Tenant-ID
    - Query: ?tenant_id=xxx
    - Path: /tenant/{tenant_id}/...
    """
    return {
        "tenant_id": tenant.tenant_id,
        "tenant_name": tenant.name
    }


@app.get("/api/public")
async def public_data(tenant = Depends(optional_tenant)):
    """테넌트 선택적 API"""
    if tenant:
        return {"message": f"안녕하세요, {tenant.name}님"}
    return {"message": "공개 데이터입니다"}
```

### 6.2 데이터베이스 스키마 격리

```python
# 테넌트별 DB 연결 가져오기
from mt_paas.core.database import DatabaseManager

async def get_tenant_data(tenant_id: str, db_manager: DatabaseManager):
    """테넌트 전용 DB에서 데이터 조회"""

    async with db_manager.get_tenant_connection(tenant_id) as conn:
        result = await conn.fetch("SELECT * FROM users")
        return result
```

### 6.3 테넌트 컨텍스트 활용

```python
from mt_paas.middleware import get_current_tenant

async def some_business_logic():
    """비즈니스 로직에서 현재 테넌트 정보 접근"""
    tenant = get_current_tenant()

    if tenant:
        print(f"현재 테넌트: {tenant.tenant_id}")
        # 테넌트별 로직 수행
```

---

## 7. Service Market 등록

### 7.1 서비스 정보 등록 (API 사용)

```bash
# Service Market에 로그인 후 서비스 등록
curl -X POST http://220.66.157.70:8502/api/v1/services/ \
  -b "cookies.txt" \
  -F "category_id=1" \
  -F "title=Your AI Service" \
  -F "provider=Your Organization" \
  -F "service_url=http://220.66.157.70:YOUR_PORT/" \
  -F "contact=your@email.com" \
  -F "introduction=서비스 소개 내용" \
  -F "features=- 기능1
- 기능2
- 기능3" \
  -F "use_cases=- 사용사례1
- 사용사례2" \
  -F "image=@/path/to/logo.png"
```

### 7.2 서비스 정보 등록 (DB 직접)

```sql
-- Service Market DB (MySQL)
INSERT INTO services (
    user_id,
    category_id,
    title,
    provider,
    service_url,
    introduction,
    features,
    use_cases,
    contact,
    slug,
    icon,
    bg_gradient,
    integration_type,
    integration_endpoint
) VALUES (
    4,                                              -- owner user_id
    1,                                              -- 카테고리: AI 튜터
    'Your AI Service',
    'Your Organization',
    'http://220.66.157.70:YOUR_PORT/',
    '서비스 소개 내용입니다.',
    '- 기능1\n- 기능2\n- 기능3',
    '- 사용사례1\n- 사용사례2',
    'your@email.com',
    'your-ai-service',                              -- URL 슬러그
    '🤖',
    'linear-gradient(135deg,#6366f1,#8b5cf6)',
    'webhook',                                      -- 연동 타입
    'http://your-service-backend:8000'              -- Webhook URL (Docker 내부)
);
```

### 7.3 주요 필드 설명

| 필드 | 설명 | 예시 |
|------|------|------|
| `slug` | URL용 고유 식별자 | `my-ai-chatbot` |
| `integration_type` | 연동 방식 | `webhook`, `iframe`, `redirect` |
| `integration_endpoint` | Webhook 호출 URL | `http://container-name:port` |

---

## 8. Docker 네트워크 연결

### 8.1 네트워크 확인

```bash
# 현재 컨테이너의 네트워크 확인
docker inspect your-service-backend --format '{{json .NetworkSettings.Networks}}' | jq

# Service Market 백엔드 네트워크 확인
docker inspect service-market-backend --format '{{json .NetworkSettings.Networks}}' | jq
```

### 8.2 네트워크 연결

```bash
# 방법 1: Service Market을 AI 서비스 네트워크에 연결
docker network connect your_service_network service-market-backend

# 방법 2: AI 서비스를 Service Market 네트워크에 연결
docker network connect service-market_default your-service-backend
```

### 8.3 docker-compose.yml 설정 (권장)

```yaml
# your_ai_service/docker-compose.yml

version: '3.8'

services:
  backend:
    build: ./backend
    container_name: your-service-backend
    ports:
      - "8XXX:8000"
    environment:
      - MT_DB_HOST=postgres
      - MARKET_API_KEY=mt_dev_key_12345
    networks:
      - your-network
      - service-market_default  # Service Market 네트워크 추가

networks:
  your-network:
    driver: bridge
  service-market_default:
    external: true  # 외부 네트워크 참조
```

---

## 9. 테스트 및 검증

### 9.1 Webhook 직접 테스트

```bash
# 1. Webhook 엔드포인트 테스트
curl -X POST http://localhost:8000/api/tenant/webhook/application-approved \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mt_dev_key_12345" \
  -d '{
    "application": {
      "id": 999,
      "kind": "demo",
      "contact": "010-1234-5678",
      "reason": "테스트 신청"
    },
    "applicant": {
      "id": 1,
      "name": "테스트",
      "email": "test@test.com",
      "university_name": "테스트대학교"
    },
    "service": {
      "id": 1,
      "slug": "your-service",
      "title": "Your Service"
    }
  }'
```

예상 응답:
```json
{
  "success": true,
  "tenant_id": "___________999",
  "message": "테넌트 '테스트대학교' 생성 완료",
  "access_url": "http://220.66.157.70:8XXX?tenant=___________999",
  "admin_credentials": {
    "email": "test@test.com",
    "note": "서비스 마켓 계정으로 로그인하세요."
  },
  "created_at": "2026-01-10T12:00:00"
}
```

### 9.2 테넌트 상태 확인

```bash
# 테넌트 목록 조회
curl http://localhost:8000/api/tenant/list

# 특정 테넌트 상태 조회
curl http://localhost:8000/api/tenant/status/___________999
```

### 9.3 전체 플로우 테스트

```
1. Service Market (http://220.66.157.70:8501) 접속
2. 사용자 계정으로 로그인
3. 서비스 상세 페이지에서 "데모 신청" 또는 "서비스 신청"
4. 관리자 계정으로 로그인 (/ad-login)
5. 신청 목록에서 "승인" 클릭
6. AI 서비스 로그에서 Webhook 호출 확인
7. 생성된 테넌트 접속 확인
```

### 9.4 로그 확인

```bash
# AI 서비스 백엔드 로그
docker logs -f your-service-backend

# Service Market 백엔드 로그
docker logs -f service-market-backend
```

---

## 10. 체크리스트

### Phase 1: 기본 설정

- [ ] mt_paas 패키지 설치
- [ ] 환경변수 설정 (.env)
- [ ] FastAPI 앱에 MT-PaaS 통합
- [ ] 데이터베이스 연결 확인

### Phase 2: Webhook 구현

- [ ] `/api/tenant/webhook/application-approved` 엔드포인트 구현
- [ ] API Key 검증 로직
- [ ] 테넌트 생성 로직
- [ ] 접속 URL 생성 로직
- [ ] 라우터 등록

### Phase 3: Service Market 연동

- [ ] 서비스 정보 등록
- [ ] integration_endpoint 설정
- [ ] Docker 네트워크 연결
- [ ] Webhook 통신 확인

### Phase 4: 테스트

- [ ] Webhook 직접 호출 테스트
- [ ] 전체 플로우 테스트 (신청 → 승인 → 테넌트 생성)
- [ ] 테넌트 접속 테스트
- [ ] 에러 케이스 테스트

---

## 문제 해결

### Connection refused 에러

```
Webhook call failed: [Errno 111] Connection refused
```

**해결**: Docker 네트워크 연결 확인

```bash
docker network connect your_network service-market-backend
```

### 401 Unauthorized

```json
{"detail": "Invalid API Key"}
```

**해결**: API Key 일치 확인

```bash
# AI 서비스 .env
MARKET_API_KEY=mt_dev_key_12345

# Service Market DB
SELECT integration_api_key FROM services WHERE slug = 'your-service';
```

### 404 Not Found

```json
{"detail": "Not Found"}
```

**해결**: 라우터 경로 확인

```python
# integration_endpoint와 실제 라우터 경로가 일치해야 함
# integration_endpoint: http://backend:8000
# 라우터: /api/tenant/webhook/application-approved
# 전체 URL: http://backend:8000/api/tenant/webhook/application-approved
```

### 서버 코드 변경이 반영되지 않음 (Gunicorn)

**문제 상황**:
- 코드를 수정했지만 새 코드가 반영되지 않음
- 여러 gunicorn 프로세스가 동시에 실행 중

**해결**:

```bash
# 1. 모든 gunicorn 프로세스 확인
ps aux | grep gunicorn

# 2. 프로젝트 관련 gunicorn 프로세스 모두 종료
pkill -9 -f "gunicorn.*llm_chatbot"  # 프로젝트명 변경

# 3. 올바른 디렉토리에서 재시작
cd /home/aiedu/workspace/llm_chatbot/backend
source venv/bin/activate

# 4. 데몬 모드로 시작 (PID 파일 저장)
gunicorn server:app \
  --bind 0.0.0.0:8600 \
  --workers 1 \
  --worker-class uvicorn.workers.UvicornWorker \
  --daemon \
  --pid gunicorn.pid

# 5. 정상 시작 확인
curl http://localhost:8600/health
```

**팁**: 개발 중에는 `--reload` 옵션으로 자동 재시작:
```bash
# 개발 모드 (코드 변경 시 자동 재시작)
uvicorn server:app --host 0.0.0.0 --port 8600 --reload
```

---

## 검증된 실제 구현 (llm_chatbot)

> 이 섹션은 2026-01-10에 llm_chatbot을 Service Market에 연동하며 검증된 내용입니다.

### 실제 Webhook 페이로드 형식

Service Market이 실제로 전송하는 페이로드:

```json
{
  "application_id": 17,
  "kind": "demo",
  "contact": "02-880-1234",
  "reason": "AI 튜터 서비스 데모 체험 신청합니다.",
  "applicant": {
    "id": 27,
    "name": "김서울",
    "email": "seoul@university.ac.kr",
    "university_name": "서울대학교"
  },
  "service": {
    "id": 18,
    "slug": "llm-chatbot",
    "title": "Multi-LLM Chatbot"
  },
  "callback_url": "http://service-market-backend:8000/api/v1/callback"
}
```

### llm_chatbot Webhook 구현 (검증됨)

```python
# /home/aiedu/workspace/llm_chatbot/backend/routers/marketplace.py

class AutoProvisionPayload(BaseModel):
    """Service Market에서 전송하는 자동 프로비저닝 Webhook 페이로드"""
    application_id: int
    kind: str  # "demo" or "service"
    contact: Optional[str] = None
    reason: Optional[str] = None
    applicant: dict  # {id, name, email, university_name}
    service: dict    # {id, title, slug}
    callback_url: Optional[str] = None


class AutoProvisionResponse(BaseModel):
    """자동 프로비저닝 응답"""
    status: str  # "approved", "processing", "rejected", "error"
    tenant_id: Optional[str] = None
    tenant_url: Optional[str] = None
    message: Optional[str] = None
    expires_at: Optional[str] = None
```

### 환경변수 설정 예시

```bash
# /home/aiedu/workspace/llm_chatbot/backend/.env

# 프론트엔드 URL (테넌트 접속 URL 생성에 사용)
FRONTEND_URL="http://220.66.157.70:8612"

# Service Market API Key
MT_PAAS_API_KEY="mt_dev_key_12345"

# Marketplace API Key (기존 연동용)
MARKETPLACE_API_KEY="svcmkt_secret_key_2024"
```

### Service Market DB 설정 (검증됨)

```sql
-- Service Market MySQL DB에서 실행
UPDATE services SET
  integration_endpoint='http://220.66.157.70:8600',
  integration_webhook_path='/api/tenant/webhook/auto-provision',
  integration_api_key='mt_dev_key_12345'
WHERE id=2;  -- llm_chatbot service ID
```

### 성공적인 Webhook 테스트 결과

```bash
curl -X POST http://localhost:8600/api/tenant/webhook/auto-provision \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mt_dev_key_12345" \
  -d '{
    "application_id": 999,
    "kind": "demo",
    "applicant": {"id":1,"name":"테스트","email":"test@test.com","university_name":"테스트대학교"},
    "service": {"id":1,"slug":"llm-chatbot","title":"LLM Chatbot"}
  }'
```

응답:
```json
{
  "status": "approved",
  "tenant_id": "demo_tenant_999",
  "tenant_url": "http://220.66.157.70:8612/#/?tenant=demo_tenant_999",
  "message": "테넌트 '테스트대학교' 생성 완료",
  "expires_at": "2026-02-09T04:16:19.121568"
}
```

---

## 11. Service Market ↔ AI Service 데이터 흐름

> 이 섹션은 Service Market과 AI 서비스 간에 주고받는 데이터를 명확히 정리합니다.

### 11.1 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Service Market                                  │
│                                                                              │
│  1. 사용자가 서비스 신청 (데모/정식)                                           │
│  2. 관리자가 신청 승인                                                        │
│  3. Webhook 호출 ─────────────────────────────────────────────────────────┐  │
│                                                                           │  │
└───────────────────────────────────────────────────────────────────────────│──┘
                                                                            │
                                                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                AI Service                                    │
│                                                                              │
│  4. Webhook 수신 (POST /api/tenant/webhook/auto-provision)                   │
│  5. 테넌트 생성 또는 기존 테넌트 재사용                                         │
│  6. 신청 내역 저장 (service_applications 테이블)                              │
│  7. 응답 반환 ────────────────────────────────────────────────────────────┐  │
│                                                                           │  │
└───────────────────────────────────────────────────────────────────────────│──┘
                                                                            │
                                                                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Service Market                                  │
│                                                                              │
│  8. 응답 수신 및 처리                                                         │
│  9. 사용자에게 접속 URL 안내                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Service Market → AI Service (Webhook 요청)

**엔드포인트**: `POST {integration_endpoint}{integration_webhook_path}`
**예시**: `POST http://220.66.157.70:8600/api/tenant/webhook/auto-provision`

**요청 헤더**:
```
Content-Type: application/json
X-API-Key: {integration_api_key}
```

**요청 본문 (Webhook Payload)**:

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| `application_id` | integer | ✅ | Service Market 신청 ID | `17` |
| `kind` | string | ✅ | 신청 유형 ("demo" 또는 "service") | `"demo"` |
| `contact` | string | ❌ | 연락처 | `"02-880-1234"` |
| `reason` | string | ❌ | 신청 사유 | `"AI 튜터 서비스 체험 희망"` |
| `applicant` | object | ✅ | 신청자 정보 | 아래 참조 |
| `applicant.id` | integer | ✅ | Service Market 사용자 ID | `27` |
| `applicant.name` | string | ✅ | 신청자 이름 | `"김서울"` |
| `applicant.email` | string | ✅ | 신청자 이메일 | `"seoul@university.ac.kr"` |
| `applicant.university_name` | string | ✅ | 소속 기관명 | `"서울대학교"` |
| `service` | object | ✅ | 서비스 정보 | 아래 참조 |
| `service.id` | integer | ✅ | Service Market 서비스 ID | `18` |
| `service.slug` | string | ✅ | 서비스 슬러그 | `"llm-chatbot"` |
| `service.title` | string | ✅ | 서비스 제목 | `"Multi-LLM Chatbot"` |
| `callback_url` | string | ❌ | 콜백 URL (현재 미사용) | `"http://..."` |
| `start_date` | string | ❌ | 서비스 시작일 (YYYY-MM-DD) | `"2026-01-10"` |
| `end_date` | string | ❌ | 서비스 종료일 (YYYY-MM-DD) | `"2026-12-31"` |

**전체 페이로드 예시**:
```json
{
  "application_id": 17,
  "kind": "demo",
  "contact": "02-880-1234",
  "reason": "AI 튜터 서비스 데모 체험 신청합니다.",
  "applicant": {
    "id": 27,
    "name": "김서울",
    "email": "seoul@university.ac.kr",
    "university_name": "서울대학교"
  },
  "service": {
    "id": 18,
    "slug": "llm-chatbot",
    "title": "Multi-LLM Chatbot"
  },
  "callback_url": "http://service-market-backend:8000/api/v1/callback",
  "start_date": "2026-01-10",
  "end_date": "2026-02-09"
}
```

### 11.3 AI Service → Service Market (Webhook 응답)

**응답 상태 코드**:
- `200 OK`: 성공 (테넌트 생성 또는 재사용)
- `400 Bad Request`: 잘못된 요청
- `401 Unauthorized`: API Key 오류
- `500 Internal Server Error`: 서버 오류

**응답 본문 (Response Payload)**:

| 필드 | 타입 | 필수 | 설명 | 예시 |
|------|------|------|------|------|
| `status` | string | ✅ | 처리 상태 | `"approved"`, `"processing"`, `"rejected"`, `"error"` |
| `tenant_id` | string | ✅ | 생성된 테넌트 ID | `"demo_tenant_21"` |
| `tenant_url` | string | ✅ | 테넌트 접속 URL | `"http://220.66.157.70:8612/#/?tenant=demo_tenant_21"` |
| `message` | string | ✅ | 처리 결과 메시지 | `"테넌트 '서울대학교' 생성 완료"` |
| `expires_at` | string | ❌ | 만료 일시 (ISO 8601) | `"2026-02-09T04:16:19.121568"` |

**응답 상태값 설명**:

| status | 의미 | Service Market 동작 |
|--------|------|---------------------|
| `approved` | 즉시 승인됨 | 사용자에게 접속 URL 안내 |
| `processing` | 처리 중 (비동기) | 콜백 대기 |
| `rejected` | 거절됨 | 거절 사유 표시 |
| `error` | 오류 발생 | 오류 메시지 표시 |

**성공 응답 예시**:
```json
{
  "status": "approved",
  "tenant_id": "demo_tenant_21",
  "tenant_url": "http://220.66.157.70:8612/#/?tenant=demo_tenant_21",
  "message": "테넌트 '서울대학교' 생성 완료",
  "expires_at": "2026-02-09T04:16:19.121568"
}
```

**기존 테넌트 재사용 응답 예시**:
```json
{
  "status": "approved",
  "tenant_id": "hallym",
  "tenant_url": "http://220.66.157.70:8612/#/?tenant=hallym",
  "message": "기존 테넌트 'hallym'에 신규 서비스 신청이 추가되었습니다."
}
```

**오류 응답 예시**:
```json
{
  "status": "error",
  "tenant_id": null,
  "tenant_url": null,
  "message": "테넌트 생성 실패: 데이터베이스 연결 오류"
}
```

### 11.4 테넌트 재사용 로직

AI 서비스는 다음 조건에서 기존 테넌트를 재사용합니다:

```python
# 동일한 admin_email을 가진 테넌트가 있으면 재사용
existing = await conn.execute(
    text("SELECT id FROM tenants WHERE admin_email = :email"),
    {"email": applicant.get("email")}
)
existing_tenant = existing.fetchone()

if existing_tenant:
    # 기존 테넌트 재사용
    tenant_id = existing_tenant.id
    # service_applications에 새 신청 내역만 추가
else:
    # 새 테넌트 생성
```

**이 로직의 장점**:
- 동일 기관의 여러 신청이 하나의 테넌트에 통합됨
- 신청 이력은 `service_applications` 테이블에서 관리
- 테넌트 ID 난립 방지

### 11.5 DB 테이블 구조

**Service Market DB (MySQL)** - `services` 테이블:

| 컬럼 | 설명 | AI 서비스에서 사용 |
|------|------|-------------------|
| `integration_endpoint` | AI 서비스 기본 URL | Webhook 호출 시 사용 |
| `integration_webhook_path` | Webhook 경로 | 기본값: `/api/tenant/webhook/auto-provision` |
| `integration_api_key` | API Key | `X-API-Key` 헤더로 전송 |

**AI Service Central DB (PostgreSQL)** - `tenants` 테이블:

| 컬럼 | 설명 | Service Market에서 전달 |
|------|------|------------------------|
| `id` | 테넌트 ID | AI 서비스가 생성 |
| `admin_email` | 관리자 이메일 | `applicant.email` |
| `name` | 기관명 | `applicant.university_name` |
| `config` | 추가 설정 (JSON) | 전체 페이로드 저장 가능 |

**AI Service Central DB (PostgreSQL)** - `service_applications` 테이블:

| 컬럼 | 설명 | 데이터 출처 |
|------|------|------------|
| `tenant_id` | 테넌트 ID | 생성/재사용된 테넌트 |
| `application_id` | 신청 ID | `application_id` |
| `kind` | 신청 유형 | `kind` |
| `applicant_email` | 신청자 이메일 | `applicant.email` |
| `applicant_name` | 신청자 이름 | `applicant.name` |
| `university_name` | 기관명 | `applicant.university_name` |
| `contact` | 연락처 | `contact` |
| `reason` | 신청 사유 | `reason` |
| `service_id` | 서비스 ID | `service.id` |
| `service_slug` | 서비스 슬러그 | `service.slug` |
| `start_date` | 시작일 | `start_date` |
| `end_date` | 종료일 | `end_date` |

---

## 참고 자료

- [MT-PaaS 전체 개발 가이드](./MT-PAAS-Complete-Developer-Guide.md)
- [서비스 통합 상세 가이드](./SERVICE_INTEGRATION_GUIDE.md)
- [Service Market AI 연동 가이드](/home/aiedu/workspace/service_market/docs/AI_SERVICE_INTEGRATION_GUIDE.md)

---

## 연락처

문제가 발생하면 다음 로그를 첨부하여 문의하세요:

```bash
# 필수 로그 수집
docker logs your-service-backend > backend.log 2>&1
docker logs service-market-backend > market.log 2>&1
docker network ls > networks.log
```

---

*최종 업데이트: 2026-01-10*
