# Standard API 확장 계획: Service Market 대시보드 연동

> 작성일: 2026-01-30
> 목적: 코드 중복 제거 및 인터페이스 통일을 위한 mt_paas Standard API 확장

---

## 1. 현재 문제점

### 1.1 인터페이스 불일치

| 계층 | Service Market 기대 | advisor 현재 | llm_chatbot 현재 |
|------|---------------------|--------------|------------------|
| 프로비저닝 | `/api/tenant/webhook/auto-provision` | `/api/marketplace/demo/request` | `/api/marketplace/demo/provision` |
| 통계 조회 | `/api/tenant/stats/{id}` | `/admin/dashboard` | `/admin/dashboard` |
| 사용자 목록 | `/api/tenant/users/{id}` | `/admin/users` | `/admin/users` |
| 인증 헤더 | `X-API-Key` | `X-Marketplace-Key` | `Bearer Token` |

### 1.2 mt_paas Standard API 현재 범위

```
현재 정의된 API (테넌트 생명주기만)
├── GET  /mt/health                     ✅
├── POST /mt/tenant/{id}/activate       ✅
├── POST /mt/tenant/{id}/deactivate     ✅
├── GET  /mt/tenant/{id}/status         ✅
└── GET  /mt/tenant/{id}/usage          ✅

누락된 API (대시보드/관리 기능)
├── GET  /mt/tenant/{id}/stats          ❌
├── GET  /mt/tenant/{id}/users          ❌
├── POST /mt/tenant/{id}/users          ❌
├── GET  /mt/tenant/{id}/costs          ❌
└── GET  /mt/tenant/{id}/settings       ❌
```

---

## 2. 확장된 Standard API 설계

### 2.1 API 구조 개요

```
mt_paas Standard API v2
│
├── 생명주기 관리 (Lifecycle) - 기존 유지
│   ├── POST /mt/tenant/{id}/activate
│   ├── POST /mt/tenant/{id}/deactivate
│   └── GET  /mt/tenant/{id}/status
│
├── 대시보드 데이터 (Dashboard) - 신규
│   ├── GET  /mt/tenant/{id}/stats
│   ├── GET  /mt/tenant/{id}/stats/usage-patterns
│   ├── GET  /mt/tenant/{id}/stats/costs
│   └── GET  /mt/tenant/{id}/stats/top-users
│
├── 사용자 관리 (Users) - 신규
│   ├── GET  /mt/tenant/{id}/users
│   ├── POST /mt/tenant/{id}/users
│   ├── GET  /mt/tenant/{id}/users/{user_id}
│   ├── PUT  /mt/tenant/{id}/users/{user_id}
│   └── DELETE /mt/tenant/{id}/users/{user_id}
│
├── 설정 관리 (Settings) - 신규
│   ├── GET  /mt/tenant/{id}/settings
│   ├── PUT  /mt/tenant/{id}/settings
│   └── GET  /mt/tenant/{id}/limits
│
└── 헬스체크 (Health)
    └── GET  /mt/health
```

### 2.2 Service Market 호환 엔드포인트 (Alias)

Service Market의 기존 기대치와 호환성을 위한 alias 경로:

```
Service Market 호환 경로           →  mt_paas 표준 경로
───────────────────────────────────────────────────────
/api/tenant/webhook/auto-provision → POST /mt/tenant/{id}/activate
/api/tenant/stats/{id}             → GET  /mt/tenant/{id}/stats
/api/tenant/users/{id}             → GET  /mt/tenant/{id}/users
/api/tenant/courses/{id}           → GET  /mt/tenant/{id}/resources?type=course
/api/tenant/discussions/{id}       → GET  /mt/tenant/{id}/resources?type=discussion
```

---

## 3. API 상세 스펙

### 3.1 대시보드 통계 API

#### `GET /mt/tenant/{tenant_id}/stats`

**용도:** Service Market 대시보드에서 테넌트 요약 정보 표시

**Request:**
```http
GET /mt/tenant/hallym_univ/stats?period=30d
X-Market-API-Key: {api_key}
```

**Response:**
```json
{
  "tenant_id": "hallym_univ",
  "period": "30d",
  "summary": {
    "total_users": 1250,
    "active_users": 890,
    "new_users_this_period": 45,
    "total_sessions": 15680,
    "total_messages": 89450,
    "total_tokens": 12500000,
    "estimated_cost_usd": 125.50
  },
  "trends": {
    "daily": [
      {"date": "2026-01-29", "users": 120, "messages": 3200, "tokens": 450000},
      {"date": "2026-01-28", "users": 115, "messages": 2980, "tokens": 420000}
    ]
  },
  "health": {
    "status": "healthy",
    "last_check": "2026-01-30T10:00:00Z",
    "response_time_ms": 45
  }
}
```

