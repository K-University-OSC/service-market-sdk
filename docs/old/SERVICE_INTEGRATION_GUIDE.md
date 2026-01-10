# Multi-Tenant PaaS 서비스 통합 가이드

> 서비스 마켓에 새로운 AI 서비스를 등록하고 멀티테넌트 SaaS로 운영하기 위한 종합 가이드

## 목차

1. [개요](#1-개요)
2. [아키텍처 이해](#2-아키텍처-이해)
3. [새 서비스 등록 절차](#3-새-서비스-등록-절차)
4. [멀티테넌트 구현 방법](#4-멀티테넌트-구현-방법)
5. [서비스 마켓 연동](#5-서비스-마켓-연동)
6. [Webhook 구현](#6-webhook-구현)
7. [테스트 방법](#7-테스트-방법)
8. [운영 가이드](#8-운영-가이드)
9. [KELI Tutor 구현 사례](#9-keli-tutor-구현-사례)

---

## 1. 개요

### 1.1 Multi-Tenant PaaS란?

서비스 마켓에서 판매하는 AI 서비스들이 공통으로 사용하는 멀티테넌트 인프라입니다.

```
┌─────────────────────────────────────────────────────────────┐
│                    서비스 마켓 (Service Market)               │
│                  https://svcmkt.k-university.ai              │
│         - 서비스 등록/구매 - 테넌트 관리 - 구독/결제            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Webhook / API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Tenant PaaS Layer                   │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 테넌트 격리   │  │   인증/인가   │  │  사용량 추적  │      │
│  │ (DB 스키마)  │  │ (JWT/Cookie) │  │  (API 호출)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │ KELI Tutor  │     │ AI Chatbot  │     │  AI Advisor │
   │ (교육 AI)   │     │ (대화 AI)   │     │ (상담 AI)   │
   └─────────────┘     └─────────────┘     └─────────────┘
```

### 1.2 주요 개념

| 용어 | 설명 |
|------|------|
| **테넌트(Tenant)** | 서비스를 사용하는 기관 (예: 광주대학교) |
| **테넌트 ID** | 테넌트 고유 식별자 (예: `univ_8`, `demo_7`) |
| **스키마 격리** | 테넌트별 PostgreSQL 스키마로 데이터 분리 |
| **서비스 신청** | 서비스 마켓에서 데모/정식 서비스 신청 |
| **Webhook** | 서비스 마켓 이벤트를 서비스에 전달하는 HTTP 콜백 |

---

## 2. 아키텍처 이해

### 2.1 전체 시스템 구성

```
┌─────────────────────────────────────────────────────────────────────┐
│                           인프라 레이어                               │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   nginx     │  │   Docker    │  │  PostgreSQL │                 │
│  │ (리버스프록시)│  │  (컨테이너)  │  │   (DB)     │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         서비스 마켓 (MySQL)                          │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   users     │  │  services   │  │ service_    │                 │
│  │   테이블     │  │   테이블    │  │ applications│                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    AI 서비스 (PostgreSQL 스키마 격리)                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ hltutor (중앙 스키마)                                        │   │
│  │ - tenants 테이블 (테넌트 목록)                               │   │
│  │ - 공통 설정                                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  univ_8     │  │  demo_7     │  │  univ_xyz   │  ...           │
│  │ (광주대학교) │  │ (데모)      │  │ (다른 기관) │                 │
│  │ - user_mst  │  │ - user_mst  │  │ - user_mst  │                 │
│  │ - chat_his  │  │ - chat_his  │  │ - chat_his  │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 요청 흐름

```
사용자 요청
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 1. nginx: HTTPS → HTTP 프록시                        │
│    - /api/* → 백엔드 (포트 10101)                    │
│    - /* → 프론트엔드 (포트 10100)                    │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 2. 프론트엔드: 테넌트 ID 결정                         │
│    - URL 파라미터: ?tenant=univ_8                    │
│    - 쿠키: tenant_id=univ_8                         │
│    - 도메인: univ_8.ktutor.k-university.ai          │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 3. API 요청: X-Tenant-ID 헤더 포함                   │
│    GET /api/chat                                    │
│    Headers: X-Tenant-ID: univ_8                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 4. 백엔드 미들웨어: 스키마 전환                       │
│    SET search_path TO univ_8, public                │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ 5. 비즈니스 로직: 해당 테넌트 데이터만 접근           │
│    SELECT * FROM user_mst (= univ_8.user_mst)       │
└─────────────────────────────────────────────────────┘
```

---

## 3. 새 서비스 등록 절차

새로운 AI 서비스를 서비스 마켓에 등록하려면 다음 단계를 따릅니다.

### 3.1 사전 요구사항

- [ ] PostgreSQL 데이터베이스
- [ ] Docker 및 Docker Compose
- [ ] FastAPI 기반 백엔드 (권장)
- [ ] React/Vue 기반 프론트엔드 (권장)

### 3.2 단계별 절차

#### Step 1: 서비스 마켓에 서비스 등록

```sql
-- 서비스 마켓 MySQL에서 서비스 등록
INSERT INTO services (
    title,
    description,
    vendor_id,
    category_id,
    status
) VALUES (
    'My AI Service',
    'AI 기반 서비스 설명',
    (SELECT id FROM users WHERE role = 'vendor' AND email = 'vendor@example.com'),
    1,
    'active'
);
```

#### Step 2: 서비스 템플릿 생성

```bash
# 서비스 템플릿 디렉토리 구조
/home/aiedu/workspace/my_ai_service/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py
│   ├── database/
│   │   ├── multi_tenant.py      # 멀티테넌트 핵심 모듈
│   │   └── tenant_context.py    # 테넌트 컨텍스트 관리
│   ├── middleware/
│   │   └── tenant_middleware.py # 테넌트 식별 미들웨어
│   └── routers/
│       └── tenant.py            # 테넌트 관리 API
├── frontend/
│   ├── Dockerfile
│   └── src/
│       └── api/
│           └── axiosInstance.js # 테넌트 ID 자동 주입
└── docker-compose.yml
```

#### Step 3: Webhook 엔드포인트 구현

서비스 마켓과 연동하기 위한 필수 Webhook 엔드포인트:

| 엔드포인트 | 메서드 | 용도 |
|-----------|--------|------|
| `/api/tenant/webhook/user-deleted` | POST | 회원 탈퇴 시 테넌트 삭제 |
| `/api/tenant/webhook/service-cancelled` | POST | 서비스 해지 시 테넌트 정지 |
| `/api/tenant/create` | POST | 새 테넌트 생성 (자동 온보딩) |

#### Step 4: Docker Compose 설정

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "10201:8085"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/myservice
      - SERVICE_MARKET_WEBHOOK_SECRET=webhook_secret_12345
    networks:
      - myservice-network
      - servicemarket_service-market-network  # 서비스 마켓 네트워크 연결

  frontend:
    build: ./frontend
    ports:
      - "10200:80"
    networks:
      - myservice-network

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=myservice
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - myservice-network

networks:
  myservice-network:
    driver: bridge
  servicemarket_service-market-network:
    external: true

volumes:
  db-data:
```

#### Step 5: nginx 설정

```nginx
# /etc/nginx/sites-available/myservice.k-university.ai.conf
server {
    listen 80;
    server_name myservice.k-university.ai;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name myservice.k-university.ai;

    include /etc/nginx/snippets/ssl-wildcard-kuniversity.conf;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:10200;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:10201;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 4. 멀티테넌트 구현 방법

### 4.1 PostgreSQL 스키마 격리 (권장)

KELI Tutor에서 사용하는 방식입니다.

#### 4.1.1 중앙 스키마 테이블 (tenants)

```sql
-- hltutor 스키마 (중앙)
CREATE TABLE hltutor.tenants (
    tenant_id VARCHAR(50) PRIMARY KEY,
    tenant_name VARCHAR(200) NOT NULL,
    admin_email VARCHAR(200),
    admin_name VARCHAR(100),
    university_name VARCHAR(200),
    contact VARCHAR(100),
    description TEXT,
    application_id INTEGER,           -- 서비스 마켓 신청 ID
    application_kind VARCHAR(20),     -- 'demo' or 'service'
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP,
    deleted_reason VARCHAR(255),
    suspended_at TIMESTAMP,
    suspended_reason VARCHAR(255)
);
```

#### 4.1.2 테넌트 컨텍스트 관리

```python
# database/tenant_context.py
from contextvars import ContextVar

_tenant_context: ContextVar[str] = ContextVar('tenant_id', default='hltutor')

def set_tenant(tenant_id: str):
    """현재 요청의 테넌트 ID 설정"""
    _tenant_context.set(tenant_id)

def get_tenant() -> str:
    """현재 요청의 테넌트 ID 반환"""
    return _tenant_context.get()

def get_schema_name() -> str:
    """현재 테넌트의 스키마명 반환"""
    return get_tenant()
```

#### 4.1.3 테넌트 미들웨어

```python
# middleware/tenant_middleware.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from database.tenant_context import set_tenant

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 테넌트 ID 추출 (우선순위)
        tenant_id = (
            request.headers.get('X-Tenant-ID') or
            request.query_params.get('tenant') or
            request.cookies.get('tenant_id') or
            'hltutor'  # 기본값
        )

        # 컨텍스트에 설정
        set_tenant(tenant_id)

        response = await call_next(request)
        return response
```

#### 4.1.4 DB 연결 시 스키마 전환

```python
# database/multi_tenant.py
from database.tenant_context import get_schema_name

async def get_tenant_connection(db_pool):
    """테넌트별 스키마로 전환된 DB 연결 반환"""
    schema_name = get_schema_name()

    conn = await db_pool.acquire()
    await conn.execute(f"SET search_path TO {schema_name}, public")

    return conn
```

### 4.2 동적 스키마 생성

새 테넌트 온보딩 시 스키마 자동 생성:

```python
# database/multi_tenant.py
async def create_tenant_schema(conn, tenant_id: str, template_schema: str = 'template_schema'):
    """템플릿 스키마를 복제하여 새 테넌트 스키마 생성"""

    # 1. 템플릿 스키마에서 테이블 목록 조회
    tables = await conn.fetch("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = $1
    """, template_schema)

    # 2. 새 스키마 생성
    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {tenant_id}")

    # 3. 각 테이블 복제
    for table in tables:
        table_name = table['table_name']
        await conn.execute(f"""
            CREATE TABLE {tenant_id}.{table_name}
            (LIKE {template_schema}.{table_name} INCLUDING ALL)
        """)

    return True
```

---

## 5. 서비스 마켓 연동

### 5.1 서비스 마켓 DB 연결

서비스에서 서비스 마켓 MySQL에 접근하여 신청 정보를 조회할 수 있습니다.

```python
# 서비스 마켓 DB 연결 설정
import aiomysql

async def get_service_market_connection():
    return await aiomysql.connect(
        host='service-market-db',      # Docker 네트워크 컨테이너명
        port=3306,
        user='market_user',
        password='your_password',
        db='market_place_db',
        charset='utf8mb4'
    )
```

### 5.2 서비스 신청 현황 조회

```python
@router.get("/superadmin/applications")
async def get_service_applications():
    """서비스 마켓에서 신청 현황 조회"""
    conn = await get_service_market_connection()

    async with conn.cursor(aiomysql.DictCursor) as cursor:
        await cursor.execute("""
            SELECT
                sa.id,
                sa.kind,           -- 'demo' or 'service'
                sa.status,         -- 'requested', 'approved', 'completed', 'rejected'
                sa.created_at,
                sa.demo_expires_at,
                u.email,
                u.university_name
            FROM service_applications sa
            JOIN users u ON sa.user_id = u.id
            JOIN services s ON sa.service_id = s.id
            WHERE s.title LIKE '%My Service%'
            ORDER BY sa.created_at DESC
        """)
        applications = await cursor.fetchall()

    conn.close()
    return {"applications": applications}
```

### 5.3 자동 테넌트 온보딩

서비스 마켓에서 서비스 신청이 승인되면 자동으로 테넌트를 생성합니다.

```python
@router.post("/tenant/create")
async def create_tenant(request: Request, payload: TenantCreateRequest):
    """서비스 마켓에서 호출 - 자동 테넌트 생성"""

    # 1. tenants 테이블에 등록
    await conn.execute("""
        INSERT INTO hltutor.tenants
        (tenant_id, tenant_name, admin_email, application_id, application_kind, status)
        VALUES ($1, $2, $3, $4, $5, 'active')
    """, payload.tenant_id, payload.tenant_name, payload.admin_email,
        payload.application_id, payload.application_kind)

    # 2. 테넌트 스키마 생성
    await create_tenant_schema(conn, payload.tenant_id)

    # 3. 관리자 계정 생성
    await create_admin_user(conn, payload.tenant_id, payload.admin_email)

    return {
        "success": True,
        "tenant_id": payload.tenant_id,
        "access_url": f"https://myservice.k-university.ai?tenant={payload.tenant_id}"
    }
```

---

## 6. Webhook 구현

### 6.1 회원 탈퇴 Webhook

서비스 마켓에서 회원 탈퇴 시 해당 사용자의 테넌트를 삭제합니다.

```python
# routers/tenant.py
from pydantic import BaseModel

class WebhookUserDeleteRequest(BaseModel):
    event: str          # "user.deleted"
    user_id: int
    email: str
    university_name: Optional[str]
    deleted_at: str

@router.post("/webhook/user-deleted")
async def webhook_user_deleted(
    request: Request,
    payload: WebhookUserDeleteRequest,
    x_webhook_secret: str = Header(None)
):
    """서비스 마켓 회원 탈퇴 Webhook"""

    # 1. Webhook Secret 검증
    expected_secret = os.getenv("SERVICE_MARKET_WEBHOOK_SECRET", "webhook_secret_12345")
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # 2. 이벤트 타입 확인
    if payload.event != "user.deleted":
        return {"success": False, "message": f"Unsupported event: {payload.event}"}

    # 3. 해당 이메일로 생성된 테넌트 조회
    tenants = await conn.fetch("""
        SELECT tenant_id, tenant_name
        FROM hltutor.tenants
        WHERE admin_email = $1
    """, payload.email)

    # 4. 테넌트 상태를 'deleted'로 변경 (soft delete)
    deleted_tenants = []
    for tenant in tenants:
        await conn.execute("""
            UPDATE hltutor.tenants
            SET status = 'deleted',
                deleted_at = NOW(),
                deleted_reason = $1
            WHERE tenant_id = $2
        """, f"서비스 마켓 회원 탈퇴 (user_id={payload.user_id})", tenant["tenant_id"])

        deleted_tenants.append(tenant["tenant_id"])

    return {
        "success": True,
        "deleted_tenants": deleted_tenants
    }
```

### 6.2 서비스 해지 Webhook

```python
@router.post("/webhook/service-cancelled")
async def webhook_service_cancelled(
    request: Request,
    x_webhook_secret: str = Header(None)
):
    """서비스 마켓 서비스 해지 Webhook"""

    # Secret 검증
    expected_secret = os.getenv("SERVICE_MARKET_WEBHOOK_SECRET")
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    application_id = body.get("application_id")

    # 해당 신청 건의 테넌트 정지
    await conn.execute("""
        UPDATE hltutor.tenants
        SET status = 'suspended',
            suspended_at = NOW(),
            suspended_reason = '서비스 마켓 서비스 해지'
        WHERE application_id = $1
    """, application_id)

    return {"success": True}
```

### 6.3 서비스 마켓에서 Webhook 호출 코드

```python
# service_market/backend/app/api/v1/auth.py
@router.delete("/withdraw")
async def withdraw(request: Request, response: Response, db: Session = Depends(get_db)):
    """회원 탈퇴 시 연동 서비스에 Webhook 전송"""

    # ... 사용자 삭제 로직 ...

    # Webhook 전송
    webhook_url = os.getenv("KELI_TUTOR_WEBHOOK_URL",
                           "http://keli-test_univ-backend:8085/api/tenant/webhook/user-deleted")
    webhook_secret = os.getenv("KELI_TUTOR_WEBHOOK_SECRET", "webhook_secret_12345")

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            webhook_url,
            json={
                "event": "user.deleted",
                "user_id": user_id,
                "email": user_email,
                "university_name": university_name,
                "deleted_at": datetime.now().isoformat()
            },
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": webhook_secret
            }
        )

    return {"success": True, "message": "회원 탈퇴가 완료되었습니다."}
```

---

## 7. 테스트 방법

### 7.1 로컬 환경 테스트

#### 7.1.1 Docker 컨테이너 실행

```bash
# 서비스 시작
cd /home/aiedu/workspace/my_ai_service
docker-compose up -d

# 로그 확인
docker-compose logs -f backend
```

#### 7.1.2 테넌트 생성 테스트

```bash
# 테넌트 생성 API 테스트
curl -X POST "http://localhost:10201/api/tenant/create" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "tenant_id": "test_univ",
    "tenant_name": "테스트대학교",
    "admin_email": "admin@test.ac.kr",
    "admin_name": "관리자",
    "application_id": 1,
    "application_kind": "service"
  }'
```

#### 7.1.3 테넌트 API 테스트

```bash
# 테넌트별 API 호출
curl -X GET "http://localhost:10201/api/users" \
  -H "X-Tenant-ID: test_univ"
```

### 7.2 Webhook 테스트

#### 7.2.1 회원 탈퇴 Webhook 테스트

```bash
# 실제 테넌트가 있는 이메일로 테스트
curl -X POST "http://localhost:10201/api/tenant/webhook/user-deleted" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: webhook_secret_12345" \
  -d '{
    "event": "user.deleted",
    "user_id": 123,
    "email": "admin@test.ac.kr",
    "university_name": "테스트대학교",
    "deleted_at": "2026-01-08T10:00:00"
  }'

# 응답 예시
# {"success": true, "message": "Deleted 1 tenant(s)", "deleted_tenants": ["test_univ"]}
```

#### 7.2.2 테넌트 상태 확인

```bash
# PostgreSQL에서 테넌트 상태 확인
docker exec my-service-db psql -U user -d myservice -c \
  "SELECT tenant_id, status, deleted_at, deleted_reason FROM hltutor.tenants;"
```

### 7.3 통합 테스트

#### 7.3.1 E2E 테스트 스크립트

```python
# tests/e2e/test_tenant_lifecycle.py
import pytest
import httpx

BASE_URL = "http://localhost:10201/api"
WEBHOOK_SECRET = "webhook_secret_12345"

@pytest.mark.asyncio
async def test_tenant_lifecycle():
    """테넌트 생명주기 테스트: 생성 → 사용 → 삭제"""

    async with httpx.AsyncClient() as client:
        # 1. 테넌트 생성
        response = await client.post(
            f"{BASE_URL}/tenant/create",
            json={
                "tenant_id": "e2e_test",
                "tenant_name": "E2E 테스트",
                "admin_email": "e2e@test.com",
                "application_id": 999,
                "application_kind": "demo"
            },
            headers={"X-API-Key": "test_key"}
        )
        assert response.status_code == 200
        assert response.json()["success"] == True

        # 2. 테넌트 API 사용
        response = await client.get(
            f"{BASE_URL}/health",
            headers={"X-Tenant-ID": "e2e_test"}
        )
        assert response.status_code == 200

        # 3. Webhook으로 테넌트 삭제
        response = await client.post(
            f"{BASE_URL}/tenant/webhook/user-deleted",
            json={
                "event": "user.deleted",
                "user_id": 999,
                "email": "e2e@test.com",
                "deleted_at": "2026-01-08T10:00:00"
            },
            headers={"X-Webhook-Secret": WEBHOOK_SECRET}
        )
        assert response.status_code == 200
        assert "e2e_test" in response.json()["deleted_tenants"]
```

#### 7.3.2 테스트 실행

```bash
# pytest 실행
cd /home/aiedu/workspace/my_ai_service
pip install pytest pytest-asyncio httpx
pytest tests/e2e/ -v
```

---

## 8. 운영 가이드

### 8.1 모니터링

#### 8.1.1 테넌트별 사용량 조회 API

```python
@router.get("/superadmin/tenants/{tenant_id}/usage")
async def get_tenant_usage(tenant_id: str):
    """테넌트별 사용량 조회"""

    # 스키마 존재 확인
    schema_exists = await conn.fetchval("""
        SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = $1)
    """, tenant_id)

    if not schema_exists:
        raise HTTPException(status_code=404, detail="테넌트를 찾을 수 없습니다")

    # 사용량 조회
    await conn.execute(f"SET search_path TO {tenant_id}, public")

    user_count = await conn.fetchval("SELECT COUNT(*) FROM user_mst")
    chat_count = await conn.fetchval("SELECT COUNT(*) FROM chat_his")
    last_activity = await conn.fetchval("SELECT MAX(reg_dtm) FROM chat_his")

    return {
        "tenant_id": tenant_id,
        "usage": {
            "user_count": user_count,
            "chat_count": chat_count,
            "last_activity": last_activity.isoformat() if last_activity else None
        }
    }
```

#### 8.1.2 Docker 로그 모니터링

```bash
# 백엔드 로그 실시간 모니터링
docker logs -f my-service-backend --tail 100

# 에러만 필터링
docker logs my-service-backend 2>&1 | grep -i error
```

### 8.2 백업 및 복구

#### 8.2.1 테넌트별 데이터 백업

```bash
# 특정 테넌트 스키마만 백업
docker exec my-service-db pg_dump -U user -d myservice \
  -n univ_8 -f /backup/univ_8_backup.sql

# 전체 백업
docker exec my-service-db pg_dump -U user -d myservice \
  -f /backup/full_backup.sql
```

#### 8.2.2 데이터 복구

```bash
# 특정 테넌트 복구
docker exec -i my-service-db psql -U user -d myservice < univ_8_backup.sql
```

### 8.3 트러블슈팅

#### 문제 1: 테넌트 스키마가 생성되지 않음

```bash
# 스키마 목록 확인
docker exec my-service-db psql -U user -d myservice -c "\dn"

# 수동 스키마 생성
docker exec my-service-db psql -U user -d myservice -c "CREATE SCHEMA test_tenant"
```

#### 문제 2: Webhook 연결 실패

```bash
# 네트워크 연결 확인
docker network ls
docker network inspect servicemarket_service-market-network

# 네트워크 연결
docker network connect servicemarket_service-market-network my-service-backend
```

#### 문제 3: 서비스 마켓 DB 연결 실패

```bash
# 서비스 마켓 DB 컨테이너 상태 확인
docker ps | grep service-market-db

# 연결 테스트
docker exec my-service-backend python -c "
import pymysql
conn = pymysql.connect(host='service-market-db', port=3306, user='market_user', password='xxx', db='market_place_db')
print('Connected!')
conn.close()
"
```

---

## 9. KELI Tutor 구현 사례

실제 운영 중인 KELI Tutor의 멀티테넌트 구현을 참조하세요.

### 9.1 주요 파일 위치

```
/home/aiedu/workspace/keli_tutor/
├── backend/
│   ├── database/
│   │   ├── multi_tenant.py      # 멀티테넌트 핵심 로직
│   │   └── tenant_context.py    # 테넌트 컨텍스트 관리
│   ├── middleware/
│   │   └── tenant_middleware.py # 요청별 테넌트 식별
│   └── routers/
│       └── tenant.py            # 테넌트 관리 API (2700+ lines)
├── frontend/
│   └── src/
│       └── api/
│           └── axiosInstance.js # 테넌트 ID 자동 주입
└── docker-compose.test_univ.yml # 테넌트별 Docker 구성
```

### 9.2 핵심 구현 코드 참조

#### 테넌트 미들웨어
- 파일: `backend/middleware/tenant_middleware.py`
- 기능: X-Tenant-ID 헤더에서 테넌트 식별, 스키마 전환

#### 테넌트 관리 API
- 파일: `backend/routers/tenant.py`
- 주요 엔드포인트:
  - `POST /api/tenant/create` - 테넌트 생성
  - `GET /api/tenant/superadmin/tenants` - 테넌트 목록
  - `GET /api/tenant/superadmin/tenants/{id}/history` - 테넌트 히스토리
  - `POST /api/tenant/webhook/user-deleted` - 회원 탈퇴 Webhook

#### 프론트엔드 테넌트 처리
- 파일: `frontend/src/api/axiosInstance.js`
- 기능: URL 파라미터, 쿠키, 도메인에서 테넌트 ID 추출 및 API 요청에 자동 포함

### 9.3 운영 정보

| 항목 | 값 |
|------|-----|
| 도메인 | https://ktutor.k-university.ai |
| 프론트엔드 포트 | 10100 |
| 백엔드 포트 | 10101 |
| DB 포트 | 10102 |
| 중앙 스키마 | hltutor |
| 테넌트 예시 | univ_8 (광주대학교) |

---

## 부록

### A. 환경변수 설정

```bash
# .env 파일
DATABASE_URL=postgresql://user:pass@db:5432/myservice
SERVICE_MARKET_DB_HOST=service-market-db
SERVICE_MARKET_DB_PORT=3306
SERVICE_MARKET_WEBHOOK_SECRET=webhook_secret_12345
KELI_TUTOR_WEBHOOK_URL=http://keli-test_univ-backend:8085/api/tenant/webhook/user-deleted
```

### B. Docker 네트워크 구성

```bash
# 서비스 마켓 네트워크 확인
docker network ls | grep service-market

# 외부 서비스 연결
docker network connect servicemarket_service-market-network my-service-backend
```

### C. 유용한 SQL 쿼리

```sql
-- 모든 테넌트 조회
SELECT * FROM hltutor.tenants ORDER BY created_at DESC;

-- 활성 테넌트만 조회
SELECT * FROM hltutor.tenants WHERE status = 'active';

-- 스키마 목록 조회
SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'public');

-- 특정 테넌트의 사용자 수
SET search_path TO univ_8, public;
SELECT COUNT(*) FROM user_mst;
```

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 내용 |
|------|------|--------|------|
| 1.0 | 2026-01-08 | AI Developer | 초기 문서 작성 |

---

**문의**: developer@k-university.ai
