# 서비스 마켓 연동 매뉴얼

서비스 회사가 자사의 멀티 테넌트 서비스를 서비스 마켓에 연동하기 위한 가이드입니다.

---

## 목차

1. [개요](#1-개요)
2. [아키텍처](#2-아키텍처)
3. [웹훅 스펙](#3-웹훅-스펙)
4. [웹훅 엔드포인트 구현](#4-웹훅-엔드포인트-구현)
5. [테넌트 어드민 API 구현](#5-테넌트-어드민-api-구현) ← **신규**
6. [시뮬레이터로 테스트](#6-시뮬레이터로-테스트)
7. [실제 서비스 마켓 연동](#7-실제-서비스-마켓-연동)
8. [체크리스트](#8-체크리스트)
9. [FAQ](#9-faq)

---

## 1. 개요

### 서비스 마켓이란?
대학교 등 기관에서 AI 서비스를 신청하고 사용할 수 있는 플랫폼입니다.

### 연동 흐름
```
[대학교 담당자]
     ↓ 서비스 신청 (데모/정식)
[서비스 마켓]
     ↓ 웹훅 전송 (POST)
[회사 서비스] ← 여기를 구현해야 합니다
     ↓ 테넌트 생성
[응답 반환]
     ↓
[서비스 마켓]
     ↓ 접속 URL 제공
[대학교 담당자] → 서비스 사용
```

### 회사에서 해야 할 일
1. **웹훅 엔드포인트 구현** - 서비스 마켓의 요청을 받아 테넌트 생성
2. **테넌트 어드민 API 구현** - 서비스 마켓에서 테넌트 정보 조회 가능하도록
3. **시뮬레이터로 테스트** - 실제 연동 전 테스트
4. **서비스 마켓에 등록** - 엔드포인트 URL 등록

---

## 2. 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        서비스 마켓                               │
│  (대학교에서 서비스 신청 → 웹훅 전송)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ POST /api/tenant/webhook/application-approved
                              │ Header: X-API-Key
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      회사 서비스 (구현 필요)                      │
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │  웹훅 엔드포인트  │───▶│   테넌트 관리     │                   │
│  │  (API 수신)       │    │   (생성/조회)     │                   │
│  └──────────────────┘    └──────────────────┘                   │
│           │                       │                              │
│           │                       ▼                              │
│           │              ┌──────────────────┐                   │
│           │              │    데이터베이스    │                   │
│           │              │  (테넌트 정보)    │                   │
│           │              └──────────────────┘                   │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │   응답 반환       │                                           │
│  │ (tenant_id, url) │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 웹훅 스펙

### 3.1 요청 (서비스 마켓 → 회사 서비스)

**HTTP 요청**
```http
POST /api/tenant/webhook/application-approved
Host: your-service.com
Content-Type: application/json
X-API-Key: {서비스마켓에서_발급받은_API키}
```

**요청 본문 (JSON)**
```json
{
    "application": {
        "id": 17,
        "kind": "demo",
        "contact": "02-880-1234",
        "reason": "AI 튜터 서비스 데모 체험 신청합니다."
    },
    "applicant": {
        "id": 27,
        "name": "김서울",
        "email": "seoul@university.ac.kr",
        "university_name": "서울대학교"
    },
    "service": {
        "id": 18,
        "slug": "keli-tutor",
        "title": "KELI Tutor"
    }
}
```

**필드 설명**

| 필드 | 타입 | 설명 |
|------|------|------|
| `application.id` | int | 신청 고유 ID |
| `application.kind` | string | `"demo"` (30일 체험) 또는 `"service"` (정식) |
| `application.contact` | string | 연락처 |
| `application.reason` | string | 신청 사유 |
| `applicant.id` | int | 신청자 ID |
| `applicant.name` | string | 신청자 이름 |
| `applicant.email` | string | 신청자 이메일 (테넌트 식별에 사용) |
| `applicant.university_name` | string | 대학명 |
| `service.id` | int | 서비스 ID |
| `service.slug` | string | 서비스 슬러그 |
| `service.title` | string | 서비스 제목 |

### 3.2 응답 (회사 서비스 → 서비스 마켓)

**성공 응답 (HTTP 200)**
```json
{
    "success": true,
    "tenant_id": "seoul_university_17",
    "message": "테넌트 '서울대학교' 생성 완료",
    "access_url": "http://your-service.com?tenant=seoul_university_17",
    "admin_credentials": {
        "email": "seoul@university.ac.kr",
        "note": "LMS 계정으로 로그인하세요."
    },
    "created_at": "2026-01-04T21:38:22"
}
```

**필드 설명**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `success` | boolean | O | 성공 여부 (`true` / `false`) |
| `tenant_id` | string | O | 생성된 테넌트 ID |
| `message` | string | O | 결과 메시지 |
| `access_url` | string | O | 서비스 접속 URL |
| `admin_credentials` | object | X | 관리자 로그인 정보 |
| `created_at` | string | X | 생성 일시 (ISO 8601) |

**실패 응답**

```json
{
    "detail": "테넌트 생성 실패: {error_message}"
}
```

---

## 4. 웹훅 엔드포인트 구현

### 4.1 Python (FastAPI) 예제

```python
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import re

app = FastAPI()

# 테넌트 저장소 (실제로는 DB 사용)
tenants = {}

# API 키 (환경변수에서 로드)
MT_PAAS_API_KEY = "mt_dev_key_12345"  # 서비스 마켓에서 발급받은 키


class WebhookResponse(BaseModel):
    success: bool
    tenant_id: str
    message: str
    access_url: Optional[str] = None
    admin_credentials: Optional[dict] = None
    created_at: str


@app.post("/api/tenant/webhook/application-approved")
async def handle_webhook(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """
    서비스 마켓 웹훅 처리 엔드포인트
    """
    # 1. API 키 검증
    if x_api_key != MT_PAAS_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # 2. 요청 본문 파싱
    body = await request.json()
    application = body.get("application", {})
    applicant = body.get("applicant", {})
    service = body.get("service", {})

    # 3. 데이터 추출
    application_id = application.get("id")
    kind = application.get("kind", "demo")
    email = applicant.get("email")
    university = applicant.get("university_name", "unknown")

    # 4. 테넌트 ID 생성 (대학명 기반)
    tenant_id = re.sub(r'[^a-zA-Z0-9]', '_', university.lower())[:30]
    tenant_id = f"{tenant_id}_{application_id}"

    # 5. 동일 이메일 테넌트 확인 (재사용)
    existing_tenant = None
    for tid, tenant in tenants.items():
        if tenant["email"] == email:
            existing_tenant = tid
            break

    if existing_tenant:
        tenant_id = existing_tenant
        message = f"기존 테넌트 '{university}' 재사용"
    else:
        tenants[tenant_id] = {
            "email": email,
            "university": university,
            "created_at": datetime.now().isoformat()
        }
        message = f"테넌트 '{university}' 생성 완료"

    # 6. 응답 반환 (실제 service_market 스펙)
    return {
        "success": True,
        "tenant_id": tenant_id,
        "message": message,
        "access_url": f"http://your-service.com?tenant={tenant_id}",
        "admin_credentials": {
            "email": email,
            "note": "LMS 계정으로 로그인하세요."
        },
        "created_at": datetime.now().isoformat()
    }


@app.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy"}
```

### 4.2 Node.js (Express) 예제

```javascript
const express = require('express');
const app = express();
app.use(express.json());

const tenants = {};
const MT_PAAS_API_KEY = 'mt_dev_key_12345';

app.post('/api/tenant/webhook/application-approved', (req, res) => {
    // 1. API 키 검증
    const apiKey = req.headers['x-api-key'];
    if (apiKey !== MT_PAAS_API_KEY) {
        return res.status(401).json({ detail: 'Invalid API Key' });
    }

    // 2. 요청 데이터 추출 (실제 service_market 스펙)
    const { application, applicant, service } = req.body;
    const { id: applicationId, kind } = application;
    const { email, university_name: university } = applicant;

    // 3. 테넌트 ID 생성
    let tenantId = university.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 30);
    tenantId = `${tenantId}_${applicationId}`;

    // 4. 동일 이메일 테넌트 확인
    const existingTenant = Object.keys(tenants).find(
        tid => tenants[tid].email === email
    );

    let message;
    if (existingTenant) {
        tenantId = existingTenant;
        message = `기존 테넌트 '${university}' 재사용`;
    } else {
        tenants[tenantId] = {
            email,
            university,
            createdAt: new Date().toISOString()
        };
        message = `테넌트 '${university}' 생성 완료`;
    }

    // 5. 응답 반환 (실제 service_market 스펙)
    res.json({
        success: true,
        tenant_id: tenantId,
        message,
        access_url: `http://your-service.com?tenant=${tenantId}`,
        admin_credentials: {
            email,
            note: 'LMS 계정으로 로그인하세요.'
        },
        created_at: new Date().toISOString()
    });
});

app.get('/health', (req, res) => {
    res.json({ status: 'healthy' });
});

app.listen(8000, () => {
    console.log('Server running on port 8000');
});
```

### 4.3 핵심 구현 포인트

| 항목 | 설명 | 중요도 |
|------|------|--------|
| **API 키 검증** | X-API-Key 헤더 검증 | 필수 |
| **테넌트 재사용** | 동일 이메일은 기존 테넌트 반환 | 권장 |
| **에러 처리** | 적절한 HTTP 상태 코드 반환 | 필수 |
| **응답 형식** | success, tenant_id, access_url, message 포함 | 필수 |

---

## 5. 테넌트 어드민 API 구현

서비스 마켓에서 회사 서비스의 테넌트 정보를 조회할 수 있도록 API를 구현해야 합니다.
테넌트 어드민(기관 관리자)이 대시보드에서 볼 수 있는 모든 정보를 서비스 마켓에서도 조회할 수 있어야 합니다.

### 5.1 테넌트 어드민 대시보드 기능 (참고: advisor 프로젝트)

테넌트 어드민 대시보드는 3개 탭으로 구성됩니다:

| 탭 | 기능 |
|----|------|
| **대시보드 개요** | DAU/WAU/MAU, 비용, 사용 추이 차트 |
| **사용자 관리** | 사용자 등록/정지/삭제, 관리자 관리 |
| **데이터 관리** | 문서/동영상/크롤링 사이트 관리 |

### 5.2 필수 구현 API

#### 기본 조회 API

| API | Method | 설명 |
|-----|--------|------|
| `/api/tenant/list` | GET | 전체 테넌트 목록 조회 |
| `/api/tenant/status/{tenant_id}` | GET | 테넌트 상세 정보 조회 |

#### 대시보드 API

| API | Method | 설명 |
|-----|--------|------|
| `/api/admin/dashboard` | GET | 메인 대시보드 (사용자/메시지/토큰 통계) |
| `/api/admin/dashboard/usage-patterns` | GET | 사용 패턴 분석 (시간대/요일별) |
| `/api/admin/dashboard/costs` | GET | 비용 분석 (모델별/사용자별) |
| `/api/admin/dashboard/top-users` | GET | 상위 활성 사용자 |

#### 사용자 관리 API

| API | Method | 설명 |
|-----|--------|------|
| `/api/admin/users` | GET | 사용자 목록 (페이징, 검색) |
| `/api/admin/users` | POST | 사용자 생성 |
| `/api/admin/users/bulk` | POST | 사용자 일괄 등록 |
| `/api/admin/users/{user_id}` | GET | 사용자 상세 |
| `/api/admin/users/{user_id}` | PUT | 사용자 수정 |
| `/api/admin/users/{user_id}` | DELETE | 사용자 삭제 |
| `/api/admin/users/{user_id}/suspend` | POST | 사용자 정지 |
| `/api/admin/users/{user_id}/activate` | POST | 사용자 활성화 |

#### 관리자 관리 API

| API | Method | 설명 |
|-----|--------|------|
| `/api/admin/admins` | GET | 관리자 목록 |
| `/api/admin/admins` | POST | 관리자 등록 |
| `/api/admin/admins/{user_id}` | DELETE | 관리자 삭제 |

#### 데이터 관리 API

| API | Method | 설명 |
|-----|--------|------|
| `/api/admin/data/stats` | GET | 데이터 저장소 통계 |
| `/api/admin/data/documents` | GET | 문서 목록 |
| `/api/admin/data/documents/upload` | POST | 문서 업로드 |
| `/api/admin/data/documents/{docId}` | DELETE | 문서 삭제 |

### 5.3 API 스펙 상세

#### 5.3.1 테넌트 목록 조회

**요청**
```http
GET /api/tenant/list
X-API-Key: {API_KEY}
```

**응답**
```json
{
    "tenants": [
        {
            "tenant_id": "demo_1000",
            "university_name": "서울대학교",
            "email": "admin@seoul.ac.kr",
            "status": "active",
            "created_at": "2026-02-01T10:00:00",
            "users_count": 150
        }
    ],
    "total": 1
}
```

#### 5.3.2 메인 대시보드 (GET /api/admin/dashboard)

서비스 마켓에서 가장 중요한 API입니다. 테넌트의 전체 현황을 조회합니다.

**요청**
```http
GET /api/admin/dashboard
Authorization: Bearer {TOKEN}
X-Tenant-ID: {tenant_id}
```

**응답**
```json
{
    "users": {
        "total": 150,
        "active": 145,
        "new_this_week": 10,
        "active_7days": 120,
        "active_30days": 140,
        "admins": 3
    },
    "usage": {
        "total_sessions": 5000,
        "sessions_today": 150,
        "total_messages": 25000,
        "messages_today": 800,
        "total_tokens": 5000000,
        "tokens_today": 150000
    },
    "daily_trend": [
        {"date": "2026-02-01", "messages": 800, "users": 120, "tokens": 150000}
    ],
    "monthly_user_trend": [
        {"month": "2026-01", "users": 100, "messages": 20000, "tokens": 4000000},
        {"month": "2026-02", "users": 150, "messages": 25000, "tokens": 5000000}
    ],
    "model_usage": [
        {"model": "gpt-4", "count": 5000, "tokens": 2000000},
        {"model": "gpt-3.5-turbo", "count": 20000, "tokens": 3000000}
    ]
}
```

#### 5.3.3 비용 분석 (GET /api/admin/dashboard/costs)

**요청**
```http
GET /api/admin/dashboard/costs?days=30
Authorization: Bearer {TOKEN}
X-Tenant-ID: {tenant_id}
```

**응답**
```json
{
    "total_tokens": 5000000,
    "estimated_cost_usd": 125.50,
    "by_model": [
        {"model": "gpt-4", "tokens": 2000000, "cost_usd": 100.00},
        {"model": "gpt-3.5-turbo", "tokens": 3000000, "cost_usd": 25.50}
    ],
    "by_user": [
        {"username": "user1", "tokens": 500000, "cost_usd": 12.50},
        {"username": "user2", "tokens": 400000, "cost_usd": 10.00}
    ],
    "monthly_costs": [
        {"month": "2026-01", "cost_usd": 100.00},
        {"month": "2026-02", "cost_usd": 125.50}
    ]
}
```

#### 5.3.4 사용 패턴 (GET /api/admin/dashboard/usage-patterns)

**요청**
```http
GET /api/admin/dashboard/usage-patterns?days=30
Authorization: Bearer {TOKEN}
X-Tenant-ID: {tenant_id}
```

**응답**
```json
{
    "hourly_distribution": [
        {"hour": 9, "count": 500},
        {"hour": 10, "count": 800},
        {"hour": 14, "count": 1200}
    ],
    "weekday_distribution": [
        {"day": "Monday", "count": 3000},
        {"day": "Tuesday", "count": 3500},
        {"day": "Wednesday", "count": 4000}
    ],
    "avg_session_length": 15.5
}
```

#### 5.3.5 사용자 목록 (GET /api/admin/users)

**요청**
```http
GET /api/admin/users?page=1&limit=20&search=홍길동
Authorization: Bearer {TOKEN}
X-Tenant-ID: {tenant_id}
```

**응답**
```json
{
    "users": [
        {
            "id": 1,
            "username": "user001",
            "display_name": "홍길동",
            "email": "user1@seoul.ac.kr",
            "is_active": true,
            "created_at": "2026-01-15T10:00:00",
            "last_login": "2026-02-01T20:00:00",
            "monthly_cost_usd": 12.50
        }
    ],
    "total": 1,
    "page": 1,
    "limit": 20
}
```

### 5.4 Python 구현 예제 (전체)

```python
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

app = FastAPI()

# ============================================================================
# 데이터 저장소 (실제로는 DB 사용)
# ============================================================================
tenants = {}  # tenant_id -> tenant_info
users_db = {}  # tenant_id -> [users]
sessions_db = {}  # tenant_id -> [sessions]
messages_db = {}  # tenant_id -> [messages]

# ============================================================================
# 인증
# ============================================================================
def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != "your_api_key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

def verify_tenant_admin(
    authorization: str = Header(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    # Bearer 토큰 검증 로직
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    return x_tenant_id

# ============================================================================
# 테넌트 기본 조회 API
# ============================================================================
@app.get("/api/tenant/list")
async def list_tenants(api_key: str = Depends(verify_api_key)):
    """테넌트 목록 조회"""
    tenant_list = []
    for tid, data in tenants.items():
        tenant_list.append({
            "tenant_id": tid,
            "university_name": data.get("university"),
            "email": data.get("email"),
            "status": "active",
            "created_at": data.get("created_at"),
            "users_count": len(users_db.get(tid, []))
        })
    return {"tenants": tenant_list, "total": len(tenant_list)}

@app.get("/api/tenant/status/{tenant_id}")
async def get_tenant_status(tenant_id: str, api_key: str = Depends(verify_api_key)):
    """테넌트 상세 조회"""
    if tenant_id not in tenants:
        raise HTTPException(status_code=404, detail="Tenant not found")

    data = tenants[tenant_id]
    users = users_db.get(tenant_id, [])
    return {
        "tenant_id": tenant_id,
        "university_name": data.get("university"),
        "email": data.get("email"),
        "status": "active",
        "created_at": data.get("created_at"),
        "users_count": len(users),
        "active_users": len([u for u in users if u.get("is_active")])
    }

# ============================================================================
# 대시보드 API (테넌트 어드민용)
# ============================================================================
@app.get("/api/admin/dashboard")
async def get_dashboard(tenant_id: str = Depends(verify_tenant_admin)):
    """메인 대시보드 - DAU/WAU/MAU, 사용량, 추이"""
    users = users_db.get(tenant_id, [])
    sessions = sessions_db.get(tenant_id, [])
    messages = messages_db.get(tenant_id, [])

    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    return {
        "users": {
            "total": len(users),
            "active": len([u for u in users if u.get("is_active")]),
            "new_this_week": len([u for u in users if u.get("created_at", "")[:10] >= str(week_ago)]),
            "active_7days": 0,  # 실제 계산 필요
            "active_30days": 0,  # 실제 계산 필요
            "admins": len([u for u in users if u.get("role") == "admin"])
        },
        "usage": {
            "total_sessions": len(sessions),
            "sessions_today": 0,
            "total_messages": len(messages),
            "messages_today": 0,
            "total_tokens": sum(m.get("tokens", 0) for m in messages),
            "tokens_today": 0
        },
        "daily_trend": [],  # 실제 집계 필요
        "monthly_user_trend": [],  # 실제 집계 필요
        "model_usage": []  # 실제 집계 필요
    }

@app.get("/api/admin/dashboard/costs")
async def get_costs(
    days: int = Query(30),
    tenant_id: str = Depends(verify_tenant_admin)
):
    """비용 분석"""
    messages = messages_db.get(tenant_id, [])
    total_tokens = sum(m.get("tokens", 0) for m in messages)

    # 비용 계산 (예시: $0.002 per 1K tokens)
    estimated_cost = (total_tokens / 1000) * 0.002

    return {
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost, 2),
        "by_model": [],
        "by_user": [],
        "monthly_costs": []
    }

@app.get("/api/admin/dashboard/usage-patterns")
async def get_usage_patterns(
    days: int = Query(30),
    tenant_id: str = Depends(verify_tenant_admin)
):
    """사용 패턴 분석"""
    return {
        "hourly_distribution": [],
        "weekday_distribution": [],
        "avg_session_length": 0
    }

@app.get("/api/admin/dashboard/top-users")
async def get_top_users(
    days: int = Query(30),
    limit: int = Query(20),
    tenant_id: str = Depends(verify_tenant_admin)
):
    """상위 활성 사용자"""
    return {"period_days": days, "users": []}

# ============================================================================
# 사용자 관리 API
# ============================================================================
@app.get("/api/admin/users")
async def list_users(
    page: int = Query(1),
    limit: int = Query(20),
    search: Optional[str] = Query(None),
    tenant_id: str = Depends(verify_tenant_admin)
):
    """사용자 목록 조회"""
    users = users_db.get(tenant_id, [])

    if search:
        users = [u for u in users if search.lower() in u.get("username", "").lower()
                 or search.lower() in u.get("display_name", "").lower()]

    start = (page - 1) * limit
    end = start + limit

    return {
        "users": users[start:end],
        "total": len(users),
        "page": page,
        "limit": limit
    }

class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    email: Optional[str] = None

@app.post("/api/admin/users")
async def create_user(user: UserCreate, tenant_id: str = Depends(verify_tenant_admin)):
    """사용자 생성"""
    if tenant_id not in users_db:
        users_db[tenant_id] = []

    new_user = {
        "id": len(users_db[tenant_id]) + 1,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "email": user.email,
        "is_active": True,
        "role": "user",
        "created_at": datetime.now().isoformat()
    }
    users_db[tenant_id].append(new_user)
    return new_user

@app.post("/api/admin/users/bulk")
async def create_users_bulk(users: List[UserCreate], tenant_id: str = Depends(verify_tenant_admin)):
    """사용자 일괄 등록"""
    created = []
    for user in users:
        result = await create_user(user, tenant_id)
        created.append(result)
    return {"created": len(created), "users": created}

@app.post("/api/admin/users/{user_id}/suspend")
async def suspend_user(user_id: int, tenant_id: str = Depends(verify_tenant_admin)):
    """사용자 정지"""
    users = users_db.get(tenant_id, [])
    for user in users:
        if user["id"] == user_id:
            user["is_active"] = False
            return {"message": "User suspended", "user_id": user_id}
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/api/admin/users/{user_id}/activate")
async def activate_user(user_id: int, tenant_id: str = Depends(verify_tenant_admin)):
    """사용자 활성화"""
    users = users_db.get(tenant_id, [])
    for user in users:
        if user["id"] == user_id:
            user["is_active"] = True
            return {"message": "User activated", "user_id": user_id}
    raise HTTPException(status_code=404, detail="User not found")

@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: int, tenant_id: str = Depends(verify_tenant_admin)):
    """사용자 삭제"""
    users = users_db.get(tenant_id, [])
    for i, user in enumerate(users):
        if user["id"] == user_id:
            users.pop(i)
            return {"message": "User deleted", "user_id": user_id}
    raise HTTPException(status_code=404, detail="User not found")

# ============================================================================
# 관리자 관리 API
# ============================================================================
@app.get("/api/admin/admins")
async def list_admins(tenant_id: str = Depends(verify_tenant_admin)):
    """관리자 목록"""
    users = users_db.get(tenant_id, [])
    admins = [u for u in users if u.get("role") == "admin"]
    return {"admins": admins, "total": len(admins)}

@app.post("/api/admin/admins")
async def create_admin(user: UserCreate, tenant_id: str = Depends(verify_tenant_admin)):
    """관리자 등록"""
    result = await create_user(user, tenant_id)
    # 관리자 권한 부여
    for u in users_db[tenant_id]:
        if u["id"] == result["id"]:
            u["role"] = "admin"
            break
    result["role"] = "admin"
    return result

# ============================================================================
# 데이터 관리 API
# ============================================================================
@app.get("/api/admin/data/stats")
async def get_data_stats(tenant_id: str = Depends(verify_tenant_admin)):
    """데이터 저장소 통계"""
    return {
        "documents": {"total": 0, "indexed": 0},
        "videos": {"total": 0, "transcribed": 0},
        "crawl_sites": {"total": 0, "active": 0},
        "storage_used_mb": 0
    }
```

### 5.5 시뮬레이터에서 테넌트 어드민 API 테스트

서비스 마켓 시뮬레이터에서 테넌트 어드민 API를 테스트할 수 있습니다.

**URL**: http://220.66.157.70:8590/docs

| 시뮬레이터 API | 회사 서비스 호출 | 설명 |
|---------------|-----------------|------|
| POST /admin/tenants | GET /api/tenant/list | 테넌트 목록 조회 |
| POST /admin/tenants/{tenant_id} | GET /api/tenant/status/{id} | 테넌트 상세 조회 |
| POST /admin/tenants/{tenant_id}/users | GET /api/tenant/{id}/users | 사용자 목록 조회 |
| POST /admin/tenants/{tenant_id}/stats | GET /api/tenant/{id}/stats | 통계 조회 |

**테스트 방법**:
1. **POST /admin/tenants** 클릭
2. **Try it out** 클릭
3. 아래 내용 입력:
```json
{
    "target_base_url": "http://회사서비스주소",
    "api_key": "mt_dev_key_12345"
}
```
4. **Execute** 클릭

---

## 6. 시뮬레이터로 웹훅 테스트

### 6.1 시뮬레이터 접속

**URL**: http://220.66.157.70:8590/docs

### 6.2 테스트 순서

#### Step 1: 데모 신청 생성

1. **POST /applications/demo** 클릭
2. **Try it out** 클릭
3. 아래 내용 입력:
```json
{
  "applicant_email": "test@university.ac.kr",
  "applicant_name": "테스트 사용자",
  "university_name": "테스트 대학교",
  "service_slug": "your-service",
  "service_title": "Your Service"
}
```
4. **Execute** 클릭
5. 응답에서 `id` 확인 (예: 1)

#### Step 2: 웹훅 전송

1. **POST /applications/{id}/send** 클릭
2. **Try it out** 클릭
3. 파라미터 입력:
   - `id`: Step 1에서 받은 ID (예: 1)
   - `target_url`: `http://회사서비스주소/api/tenant/webhook/application-approved`
   - `api_key`: `mt_dev_key_12345` (테스트용)
4. **Execute** 클릭

#### Step 3: 결과 확인

1. **GET /results** 에서 웹훅 결과 확인
2. **GET /stats** 에서 통계 확인

### 6.3 CLI로 테스트

```bash
# 데모 신청 + 웹훅 전송 (한 번에)
python -m sandbox.simulator.cli demo \
    --target http://회사서비스주소/api/tenant/webhook/application-approved \
    --email test@university.ac.kr \
    --university "테스트 대학교"

# 결과 확인
python -m sandbox.simulator.cli results

# 통계 확인
python -m sandbox.simulator.cli stats
```

### 6.4 curl로 테스트

```bash
# 직접 웹훅 호출 테스트 (실제 service_market 스펙)
curl -X POST http://회사서비스주소/api/tenant/webhook/application-approved \
  -H "Content-Type: application/json" \
  -H "X-API-Key: mt_dev_key_12345" \
  -d '{
    "application": {
      "id": 9999,
      "kind": "demo",
      "contact": "02-1234-5678",
      "reason": "테스트 신청"
    },
    "applicant": {
      "id": 1,
      "name": "테스트",
      "email": "test@test.ac.kr",
      "university_name": "테스트대학교"
    },
    "service": {
      "id": 1,
      "slug": "test-service",
      "title": "Test Service"
    }
  }'
```

---

## 7. 실제 서비스 마켓 연동

### 7.1 서비스 마켓 등록 정보

서비스 마켓에 등록할 때 다음 정보를 제공해야 합니다:

| 항목 | 예시 | 설명 |
|------|------|------|
| 서비스명 | AI 튜터 | 서비스 이름 |
| 웹훅 URL | `https://your-service.com/api/tenant/webhook/application-approved` | 웹훅 수신 엔드포인트 |
| API 키 | `your_secret_key` | 웹훅 인증용 API 키 |
| 서비스 URL | `https://your-service.com` | 서비스 메인 URL |

### 7.2 HTTPS 필수

실제 서비스 마켓 연동 시 **HTTPS**가 필수입니다.

```
# 테스트 (HTTP 허용)
http://your-service.com/api/tenant/webhook/application-approved

# 운영 (HTTPS 필수)
https://your-service.com/api/tenant/webhook/application-approved
```

### 7.3 API 키 관리

1. 서비스 마켓에서 API 키 발급
2. 회사 서비스에 환경변수로 설정
3. 웹훅 요청 시 검증

```python
# .env 파일
SERVICE_MARKET_API_KEY=your_secret_key_from_market

# Python 코드
import os
VALID_API_KEY = os.getenv("SERVICE_MARKET_API_KEY")
```

---

## 8. 체크리스트

### 8.1 웹훅 구현 체크리스트

- [ ] 웹훅 엔드포인트 구현 (`POST /api/tenant/webhook/application-approved`)
- [ ] API 키 검증 로직 구현
- [ ] 테넌트 생성 로직 구현
- [ ] 동일 이메일 테넌트 재사용 로직 구현
- [ ] 올바른 응답 형식 반환 (success, tenant_id, access_url, message)
- [ ] 에러 처리 구현

### 8.2 테넌트 어드민 API 구현 체크리스트

- [ ] 테넌트 목록 조회 API (`GET /api/tenant/list`)
- [ ] 테넌트 상세 조회 API (`GET /api/tenant/status/{tenant_id}`)
- [ ] 대시보드 API (`GET /api/admin/dashboard`)
- [ ] 비용 분석 API (`GET /api/admin/dashboard/costs`)
- [ ] 사용 패턴 API (`GET /api/admin/dashboard/usage-patterns`)
- [ ] 사용자 목록 API (`GET /api/admin/users`)
- [ ] 사용자 생성/수정/삭제 API
- [ ] 사용자 정지/활성화 API
- [ ] 관리자 목록/생성 API
- [ ] 데이터 통계 API (`GET /api/admin/data/stats`)

### 8.3 테스트 체크리스트

- [ ] 시뮬레이터로 데모 신청 테스트
- [ ] 시뮬레이터로 서비스 신청 테스트
- [ ] 잘못된 API 키로 401 응답 확인
- [ ] 동일 이메일 재신청 시 기존 테넌트 반환 확인
- [ ] tenant_url로 실제 서비스 접속 확인
- [ ] 테넌트 어드민 API 조회 테스트 (시뮬레이터 /admin/tenants)
- [ ] 대시보드 데이터 정상 반환 확인

### 8.4 운영 체크리스트

- [ ] HTTPS 적용
- [ ] API 키 환경변수 설정
- [ ] 로깅 구현
- [ ] 모니터링 설정
- [ ] 서비스 마켓에 정보 등록

---

## 9. FAQ

### Q1. 동일 대학에서 여러 번 신청하면?

**A**: 동일 이메일(applicant.email)로 신청하면 기존 테넌트를 재사용해야 합니다. 새 테넌트를 생성하지 않고 기존 tenant_id와 tenant_url을 반환합니다.

### Q2. 데모와 서비스 신청의 차이는?

**A**:
- `kind: "demo"` - 30일 체험판
- `kind: "service"` - 정식 서비스 (기간은 start_date ~ end_date)

### Q3. 비동기로 테넌트를 생성해야 하면?

**A**: `success: false`와 함께 처리 중 메시지를 반환하고, 생성 완료 후 콜백 URL로 결과를 전송합니다.

```json
// 즉시 응답
{
    "success": false,
    "tenant_id": null,
    "message": "테넌트 생성 중...",
    "access_url": null
}

// 나중에 콜백으로 전송
POST {callback_url}
{
    "success": true,
    "tenant_id": "demo_1000",
    "message": "테넌트 생성 완료",
    "access_url": "http://...",
    "created_at": "..."
}
```

### Q4. 에러가 발생하면?

**A**: 적절한 HTTP 상태 코드와 함께 에러 응답을 반환합니다.

```json
// HTTP 400 Bad Request
{
    "detail": "잘못된 요청 형식"
}

// HTTP 500 Internal Server Error
{
    "detail": "테넌트 생성 실패: {error_message}"
}
```

### Q5. 테스트 환경과 운영 환경의 차이는?

**A**:

| 항목 | 테스트 | 운영 |
|------|--------|------|
| 시뮬레이터 URL | http://220.66.157.70:8590 | - |
| 서비스 마켓 URL | - | https://market.k-university.ai |
| API 키 | `mt_dev_key_12345` | 서비스 마켓에서 발급 |
| 프로토콜 | HTTP 허용 | HTTPS 필수 |

---

## 문의

- 기술 문의: tech@example.com
- 서비스 마켓: https://market.k-university.ai