#### `GET /mt/tenant/{tenant_id}/stats/costs`

**용도:** 비용 분석 대시보드

**Response:**
```json
{
  "tenant_id": "hallym_univ",
  "period": "30d",
  "total_cost_usd": 125.50,
  "by_model": [
    {"model": "gpt-4", "input_tokens": 5000000, "output_tokens": 2000000, "cost_usd": 85.00},
    {"model": "gpt-3.5-turbo", "input_tokens": 4000000, "output_tokens": 1500000, "cost_usd": 40.50}
  ],
  "by_user_top10": [
    {"user_id": "user_123", "name": "김철수", "cost_usd": 15.20, "tokens": 1200000}
  ],
  "daily_trend": [
    {"date": "2026-01-29", "cost_usd": 4.50}
  ]
}
```

### 3.2 사용자 관리 API

#### `GET /mt/tenant/{tenant_id}/users`

**용도:** Service Market에서 테넌트 사용자 목록 조회

**Request:**
```http
GET /mt/tenant/hallym_univ/users?role=admin&limit=20&offset=0
X-Market-API-Key: {api_key}
```

**Response:**
```json
{
  "tenant_id": "hallym_univ",
  "total": 1250,
  "limit": 20,
  "offset": 0,
  "users": [
    {
      "user_id": "user_123",
      "email": "admin@hallym.ac.kr",
      "name": "관리자",
      "role": "admin",
      "status": "active",
      "created_at": "2025-09-01T00:00:00Z",
      "last_login": "2026-01-30T09:00:00Z",
      "usage": {
        "sessions": 150,
        "messages": 2340,
        "tokens": 350000
      }
    }
  ]
}
```

#### `POST /mt/tenant/{tenant_id}/users`

**용도:** Service Market에서 테넌트 사용자 생성

**Request:**
```json
{
  "email": "newuser@hallym.ac.kr",
  "name": "신규 사용자",
  "role": "user",
  "password": "temp_password_123",
  "send_welcome_email": true
}
```

**Response:**
```json
{
  "user_id": "user_456",
  "email": "newuser@hallym.ac.kr",
  "name": "신규 사용자",
  "role": "user",
  "status": "active",
  "created_at": "2026-01-30T10:30:00Z",
  "temporary_password": true
}
```

### 3.3 리소스 조회 API (범용)

#### `GET /mt/tenant/{tenant_id}/resources`

**용도:** 코스, 토론, 문서 등 서비스별 리소스 통합 조회

**Request:**
```http
GET /mt/tenant/hallym_univ/resources?type=course&limit=20
X-Market-API-Key: {api_key}
```

**Response:**
```json
{
  "tenant_id": "hallym_univ",
  "resource_type": "course",
  "total": 45,
  "items": [
    {
      "id": "course_001",
      "title": "AI 개론",
      "created_by": "user_123",
      "created_at": "2025-10-01T00:00:00Z",
      "stats": {
        "participants": 35,
        "discussions": 120,
        "documents": 15
      }
    }
  ]
}
```

### 3.4 설정 관리 API

#### `GET /mt/tenant/{tenant_id}/settings`

**Response:**
```json
{
  "tenant_id": "hallym_univ",
  "config": {
    "max_users": 2000,
    "max_storage_mb": 10240,
    "features": {
      "rag": true,
      "chat": true,
      "quiz": false,
      "api_integration": true
    },
    "limits": {
      "daily_tokens": 1000000,
      "monthly_tokens": 20000000,
      "max_file_size_mb": 50
    },
    "branding": {
      "logo_url": "https://...",
      "primary_color": "#003366"
    }
  },
  "subscription": {
    "plan": "premium",
    "start_date": "2025-09-01",
    "end_date": "2026-08-31",
    "auto_renew": true
  }
}
```

---

## 4. 인증 체계 통일

### 4.1 API Key 기반 인증 (표준)

```http
# Service Market → 서비스 호출
X-Market-API-Key: {service_market_api_key}

# 서비스 → Service Market 콜백
X-Service-API-Key: {service_api_key}
```

### 4.2 인증 플로우

