# Advisor 멀티 테넌트 기능 가이드

## 목차

1. [개요](#1-개요)
2. [아키텍처](#2-아키텍처)
3. [테넌트 격리 방식](#3-테넌트-격리-방식)
4. [테넌트 모델 및 스키마](#4-테넌트-모델-및-스키마)
5. [인증 및 인가](#5-인증-및-인가)
6. [테넌트 설정 관리](#6-테넌트-설정-관리)
7. [온보딩/오프보딩 프로세스](#7-온보딩오프보딩-프로세스)
8. [서비스 마켓 연동](#8-서비스-마켓-연동)
9. [사용량 로깅 및 빌링](#9-사용량-로깅-및-빌링)
10. [API 레퍼런스](#10-api-레퍼런스)
11. [파일 위치 요약](#11-파일-위치-요약)

---

## 1. 개요

Advisor는 대학교용 학사 정보 챗봇 시스템으로, **Database Per Tenant** 아키텍처로 멀티 테넌트를 구현합니다.

### 1.1 핵심 특징

| 항목 | 설명 |
|------|------|
| 격리 방식 | Database Per Tenant (테넌트별 전용 DB) |
| 인증 | JWT 토큰 (사용자), API Key (서비스) |
| 프로비저닝 | 자동 온보딩 (DB 생성 → 스키마 초기화 → 테스트 → 활성화) |
| 빌링 | 사용량 기반 (토큰, API 호출, 스토리지) |
| 서비스 마켓 | 표준 API를 통한 연동 |

### 1.2 기술 스택

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (asyncpg)
- **ORM**: SQLAlchemy (async)
- **Cache**: Redis
- **Auth**: JWT (python-jose), bcrypt

---

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                     Service Marketplace                          │
│                  (market.k-university.ai)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │ Webhook (표준 API)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Tenant PaaS (mt_paas)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ TenantMgr   │  │ Standard API│  │ Market Client│              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   Advisor     │ │  KELI Tutor   │ │  LLM Chatbot  │
│  (Backend)    │ │   (Backend)   │ │   (Backend)   │
└───────┬───────┘ └───────────────┘ └───────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Central DB      │  │ tenant_hallym   │  │ tenant_kookmin  │  │
│  │ (메타데이터)     │  │ (한림대 데이터)  │  │ (국민대 데이터)  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Advisor Backend 구조

```
/home/aiedu/workspace/advisor/backend/
├── database/
│   ├── engine.py              # DB 엔진 설정
│   ├── multi_tenant.py        # Schema Per Tenant 지원
│   ├── tenant_manager.py      # Database Per Tenant 관리
│   └── legacy.py              # 레거시 호환성
├── core/middleware/
│   └── tenant.py              # 요청별 테넌트 식별 미들웨어
├── routers/
│   ├── auth.py                # 인증 API
│   ├── admin.py               # 테넌트 관리자 API
│   ├── super_admin.py         # 슈퍼 관리자 API
│   └── rag_chat.py            # RAG 채팅 API
├── config.py                  # 중앙 설정
└── server.py                  # FastAPI 앱
```

---

## 3. 테넌트 격리 방식

### 3.1 Database Per Tenant (현재 방식)

각 테넌트가 **전용 PostgreSQL 데이터베이스**를 가짐:

```python
# 테넌트 DB URL 템플릿
TENANT_DB_URL_TEMPLATE = "postgresql+asyncpg://postgres:postgres@localhost:5434/tenant_{tenant_id}"

# Central DB (메타데이터)
CENTRAL_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5434/llm_chatbot_central"
```

**장점:**
- 완벽한 데이터 격리
- 테넌트별 성능 독립성
- 간단한 백업/복원 (DB 단위)
- 규정 준수 용이 (데이터 분리)

**단점:**
- 많은 테넌트 시 DB 관리 복잡
- 연결 풀 오버헤드

### 3.2 테넌트 DB 생성

```python
# tenant_manager.py
async def create_tenant_database(tenant_id: str) -> bool:
    """테넌트 전용 DB 생성"""
    db_name = f"tenant_{tenant_id}"
    admin_engine = create_async_engine(POSTGRES_ADMIN_URL, isolation_level="AUTOCOMMIT")

    async with admin_engine.connect() as conn:
        # DB 존재 확인
        result = await conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": db_name}
        )
        if result.fetchone():
            return True  # 이미 존재

        # 새 DB 생성
        await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        return True
```

### 3.3 테넌트 엔진 캐싱

```python
# 싱글톤 패턴 - 연결 풀 관리
_tenant_engines: Dict[str, Any] = {}

def get_tenant_engine(tenant_id: str):
    """테넌트 DB 엔진 반환 (캐싱)"""
    if tenant_id not in _tenant_engines:
        engine = create_async_engine(
            get_tenant_db_url(tenant_id),
            pool_size=5,
            max_overflow=10
        )
        _tenant_engines[tenant_id] = engine
    return _tenant_engines[tenant_id]
```

---

## 4. 테넌트 모델 및 스키마

### 4.1 Central DB 테이블

#### tenants 테이블

```sql
CREATE TABLE tenants (
    id VARCHAR(50) PRIMARY KEY,              -- 테넌트 ID (예: hallym)
    name VARCHAR(255),                        -- 테넌트 이름
    domain VARCHAR(255),                      -- 도메인 (예: hallym.ac.kr)
    db_name VARCHAR(100) UNIQUE,              -- 테넌트 DB 이름
    db_host VARCHAR(255) DEFAULT 'localhost',
    db_port INTEGER DEFAULT 5434,
    status VARCHAR(20) DEFAULT 'pending',     -- pending, provisioning, active, suspended, deleted
    onboarding_status VARCHAR(50),            -- 온보딩 진행 상태
    onboarding_log JSONB DEFAULT '[]',
    api_key VARCHAR(64) UNIQUE,               -- API 인증용
    api_key_hash VARCHAR(64),
    config JSONB,                             -- 테넌트 설정
    storage_quota_gb INTEGER DEFAULT 10,
    user_limit INTEGER DEFAULT 1000,
    daily_token_limit BIGINT DEFAULT 1000000,
    admin_email VARCHAR(255),
    contact_info JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP
);
```

#### usage_logs 테이블

```sql
CREATE TABLE usage_logs (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) REFERENCES tenants(id),
    log_date DATE NOT NULL,
    active_users INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    llm_tokens_used BIGINT DEFAULT 0,
    storage_used_mb REAL DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    api_usage JSONB DEFAULT '{}',
    estimated_cost_usd REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, log_date)
);
```

### 4.2 Tenant DB 스키마

각 테넌트의 개별 데이터베이스에 생성되는 테이블:

```sql
-- 사용자 테이블
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    display_name VARCHAR(255),
    email VARCHAR(255),
    role VARCHAR(20) DEFAULT 'user',     -- user, admin
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_login TIMESTAMP
);

-- 테넌트 관리자
CREATE TABLE tenant_admins (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'admin',
    permissions JSONB,
    created_at TIMESTAMP
);

-- 사용자 설정
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id),
    preferred_model VARCHAR(50) DEFAULT 'gpt4o',
    temperature REAL DEFAULT 0.7,
    system_prompt TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 채팅 세션
CREATE TABLE sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(500),
    model VARCHAR(50) DEFAULT 'gpt4o',
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 메시지
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES sessions(id),
    role VARCHAR(50),                   -- user, assistant
    content TEXT,
    tokens_used INTEGER,
    model VARCHAR(50),
    created_at TIMESTAMP
);

-- 첨부파일
CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id),
    session_id VARCHAR(255) REFERENCES sessions(id),
    user_id INTEGER REFERENCES users(id),
    filename VARCHAR(500),
    original_filename VARCHAR(500),
    file_type VARCHAR(50),
    file_size INTEGER,
    file_path VARCHAR(1000),
    created_at TIMESTAMP
);

-- 사용자 프로파일 (개인화)
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id),
    location VARCHAR(255),
    occupation VARCHAR(255),
    food_preferences JSONB,
    hobbies JSONB,
    communication_style JSONB,
    profile_summary TEXT,
    profile_embedding BYTEA,
    extraction_count INTEGER,
    last_extracted_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 사용자 팩트
CREATE TABLE user_facts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    category VARCHAR(50),               -- location, food, hobby, occupation, etc.
    fact_key VARCHAR(100),
    fact_value TEXT,
    confidence REAL DEFAULT 1.0,
    source_session_id VARCHAR(255),
    source_message_id INTEGER,
    is_active BOOLEAN DEFAULT true,
    invalidated_at TIMESTAMP,
    invalidated_reason TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_user_facts_user_id ON user_facts(user_id);
```

---

## 5. 인증 및 인가

### 5.1 사용자 인증 (JWT)

```python
# routers/auth.py

def create_access_token(user_id: int, username: str, tenant_id: str = None) -> str:
    """JWT 토큰 생성 (테넌트 정보 포함)"""
    expire = datetime.utcnow() + timedelta(hours=24)
    payload = {
        "sub": str(user_id),              # User ID
        "username": username,
        "tenant_id": tenant_id,           # 테넌트 ID 포함
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
) -> dict:
    """현재 사용자 조회 (의존성)"""
    token = credentials.credentials
    payload = verify_token(token)

    user_id = int(payload.get("sub"))
    tenant_id = payload.get("tenant_id") or x_tenant_id or DEFAULT_TENANT

    # 테넌트 DB에서 사용자 조회
    user = await get_tenant_user_by_id(tenant_id, user_id)
    user["tenant_id"] = tenant_id
    return user
```

### 5.2 테넌트 관리자 인증

```python
# routers/admin.py

async def verify_tenant_admin(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """테넌트 관리자 권한 검증"""
    tenant_id = get_tenant_id(request)
    user_id = current_user["id"]

    async with get_tenant_db_session(tenant_id) as session:
        # tenant_admins 테이블 확인
        result = await session.execute(
            text("SELECT * FROM tenant_admins WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        admin = result.mappings().first()

        if admin:
            return {"user": current_user, "admin": dict(admin), "tenant_id": tenant_id}

        # users 테이블에서 role 확인
        if current_user.get("role") == "admin":
            return {"user": current_user, "admin": None, "tenant_id": tenant_id}

    raise HTTPException(status_code=403, detail="Admin privileges required")
```

### 5.3 테넌트 식별 미들웨어

```python
# core/middleware/tenant.py

class TenantMiddleware(BaseHTTPMiddleware):
    """테넌트 식별 미들웨어"""

    async def dispatch(self, request: Request, call_next: Callable):
        # 공개 경로 확인
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # 테넌트 식별 (우선순위)
        tenant_info = await self._identify_tenant(request)

        if not tenant_info and self.default_tenant:
            tenant_info = {"id": self.default_tenant}

        if not tenant_info:
            raise HTTPException(status_code=400, detail="Tenant not identified")

        # 테넌트 상태 확인
        if tenant_info.get("status") not in ["active", None]:
            raise HTTPException(status_code=403, detail="Tenant is not active")

        # 요청 컨텍스트에 저장
        request.state.tenant = tenant_info
        request.state.tenant_id = tenant_info["id"]
        request.state.db_name = tenant_info.get("db_name", f"tenant_{tenant_info['id']}")

        return await call_next(request)

    async def _identify_tenant(self, request: Request) -> Optional[dict]:
        """테넌트 식별 (우선순위)"""

        # 1. API Key (X-API-Key 헤더)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return await self._get_tenant_by_api_key(api_key)

        # 2. X-Tenant-ID 헤더
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return await self._get_tenant_from_central_db(tenant_id)

        # 3. 서브도메인 (hallym.example.com → hallym)
        host = request.headers.get("host", "")
        if host:
            subdomain = host.split(".")[0]
            if subdomain not in ["www", "api", "admin"]:
                return await self._get_tenant_from_central_db(subdomain)

        # 4. 쿼리 파라미터 (?tenant=hallym)
        tenant_param = request.query_params.get("tenant")
        if tenant_param:
            return await self._get_tenant_from_central_db(tenant_param)

        return None
```

---

## 6. 테넌트 설정 관리

### 6.1 테넌트 설정 (tenants.config)

```python
# Central DB에 JSONB로 저장
config = {
    "plan": "premium",
    "max_users": 500,
    "allowed_models": ["gpt4o", "gpt4o-mini", "claude-sonnet"],
    "default_model": "gpt4o",
    "storage_quota_gb": 50,
    "daily_token_limit": 5000000,
    "enable_web_search": True,
    "enable_rag": True,
    "enable_profile_extraction": True
}

# 테넌트 생성 시 설정
await create_tenant(
    tenant_id="hallym",
    name="한림대학교",
    config=config
)

# 테넌트 설정 업데이트
async def update_tenant(tenant_id: str, **kwargs):
    allowed_fields = ['name', 'domain', 'status', 'config',
                     'storage_quota_gb', 'user_limit', 'daily_token_limit']
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    # UPDATE tenants SET ... WHERE id = :id
```

### 6.2 사용자 설정 (user_preferences)

```python
async def get_tenant_user_preferences(tenant_id: str, user_id: int):
    """사용자 설정 조회"""
    async with get_tenant_db_session(tenant_id) as session:
        result = await session.execute(
            text("SELECT * FROM user_preferences WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        return dict(result.mappings().first())

async def update_tenant_user_preferences(tenant_id: str, user_id: int, **kwargs):
    """사용자 설정 업데이트"""
    # UPSERT 로직
```

---

## 7. 온보딩/오프보딩 프로세스

### 7.1 자동 온보딩 프로세스

```python
# tenant_manager.py

async def onboard_tenant(
    tenant_id: str,
    name: str,
    domain: str = None,
    admin_email: str = None,
    config: Dict = None
) -> Dict:
    """
    테넌트 자동 온보딩

    단계:
    1. Central DB에 테넌트 정보 등록 (provisioning 상태)
    2. 테넌트 전용 DB 생성
    3. 스키마 초기화
    4. 자동 테스트 실행
    5. 테넌트 관리자 계정 생성
    6. 활성화
    """
    result = {
        "tenant_id": tenant_id,
        "status": "failed",
        "api_key": None,
        "steps": [],
        "test_results": None,
        "error": None
    }

    try:
        # Step 1: Central DB에 등록
        api_key, api_key_hash = generate_api_key()
        db_name = get_tenant_db_name(tenant_id)

        async with get_central_db() as session:
            await session.execute(text("""
                INSERT INTO tenants (id, name, domain, db_name, admin_email,
                                   config, api_key, api_key_hash, status, onboarding_status)
                VALUES (:id, :name, :domain, :db_name, :admin_email,
                       CAST(:config AS jsonb), :api_key, :api_key_hash,
                       'provisioning', 'started')
            """), {...})

        result["steps"].append({"step": "register", "status": "success"})

        # Step 2: DB 생성
        await create_tenant_database(tenant_id)
        result["steps"].append({"step": "create_db", "status": "success"})

        # Step 3: 스키마 초기화
        await init_tenant_schema(tenant_id)
        result["steps"].append({"step": "init_schema", "status": "success"})

        # Step 4: 자동 테스트
        test_results = await run_tenant_tests(tenant_id)
        result["test_results"] = test_results.to_dict()

        if not test_results.passed:
            raise Exception("Tenant tests failed")
        result["steps"].append({"step": "test", "status": "success"})

        # Step 5: 관리자 계정 생성
        await create_tenant_admin(tenant_id, admin_email)
        result["steps"].append({"step": "create_admin", "status": "success"})

        # Step 6: 활성화
        async with get_central_db() as session:
            await session.execute(text("""
                UPDATE tenants
                SET status = 'active', onboarding_status = 'completed',
                    activated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """), {"id": tenant_id})

        result["steps"].append({"step": "activate", "status": "success"})
        result["status"] = "success"
        result["api_key"] = api_key

    except Exception as e:
        result["error"] = str(e)
        # 실패 시 상태 업데이트
        ...

    return result
```

### 7.2 자동 테스트

```python
async def run_tenant_tests(tenant_id: str) -> TenantTestResult:
    """테넌트 DB에 대한 자동 테스트"""
    result = TenantTestResult()

    # 1. DB 연결 테스트
    try:
        async with get_tenant_db_session(tenant_id) as session:
            await session.execute(text("SELECT 1"))
        result.add_test("db_connection", True)
    except Exception as e:
        result.add_test("db_connection", False, error=str(e))
        return result

    # 2. 테이블 존재 확인
    required_tables = ["users", "sessions", "messages", "attachments",
                      "user_preferences", "tenant_admins"]
    # ... 테이블 확인 ...

    # 3. CRUD 테스트
    # INSERT → SELECT → DELETE 테스트

    # 4. 인덱스 확인
    # ...

    return result
```

### 7.3 오프보딩 프로세스

```python
async def offboard_tenant(
    tenant_id: str,
    backup: bool = True,
    retention_days: int = 30
) -> Dict:
    """
    테넌트 오프보딩

    단계:
    1. 상태를 deactivating으로 변경
    2. (선택) 백업 생성
    3. DB 삭제
    4. Central DB에서 상태 업데이트
    """
    result = {"tenant_id": tenant_id, "status": "failed", "steps": []}

    try:
        # Step 1: 상태 변경
        async with get_central_db() as session:
            await session.execute(text("""
                UPDATE tenants SET status = 'deactivating' WHERE id = :id
            """), {"id": tenant_id})

        # Step 2: 백업 (선택)
        if backup:
            # pg_dump 실행
            pass

        # Step 3: DB 삭제
        await drop_tenant_database(tenant_id)

        # Step 4: Central DB 업데이트
        async with get_central_db() as session:
            await session.execute(text("""
                UPDATE tenants
                SET status = 'deleted', deactivated_at = CURRENT_TIMESTAMP, api_key = NULL
                WHERE id = :id
            """), {"id": tenant_id})

        result["status"] = "success"

    except Exception as e:
        result["error"] = str(e)

    return result
```

---

## 8. 서비스 마켓 연동

### 8.1 아키텍처

```
Service Marketplace                    AI Service (Advisor)
        │                                    │
        ├─ 테넌트 생성 신청 ─────────────────>│
        │                    Webhook          │
        │                    ActivateRequest  │
        │                                    │
        │                    <─ ActivateResponse ─┤
        │                    (tenant_id, url)     │
        │                                    │
        │                    테넌트 DB 생성
        │                    구독 정보 저장
```

### 8.2 표준 API (Standard API)

모든 AI 서비스가 구현해야 하는 인터페이스:

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/mt/health` | GET | 헬스체크 |
| `/mt/tenant/{tenant_id}/activate` | POST | 테넌트 활성화 |
| `/mt/tenant/{tenant_id}/deactivate` | POST | 테넌트 비활성화 |
| `/mt/tenant/{tenant_id}/status` | GET | 상태 조회 |
| `/mt/tenant/{tenant_id}/usage` | GET | 사용량 조회 |
| `/mt/tenant/{tenant_id}/billing/usage` | GET | 빌링용 사용량 |

### 8.3 활성화 요청/응답

**요청 (ActivateRequest):**
```json
{
    "tenant_id": "hallym_univ",
    "tenant_name": "한림대학교",
    "plan": "premium",
    "features": ["ai_chat", "rag", "quiz"],
    "config": {"max_users": 500},
    "contact": {
        "email": "admin@hallym.ac.kr",
        "name": "홍길동"
    }
}
```

**응답 (ActivateResponse):**
```json
{
    "success": true,
    "tenant_id": "hallym_univ",
    "access_url": "https://advisor.example.com/hallym",
    "message": "Tenant activated successfully"
}
```

### 8.4 StandardAPIHandler 구현

```python
from mt_paas.standard_api import StandardAPIHandler, create_standard_router

class AdvisorHandler(StandardAPIHandler):
    @property
    def base_url(self) -> str:
        return "https://advisor.example.com"

    async def activate_tenant(self, request: ActivateRequest) -> ActivateResponse:
        # 온보딩 프로세스 실행
        result = await onboard_tenant(
            tenant_id=request.tenant_id,
            name=request.tenant_name,
            admin_email=request.contact.email,
            config={"plan": request.plan, "features": request.features}
        )

        return ActivateResponse(
            success=result["status"] == "success",
            tenant_id=request.tenant_id,
            access_url=f"{self.base_url}/{request.tenant_id}",
            message=result.get("error") or "Tenant activated"
        )

    async def deactivate_tenant(self, tenant_id: str, request: DeactivateRequest):
        result = await offboard_tenant(
            tenant_id=tenant_id,
            backup=request.preserve_data
        )
        return DeactivateResponse(...)

    async def get_tenant_status(self, tenant_id: str):
        tenant = await get_tenant(tenant_id)
        return StatusResponse(
            tenant_id=tenant_id,
            status=tenant["status"],
            plan=tenant["config"].get("plan", "basic"),
            features=tenant["config"].get("features", [])
        )

    async def get_tenant_usage(self, tenant_id: str, period: str):
        usage = await get_usage_logs(tenant_id, period)
        return UsageResponse(
            tenant_id=tenant_id,
            period=period,
            usage=UsageData(
                active_users=usage["active_users"],
                api_calls=usage["api_calls"],
                ai_tokens=usage["llm_tokens_used"],
                storage_mb=usage["storage_used_mb"]
            )
        )

# 라우터 생성 및 등록
router = create_standard_router(
    handler=AdvisorHandler(),
    prefix="/mt",
    api_key_header="X-Market-API-Key"
)
app.include_router(router)
```

### 8.5 서비스 매니페스트

```yaml
# manifest.yaml
service:
  name: Advisor
  version: 1.0.0
  description: "대학교용 학사 정보 RAG 챗봇"
  category: education

endpoints:
  base_url: https://advisor.example.com
  health_check: /mt/health
  activate: /mt/tenant/{tenant_id}/activate
  deactivate: /mt/tenant/{tenant_id}/deactivate
  status: /mt/tenant/{tenant_id}/status
  usage: /mt/tenant/{tenant_id}/usage

auth:
  type: api_key
  header_name: X-Market-API-Key

plans:
  - name: basic
    display_name: "기본"
    max_users: 100
    max_storage_mb: 5000
    features: ["ai_chat", "file_upload"]
    price_monthly: 99000

  - name: premium
    display_name: "프리미엄"
    max_users: 1000
    max_storage_mb: 50000
    features: ["ai_chat", "file_upload", "rag", "quiz"]
    price_monthly: 299000

usage_metrics:
  - name: api_calls
    type: counter
    unit: calls
  - name: ai_tokens
    type: counter
    unit: tokens
  - name: storage_mb
    type: gauge
    unit: MB
```

---

## 9. 사용량 로깅 및 빌링

### 9.1 사용량 로깅

```python
async def log_usage(
    tenant_id: str,
    messages: int = 0,
    tokens: int = 0,
    api_calls: int = 0
):
    """사용량 로깅 (일별 집계)"""
    today = date.today()

    async with get_db() as session:
        # UPSERT
        await session.execute(
            text("""
                INSERT INTO usage_logs (tenant_id, log_date, total_messages,
                                       llm_tokens_used, api_calls)
                VALUES (:tenant_id, :log_date, :messages, :tokens, :api_calls)
                ON CONFLICT (tenant_id, log_date)
                DO UPDATE SET
                    total_messages = usage_logs.total_messages + :messages,
                    llm_tokens_used = usage_logs.llm_tokens_used + :tokens,
                    api_calls = usage_logs.api_calls + :api_calls
            """),
            {
                "tenant_id": tenant_id,
                "log_date": today,
                "messages": messages,
                "tokens": tokens,
                "api_calls": api_calls
            }
        )
```

### 9.2 비용 계산

```python
# utils/cost_calculator.py

MODEL_PRICING = {
    "gpt4o": {"input": 0.015, "output": 0.06},      # per 1K tokens
    "gpt4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-sonnet": {"input": 0.003, "output": 0.015},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """토큰 사용량 기반 비용 계산"""
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return input_cost + output_cost

async def get_billing_summary(tenant_id: str, period: str) -> Dict:
    """빌링 요약 조회"""
    usage = await get_usage_logs(tenant_id, period)

    return {
        "tenant_id": tenant_id,
        "period": period,
        "items": [
            {
                "name": "API Calls",
                "quantity": usage["api_calls"],
                "unit_price": 10,  # per 1000 calls
                "amount": (usage["api_calls"] / 1000) * 10
            },
            {
                "name": "AI Tokens",
                "quantity": usage["llm_tokens_used"],
                "unit_price": 50,  # per 1M tokens
                "amount": (usage["llm_tokens_used"] / 1000000) * 50
            },
            {
                "name": "Storage",
                "quantity": usage["storage_used_mb"],
                "unit_price": 10000,  # per 10GB
                "amount": (usage["storage_used_mb"] / 10240) * 10000
            }
        ],
        "total": ...
    }
```

### 9.3 빌링 API 응답 예시

```json
{
    "tenant_id": "hallym_univ",
    "period": "2026-01",
    "items": [
        {
            "name": "API Calls",
            "unit": "1000 calls",
            "quantity": 15,
            "unit_price": 10000,
            "amount": 150000
        },
        {
            "name": "AI Tokens",
            "unit": "1M tokens",
            "quantity": 0.5,
            "unit_price": 100000,
            "amount": 50000
        },
        {
            "name": "Storage",
            "unit": "10GB",
            "quantity": 2.56,
            "unit_price": 100000,
            "amount": 256000
        }
    ],
    "subtotal": 456000,
    "tax": 45600,
    "total": 501600,
    "currency": "KRW"
}
```

---

## 10. API 레퍼런스

### 10.1 인증 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/auth/signup` | POST | 회원가입 |
| `/api/auth/login` | POST | 로그인 |
| `/api/auth/me` | GET | 현재 사용자 정보 |
| `/api/auth/verify` | POST | 토큰 검증 |

### 10.2 테넌트 관리 API (Admin)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/admin/users` | GET | 사용자 목록 |
| `/api/admin/users/{id}` | GET/PUT/DELETE | 사용자 관리 |
| `/api/admin/stats` | GET | 통계 조회 |

### 10.3 슈퍼 관리자 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/super/tenants` | GET | 테넌트 목록 |
| `/api/super/tenants/onboard` | POST | 테넌트 온보딩 |
| `/api/super/tenants/{id}` | GET | 테넌트 정보 |
| `/api/super/tenants/{id}/health-check` | POST | 헬스체크 |
| `/api/super/tenants/{id}/offboard` | POST | 테넌트 오프보딩 |

### 10.4 표준 API (Service Market 연동)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/mt/health` | GET | 헬스체크 |
| `/mt/tenant/{id}/activate` | POST | 테넌트 활성화 |
| `/mt/tenant/{id}/deactivate` | POST | 테넌트 비활성화 |
| `/mt/tenant/{id}/status` | GET | 상태 조회 |
| `/mt/tenant/{id}/usage` | GET | 사용량 조회 |
| `/mt/tenant/{id}/billing/usage` | GET | 빌링용 사용량 |
| `/mt/tenant/{id}/billing/detail` | GET | 상세 빌링 정보 |

---

## 11. 파일 위치 요약

### 11.1 Advisor Backend

| 파일 | 설명 |
|------|------|
| `/home/aiedu/workspace/advisor/backend/database/tenant_manager.py` | 테넌트 DB 관리 (핵심) |
| `/home/aiedu/workspace/advisor/backend/database/engine.py` | DB 엔진 설정 |
| `/home/aiedu/workspace/advisor/backend/core/middleware/tenant.py` | 테넌트 미들웨어 |
| `/home/aiedu/workspace/advisor/backend/routers/auth.py` | 인증 API |
| `/home/aiedu/workspace/advisor/backend/routers/admin.py` | 관리자 API |
| `/home/aiedu/workspace/advisor/backend/routers/super_admin.py` | 슈퍼 관리자 API |
| `/home/aiedu/workspace/advisor/backend/config.py` | 설정 관리 |
| `/home/aiedu/workspace/advisor/backend/server.py` | FastAPI 앱 |

### 11.2 Multi-Tenant PaaS

| 파일 | 설명 |
|------|------|
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/core/manager.py` | TenantManager |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/core/models.py` | Tenant, Subscription 모델 |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/middleware/tenant.py` | ContextVar 기반 미들웨어 |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/market/client.py` | ServiceMarketClient |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/market/api.py` | Market API |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/market/models.py` | Market 모델 |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/standard_api/handler.py` | StandardAPIHandler |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/standard_api/router.py` | 표준 API 라우터 |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/manifest/` | 서비스 매니페스트 |
| `/home/aiedu/workspace/multi_tenant_paas/mt_paas/config.py` | 설정 관리 |

---

## 12. 주요 클래스 요약

| 클래스 | 위치 | 설명 |
|--------|------|------|
| `TenantMiddleware` | advisor/core/middleware/tenant.py | 요청별 테넌트 식별 |
| `TenantManager` | mt_paas/core/manager.py | 테넌트 CRUD |
| `Tenant` | mt_paas/core/models.py | 테넌트 모델 |
| `Subscription` | mt_paas/core/models.py | 구독 모델 |
| `ServiceClient` | mt_paas/market/client.py | 서비스 통신 클라이언트 |
| `ServiceMarketClient` | mt_paas/market/client.py | 통합 마켓 클라이언트 |
| `StandardAPIHandler` | mt_paas/standard_api/handler.py | 서비스 구현 추상 클래스 |
| `ManifestValidator` | mt_paas/manifest/validator.py | 매니페스트 검증 |

---

*최종 업데이트: 2026-01-10*