```
┌─────────────────┐     X-Market-API-Key     ┌─────────────────┐
│  Service Market │ ──────────────────────→  │  advisor        │
│                 │                          │  llm_chatbot    │
│                 │  ←────────────────────── │                 │
│                 │     Response + Callback  │                 │
└─────────────────┘                          └─────────────────┘
        │                                            │
        │  X-Service-API-Key (콜백 시)                │
        └────────────────────────────────────────────┘
```

### 4.3 mt_paas 미들웨어 설정

```python
from mt_paas.middleware import MarketAuthMiddleware

app.add_middleware(
    MarketAuthMiddleware,
    api_key_header="X-Market-API-Key",
    valid_keys=["market_key_123", "market_key_456"],  # 또는 환경변수
    exclude_paths=["/mt/health", "/docs"]
)
```

---

## 5. 구현 계획

### 5.1 mt_paas 확장 (Phase 1)

**새로 추가할 파일:**

```
mt_paas/
├── standard_api/
│   ├── handler.py          # 기존 + 확장 메서드 추가
│   ├── models.py           # 기존 + 새 스키마 추가
│   ├── router.py           # 기존 + 새 엔드포인트 추가
│   ├── dashboard.py        # 신규: 대시보드 핸들러
│   └── users.py            # 신규: 사용자 관리 핸들러
├── middleware/
│   ├── tenant.py           # 기존
│   └── market_auth.py      # 신규: Service Market 인증
└── compat/
    └── service_market.py   # 신규: 호환성 alias 라우터
```

**StandardAPIHandler 확장:**

```python
class StandardAPIHandler(ABC):
    # 기존 메서드 (생명주기)
    @abstractmethod
    async def activate_tenant(self, request: ActivateRequest) -> ActivateResponse: ...

    @abstractmethod
    async def deactivate_tenant(self, tenant_id: str, request: DeactivateRequest) -> DeactivateResponse: ...

    # 신규 메서드 (대시보드)
    @abstractmethod
    async def get_tenant_stats(self, tenant_id: str, period: str) -> StatsResponse: ...

    @abstractmethod
    async def get_tenant_costs(self, tenant_id: str, period: str) -> CostsResponse: ...

    # 신규 메서드 (사용자 관리)
    @abstractmethod
    async def list_users(self, tenant_id: str, filters: UserFilters) -> UsersListResponse: ...

    @abstractmethod
    async def create_user(self, tenant_id: str, request: CreateUserRequest) -> UserResponse: ...

    @abstractmethod
    async def update_user(self, tenant_id: str, user_id: str, request: UpdateUserRequest) -> UserResponse: ...

    @abstractmethod
    async def delete_user(self, tenant_id: str, user_id: str) -> DeleteResponse: ...

    # 신규 메서드 (리소스)
    @abstractmethod
    async def list_resources(self, tenant_id: str, resource_type: str, filters: ResourceFilters) -> ResourcesResponse: ...

    # 신규 메서드 (설정)
    @abstractmethod
    async def get_settings(self, tenant_id: str) -> SettingsResponse: ...

    @abstractmethod
    async def update_settings(self, tenant_id: str, request: UpdateSettingsRequest) -> SettingsResponse: ...
```

### 5.2 서비스 구현 (Phase 2)

**advisor/llm_chatbot에서 구현:**

```python
from mt_paas.standard_api import StandardAPIHandler

class AdvisorHandler(StandardAPIHandler):
    async def get_tenant_stats(self, tenant_id: str, period: str) -> StatsResponse:
        # 기존 /admin/dashboard 로직 재사용
        async with self.get_tenant_session(tenant_id) as session:
            users = await self._count_users(session)
            messages = await self._count_messages(session, period)
            tokens = await self._sum_tokens(session, period)
            return StatsResponse(
                tenant_id=tenant_id,
                summary=StatsSummary(
                    total_users=users,
                    total_messages=messages,
                    total_tokens=tokens
                )
            )

    async def list_users(self, tenant_id: str, filters: UserFilters) -> UsersListResponse:
        # 기존 /admin/users 로직 재사용
        ...
```

### 5.3 Service Market 업데이트 (Phase 3)

**호출 방식 변경:**

```python
# 기존 (커스텀)
response = await client.get(f"{endpoint}/api/tenant/stats/{tenant_id}")

# 변경 후 (표준 API)
response = await client.get(
    f"{endpoint}/mt/tenant/{tenant_id}/stats",
    headers={"X-Market-API-Key": api_key}
)
```

---

## 6. 테스트 도구 확장

### 6.1 SDK 테스트 항목 추가

```python
# sandbox/sdk/tester.py 확장

class WebhookTester:
    async def test_stats_endpoint(self):
        """대시보드 통계 API 테스트"""
        response = await self.client.get(f"/mt/tenant/{self.test_tenant}/stats")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "total_users" in data["summary"]

    async def test_users_crud(self):
        """사용자 관리 CRUD 테스트"""
        # Create
        user = await self.client.post(f"/mt/tenant/{self.test_tenant}/users", json={...})
        assert user.status_code == 201

        # Read
        users = await self.client.get(f"/mt/tenant/{self.test_tenant}/users")
        assert users.status_code == 200

        # Update
        updated = await self.client.put(f"/mt/tenant/{self.test_tenant}/users/{user_id}", json={...})
        assert updated.status_code == 200

        # Delete
        deleted = await self.client.delete(f"/mt/tenant/{self.test_tenant}/users/{user_id}")
        assert deleted.status_code == 204
```

### 6.2 CLI 테스트 명령어

```bash
# 전체 테스트
python cli.py test --target http://advisor:8000 --key $API_KEY --full

# 대시보드 API만 테스트
python cli.py test --target http://advisor:8000 --key $API_KEY --suite dashboard

# 사용자 관리 API만 테스트
python cli.py test --target http://advisor:8000 --key $API_KEY --suite users
```

---

## 7. 마이그레이션 가이드

### 7.1 advisor 마이그레이션

```python
# Step 1: mt_paas 의존성 추가
# requirements.txt
mt-paas>=0.2.0

# Step 2: 핸들러 구현
# backend/handlers/market_handler.py
from mt_paas.standard_api import StandardAPIHandler

class AdvisorMarketHandler(StandardAPIHandler):
    def __init__(self, db_manager):
        self.db = db_manager

    async def get_tenant_stats(self, tenant_id, period):
        # 기존 dashboard.py 로직 이동
        ...

# Step 3: 라우터 등록
# backend/server.py
from mt_paas.standard_api import create_standard_router
from handlers.market_handler import AdvisorMarketHandler

handler = AdvisorMarketHandler(db_manager)
market_router = create_standard_router(handler)
app.include_router(market_router)

# Step 4: 기존 엔드포인트 deprecate
# backend/routers/marketplace.py
@router.post("/api/marketplace/demo/request")
@deprecated(reason="Use /mt/tenant/{id}/activate instead")
async def legacy_demo_request(...):
    ...
```

### 7.2 호환성 유지 기간

```
Phase 1 (0-2주):  새 API + 기존 API 병행
Phase 2 (2-4주):  기존 API에 deprecation warning
Phase 3 (4-6주):  기존 API 제거, 새 API만 유지
```

---

## 8. 예상 효과

### 8.1 코드 감소

| 서비스 | 현재 | 변경 후 | 감소 |
|--------|------|---------|------|
| advisor/tenant_manager.py | 1,051줄 | 0줄 | -100% |
| advisor/marketplace.py | 26KB | ~5KB (핸들러만) | -80% |
| llm_chatbot/tenant_manager.py | 1,119줄 | 0줄 | -100% |
| llm_chatbot/marketplace.py | 1,140줄 | ~300줄 (핸들러만) | -74% |

### 8.2 유지보수 개선

- **버그 수정**: mt_paas 한 곳만 수정하면 모든 서비스에 적용
- **기능 추가**: 새 API 추가 시 모든 서비스 자동 지원
- **테스트**: 공통 테스트 SDK로 일관된 품질 보장

### 8.3 확장성

```
새 서비스 추가 시:
1. StandardAPIHandler 상속
2. 10개 메서드 구현
3. 라우터 등록
→ Service Market 자동 연동 완료
```

---

## 9. 다음 단계

1. **mt_paas v0.2.0 개발** - 확장 API 구현
2. **테스트 SDK 업데이트** - 새 테스트 항목 추가
3. **llm_chatbot 적용** - 먼저 적용 (구조 단순)
4. **advisor 적용** - 이후 적용
5. **Service Market 업데이트** - 표준 API 호출로 변경
6. **문서화 및 공개** - 오픈소스 준비 완료

---

## 10. 참고

- [OPENSOURCE_READINESS_CHECK.md](./OPENSOURCE_READINESS_CHECK.md) - 오픈소스 준비 상태
- [AI_SERVICE_QUICKSTART.md](./AI_SERVICE_QUICKSTART.md) - 빠른 시작 가이드
- Service Market API: `/data/aiedu-workspace/service_market/backend/app/api/v1/`
