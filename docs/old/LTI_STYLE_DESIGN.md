# Multi-Tenant PaaS - LTI 스타일 최종 설계

> Service Market과 서비스 업체 간의 간소화된 표준 인터페이스

**작성일**: 2026-01-03
**버전**: 3.1
**핵심 원칙**: 대학별 격리된 데이터 + 서비스별 분석 + 마켓의 전체 접근

---

## 1. 역할 분담 (최종)

### 1.1 핵심 원칙

```
┌─────────────────────────────────────────────────────────────────────┐
│                         역할 분리 원칙                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Service Market: 중앙 관리 + 전체 데이터 접근                        │
│   ├─ 테넌트 라이프사이클 (생성/활성화/비활성화)                      │
│   ├─ 모든 서비스/대학의 데이터 조회 (사용량, LRS, 분석)              │
│   └─ 통합 대시보드 및 분석                                           │
│                                                                      │
│   서비스 업체: 인프라 및 인증 완전 자율                              │
│   ├─ 대학별 격리된 DB, LRS, VectorDB 운영                           │
│   ├─ 대학별 분석 서비스 제공                                         │
│   └─ 마켓에 전체 데이터 API 제공                                     │
│                                                                      │
│   대학교: 자체 로그인 체계 + 격리된 데이터                            │
│   ├─ 테넌트별 링크로 서비스 접근                                     │
│   ├─ 대학 자체 SSO/로그인 시스템 사용                                │
│   └─ 자기 대학 데이터만 접근 (분석 서비스 이용)                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 상세 역할 분담표

| 항목 | Service Market | 서비스 업체 | 대학교 |
|------|---------------|------------|--------|
| **테넌트 생성** | ✅ 생성 요청 | API 응답 | - |
| **테넌트 활성화/비활성화** | ✅ 상태 제어 | API 응답 | - |
| **인프라 (DB, LRS 등)** | ❌ 직접 운영 안함 | ✅ 대학별 격리 운영 | - |
| **인증/로그인** | ❌ 관여 안함 | ✅ 직접 구현 | ✅ 자체 시스템 |
| **데이터 접근 (자기 대학)** | - | API 제공 | ✅ 분석 서비스 이용 |
| **데이터 접근 (전체)** | ✅ 모든 데이터 | API 제공 | ❌ |
| **분석 서비스** | ✅ 통합 분석 | ✅ 대학별 분석 | 조회만 |
| **접속 링크 제공** | ✅ 링크 안내 | 테넌트별 URL | 링크로 접속 |
| **요금 관리** | ✅ 구독/과금 | - | 결제 |

---

## 2. 아키텍처 개요

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Service Market                                  │
│                                                                          │
│   역할:                                                                  │
│   • 서비스 등록 및 검증 (manifest.yaml)                                  │
│   • 테넌트 라이프사이클 관리 (activate/deactivate)                       │
│   • 모든 서비스/대학의 데이터 접근 (통합 분석)                           │
│   • 접속 링크 제공                                                       │
│                                                                          │
│   ┌────────────────────────────────────────────────────────┐            │
│   │              통합 대시보드 / 분석                        │            │
│   │   • 전체 서비스 사용량 현황                              │            │
│   │   • 전체 대학 학습 활동 분석 (LRS 통합)                  │            │
│   │   • 서비스별/대학별 비교 분석                            │            │
│   └────────────────────────────────────────────────────────┘            │
└─────────────────┬──────────────────────┬────────────────────────────────┘
                  │                      │
                  │ 표준 API             │ 표준 API
                  │ (전체 데이터 접근)   │ (전체 데이터 접근)
                  ▼                      ▼
┌─────────────────────────────────────┐  ┌─────────────────────────────────┐
│          keli_tutor                 │  │         llm_chatbot             │
│                                     │  │                                 │
│  ┌────────────────────────────┐    │  │  ┌────────────────────────┐    │
│  │ 대학별 격리 인프라          │    │  │  │ 대학별 격리 인프라      │    │
│  │                            │    │  │  │                        │    │
│  │  한림대: DB_A, LRS_A       │    │  │  │  한림대: DB_A, LRS_A   │    │
│  │  고려대: DB_B, LRS_B       │    │  │  │  고려대: DB_B, LRS_B   │    │
│  │  서울대: DB_C, LRS_C       │    │  │  │  서울대: DB_C, LRS_C   │    │
│  └────────────────────────────┘    │  │  └────────────────────────┘    │
│                                     │  │                                 │
│  ┌────────────────────────────┐    │  │  ┌────────────────────────┐    │
│  │ 분석 서비스                 │    │  │  │ 분석 서비스             │    │
│  │ • 대학별 학습 현황          │    │  │  │ • 대학별 사용 현황      │    │
│  │ • 대학별 성과 리포트        │    │  │  │ • 대학별 대화 분석      │    │
│  └────────────────────────────┘    │  │  └────────────────────────┘    │
│                                     │  │                                 │
│  테넌트별 URL:                      │  │  테넌트별 URL:                  │
│  /hallym, /korea, /snu              │  │  /hallym, /korea, /snu          │
└───────────┬───────────┬─────────────┘  └───────────┬───────────┬────────┘
            │           │                            │           │
            ▼           ▼                            ▼           ▼
┌─────────────────┐ ┌─────────────────┐  ┌─────────────────┐ ┌──────────┐
│   한림대학교     │ │   고려대학교     │  │   서울대학교     │ │  ...     │
│                 │ │                 │  │                 │ │          │
│ • 자체 로그인   │ │ • 자체 로그인   │  │ • 자체 로그인   │ │          │
│ • 자기 데이터만 │ │ • 자기 데이터만 │  │ • 자기 데이터만 │ │          │
│   접근 가능     │ │   접근 가능     │ │   접근 가능     │ │          │
└─────────────────┘ └─────────────────┘  └─────────────────┘ └──────────┘
```

### 2.2 데이터 격리 및 접근 권한

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           데이터 접근 권한                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Service Market (슈퍼 관리자)                                           │
│   └─ 모든 서비스의 모든 대학 데이터 접근 가능                            │
│      • 전체 LRS 데이터                                                   │
│      • 전체 사용량 데이터                                                │
│      • 전체 분석 데이터                                                  │
│                                                                          │
│   서비스 업체 (서비스 관리자)                                            │
│   └─ 자기 서비스의 모든 대학 데이터 접근 가능                            │
│      • 서비스 내 전체 LRS                                                │
│      • 서비스 내 전체 사용량                                             │
│                                                                          │
│   대학교 (테넌트 관리자)                                                  │
│   └─ 자기 대학 데이터만 접근 가능                                        │
│      • 해당 대학 LRS만                                                   │
│      • 해당 대학 사용량만                                                │
│      • 해당 대학 분석 리포트만                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 접속 흐름

```
대학 사용자의 서비스 접속:

┌──────────┐   ┌─────────────────┐   ┌──────────────┐   ┌──────────────┐
│  사용자   │   │   대학 포털      │   │   서비스      │   │  대학 SSO    │
└────┬─────┘   └───────┬─────────┘   └──────┬───────┘   └──────┬───────┘
     │                 │                    │                  │
     │ 1. 대학 포털 접속                    │                  │
     │────────────────▶│                    │                  │
     │                 │                    │                  │
     │ 2. AI 서비스 클릭 (링크)             │                  │
     │                 │                    │                  │
     │────────────────────────────────────▶│                  │
     │                 │                    │                  │
     │                 │                    │ 3. 인증 필요 확인│
     │                 │                    │                  │
     │                 │                    │ 4. 대학 SSO로 리다이렉트 (선택사항)
     │◀───────────────────────────────────────────────────────│
     │                 │                    │                  │
     │ 5. 대학 로그인                       │                  │
     │───────────────────────────────────────────────────────▶│
     │                 │                    │                  │
     │ 6. 인증 완료, 서비스 사용            │                  │
     │────────────────────────────────────▶│                  │
     │                 │                    │                  │

* 인증 방식은 서비스 업체와 대학이 협의하여 결정
* 마켓은 이 과정에 관여하지 않음
```

---

## 3. 표준 API 규격

### 3.1 API 목록

#### 3.1.1 기본 API (필수)

| API | 메서드 | 용도 | 필수 |
|-----|--------|------|------|
| `/mt/health` | GET | 서비스 상태 확인 | ✅ |
| `/mt/tenant/{id}/activate` | POST | 테넌트 활성화 | ✅ |
| `/mt/tenant/{id}/deactivate` | POST | 테넌트 비활성화 | ✅ |
| `/mt/tenant/{id}/status` | GET | 테넌트 상태 조회 | ✅ |
| `/mt/tenant/{id}/usage` | GET | 사용량 조회 | ✅ |

#### 3.1.2 데이터/분석 API (필수)

| API | 메서드 | 용도 | 호출자 |
|-----|--------|------|--------|
| `/mt/tenant/{id}/lrs` | GET | 테넌트 LRS 데이터 조회 | Market, 대학 |
| `/mt/tenant/{id}/analytics` | GET | 테넌트 분석 리포트 | Market, 대학 |
| `/mt/tenants/lrs` | GET | 전체 테넌트 LRS (Market 전용) | Market |
| `/mt/tenants/analytics` | GET | 전체 테넌트 분석 (Market 전용) | Market |

#### 3.1.3 비용 API (필수)

| API | 메서드 | 용도 | 호출자 |
|-----|--------|------|--------|
| `/mt/tenant/{id}/billing` | GET | 테넌트 비용 요약 조회 | Market, 대학 |
| `/mt/tenant/{id}/billing/details` | GET | 테넌트 비용 상세 내역 | Market, 대학 |
| `/mt/tenants/billing` | GET | 전체 비용 조회 (Market 전용) | Market |

#### 3.1.4 접근 권한 매트릭스

| API | Service Market | 서비스 관리자 | 대학 관리자 |
|-----|---------------|--------------|------------|
| `/mt/tenant/{id}/lrs` | ✅ 모든 테넌트 | ✅ 모든 테넌트 | ✅ 자기만 |
| `/mt/tenant/{id}/analytics` | ✅ 모든 테넌트 | ✅ 모든 테넌트 | ✅ 자기만 |
| `/mt/tenant/{id}/billing` | ✅ 모든 테넌트 | ✅ 모든 테넌트 | ✅ 자기만 |
| `/mt/tenant/{id}/billing/details` | ✅ 모든 테넌트 | ✅ 모든 테넌트 | ✅ 자기만 |
| `/mt/tenants/lrs` | ✅ | ❌ | ❌ |
| `/mt/tenants/analytics` | ✅ | ❌ | ❌ |
| `/mt/tenants/billing` | ✅ | ❌ | ❌ |

**제거된 항목:**
- ~~SSO 관련 API~~ (대학교에서 자체 처리)
- ~~인프라 프로비저닝 API~~ (서비스에서 자체 처리)

### 3.2 API 상세 규격

#### 3.2.1 헬스체크

```http
GET /mt/health

Response 200:
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-03T12:00:00Z"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| status | string | healthy, degraded, unhealthy |
| version | string | 서비스 버전 |
| timestamp | string | ISO 8601 형식 |

#### 3.2.2 테넌트 활성화

```http
POST /mt/tenant/{tenant_id}/activate
Headers:
  X-Market-API-Key: {api_key}
  Content-Type: application/json

Request:
{
  "tenant_id": "hallym_univ",
  "tenant_name": "한림대학교",
  "plan": "premium",
  "features": ["ai_chat", "rag", "quiz"],
  "config": {
    "max_users": 500
  },
  "contact": {
    "email": "admin@hallym.ac.kr",
    "name": "홍길동"
  }
}

Response 200:
{
  "success": true,
  "tenant_id": "hallym_univ",
  "access_url": "https://keli.k-university.ai/hallym",
  "message": "Tenant activated successfully"
}

Response 409:
{
  "success": false,
  "error": "TENANT_EXISTS",
  "message": "Tenant hallym_univ already exists"
}
```

**요청 필드:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| tenant_id | string | ✅ | 테넌트 고유 ID |
| tenant_name | string | ✅ | 테넌트 표시명 |
| plan | string | ✅ | 구독 요금제 |
| features | array | ✅ | 활성화할 기능 목록 |
| config | object | ❌ | 추가 설정 (서비스별 정의) |
| contact | object | ✅ | 담당자 정보 |

**응답 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| success | boolean | 성공 여부 |
| tenant_id | string | 테넌트 ID |
| access_url | string | 사용자 접속 URL |
| message | string | 결과 메시지 |

#### 3.2.3 테넌트 비활성화

```http
POST /mt/tenant/{tenant_id}/deactivate
Headers:
  X-Market-API-Key: {api_key}
  Content-Type: application/json

Request:
{
  "reason": "subscription_expired",
  "preserve_data": true
}

Response 200:
{
  "success": true,
  "tenant_id": "hallym_univ",
  "status": "deactivated",
  "data_preserved": true,
  "data_retention_until": "2026-04-03T00:00:00Z"
}
```

**요청 필드:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| reason | string | ✅ | 비활성화 사유 |
| preserve_data | boolean | ✅ | 데이터 보존 여부 |

**reason 값:**
- `subscription_expired`: 구독 만료
- `admin_request`: 관리자 요청
- `violation`: 정책 위반

#### 3.2.4 테넌트 상태 조회

```http
GET /mt/tenant/{tenant_id}/status
Headers:
  X-Market-API-Key: {api_key}

Response 200:
{
  "tenant_id": "hallym_univ",
  "status": "active",
  "plan": "premium",
  "features": ["ai_chat", "rag", "quiz"],
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-03T00:00:00Z"
}

Response 404:
{
  "success": false,
  "error": "TENANT_NOT_FOUND",
  "message": "Tenant hallym_univ not found"
}
```

**응답 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| tenant_id | string | 테넌트 ID |
| status | string | active, suspended, deactivated |
| plan | string | 현재 요금제 |
| features | array | 활성화된 기능 |
| created_at | string | 생성 시각 |
| updated_at | string | 최종 수정 시각 |

#### 3.2.5 사용량 조회

```http
GET /mt/tenant/{tenant_id}/usage?period=2026-01
Headers:
  X-Market-API-Key: {api_key}

Response 200:
{
  "tenant_id": "hallym_univ",
  "period": "2026-01",
  "usage": {
    "active_users": 150,
    "total_sessions": 3500,
    "api_calls": 15000,
    "ai_tokens": 500000,
    "storage_mb": 25600
  }
}
```

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| period | string | ✅ | 조회 기간 (YYYY-MM) |

**usage 필드 (서비스별 가변):**

| 필드 | 타입 | 설명 |
|------|------|------|
| active_users | integer | 활성 사용자 수 |
| total_sessions | integer | 총 세션 수 |
| api_calls | integer | API 호출 횟수 |
| ai_tokens | integer | AI 토큰 사용량 |
| storage_mb | integer | 스토리지 사용량 (MB) |

#### 3.2.6 LRS 데이터 조회 (테넌트별)

```http
GET /mt/tenant/{tenant_id}/lrs?from=2026-01-01&to=2026-01-31
Headers:
  X-Market-API-Key: {api_key}
  # 또는 대학 관리자 토큰
  Authorization: Bearer {tenant_admin_token}

Response 200:
{
  "tenant_id": "hallym_univ",
  "period": {
    "from": "2026-01-01",
    "to": "2026-01-31"
  },
  "total_statements": 15000,
  "statements": [
    {
      "id": "uuid-1234",
      "actor": {
        "name": "홍길동",
        "account": {
          "name": "user123",
          "homePage": "https://hallym.ac.kr"
        }
      },
      "verb": {
        "id": "http://adlnet.gov/expapi/verbs/completed",
        "display": {"ko-KR": "완료함"}
      },
      "object": {
        "id": "https://keli.k-university.ai/course/101",
        "definition": {
          "name": {"ko-KR": "AI 기초 과정"}
        }
      },
      "result": {
        "score": {"scaled": 0.85},
        "completion": true
      },
      "timestamp": "2026-01-15T10:30:00Z"
    }
    // ... more statements
  ],
  "pagination": {
    "page": 1,
    "per_page": 100,
    "total_pages": 150
  }
}
```

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| from | string | ✅ | 시작일 (YYYY-MM-DD) |
| to | string | ✅ | 종료일 (YYYY-MM-DD) |
| verb | string | ❌ | 필터: 동사 ID |
| page | integer | ❌ | 페이지 번호 (기본: 1) |
| per_page | integer | ❌ | 페이지당 개수 (기본: 100, 최대: 1000) |

#### 3.2.7 분석 리포트 조회 (테넌트별)

```http
GET /mt/tenant/{tenant_id}/analytics?period=2026-01
Headers:
  X-Market-API-Key: {api_key}

Response 200:
{
  "tenant_id": "hallym_univ",
  "tenant_name": "한림대학교",
  "period": "2026-01",
  "summary": {
    "total_users": 500,
    "active_users": 350,
    "completion_rate": 0.72,
    "avg_session_duration_minutes": 45,
    "total_learning_hours": 2500
  },
  "engagement": {
    "daily_active_users": [120, 135, 142, ...],  // 일별 DAU
    "peak_hours": [9, 10, 14, 15],               // 피크 시간대
    "retention_rate": 0.85                       // 재방문율
  },
  "learning_outcomes": {
    "courses_completed": 450,
    "avg_score": 82.5,
    "top_performers": 50,
    "at_risk_students": 25
  },
  "ai_usage": {
    "total_conversations": 8500,
    "avg_turns_per_conversation": 12,
    "satisfaction_score": 4.2
  }
}
```

#### 3.2.8 전체 LRS 데이터 (Market 전용)

```http
GET /mt/tenants/lrs?from=2026-01-01&to=2026-01-31
Headers:
  X-Market-API-Key: {market_master_key}

Response 200:
{
  "period": {
    "from": "2026-01-01",
    "to": "2026-01-31"
  },
  "tenants": [
    {
      "tenant_id": "hallym_univ",
      "tenant_name": "한림대학교",
      "total_statements": 15000,
      "statements": [...]  // 또는 summary만
    },
    {
      "tenant_id": "korea_univ",
      "tenant_name": "고려대학교",
      "total_statements": 22000,
      "statements": [...]
    }
    // ... all tenants
  ],
  "total_statements_all": 150000
}
```

**참고:** 대용량 데이터의 경우 `summary_only=true` 파라미터로 요약만 조회 가능

#### 3.2.9 전체 분석 리포트 (Market 전용)

```http
GET /mt/tenants/analytics?period=2026-01
Headers:
  X-Market-API-Key: {market_master_key}

Response 200:
{
  "period": "2026-01",
  "overall_summary": {
    "total_tenants": 50,
    "total_users": 25000,
    "total_active_users": 18000,
    "avg_completion_rate": 0.68,
    "total_learning_hours": 125000
  },
  "tenants": [
    {
      "tenant_id": "hallym_univ",
      "tenant_name": "한림대학교",
      "summary": {...},
      "engagement": {...},
      "learning_outcomes": {...}
    },
    // ... all tenants
  ],
  "rankings": {
    "by_active_users": ["korea_univ", "snu", "hallym_univ", ...],
    "by_completion_rate": ["snu", "hallym_univ", "korea_univ", ...],
    "by_satisfaction": ["hallym_univ", "snu", "korea_univ", ...]
  }
}
```

#### 3.2.10 테넌트 비용 요약 조회

```http
GET /mt/tenant/{tenant_id}/billing?period=2026-01
Headers:
  X-Market-API-Key: {api_key}
  # 또는 대학 관리자 토큰
  Authorization: Bearer {tenant_admin_token}

Response 200:
{
  "tenant_id": "hallym_univ",
  "tenant_name": "한림대학교",
  "period": "2026-01",
  "billing_summary": {
    "total_amount": 1250000,
    "currency": "KRW",
    "status": "pending"  // pending, paid, overdue
  },
  "cost_breakdown": {
    "api_costs": {
      "total": 450000,
      "details": {
        "openai_gpt4": 320000,
        "openai_embedding": 80000,
        "claude_api": 50000
      }
    },
    "cloud_costs": {
      "total": 550000,
      "details": {
        "compute": 250000,
        "storage": 150000,
        "database": 100000,
        "network": 50000
      }
    },
    "subscription_fee": {
      "total": 250000,
      "plan": "premium",
      "base_fee": 200000,
      "additional_users_fee": 50000
    }
  },
  "usage_summary": {
    "ai_tokens_used": 2500000,
    "api_calls": 150000,
    "storage_gb": 45,
    "active_users": 320
  }
}
```

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| period | string | ✅ | 조회 기간 (YYYY-MM) |

#### 3.2.11 테넌트 비용 상세 내역

```http
GET /mt/tenant/{tenant_id}/billing/details?period=2026-01&category=api_costs
Headers:
  X-Market-API-Key: {api_key}

Response 200:
{
  "tenant_id": "hallym_univ",
  "period": "2026-01",
  "category": "api_costs",
  "daily_breakdown": [
    {
      "date": "2026-01-01",
      "items": [
        {
          "service": "openai_gpt4",
          "usage": {
            "input_tokens": 150000,
            "output_tokens": 50000,
            "requests": 1200
          },
          "unit_price": {
            "input_per_1k": 30,
            "output_per_1k": 60
          },
          "amount": 7500
        },
        {
          "service": "openai_embedding",
          "usage": {
            "tokens": 500000,
            "requests": 800
          },
          "unit_price": {
            "per_1k_tokens": 0.13
          },
          "amount": 65
        }
      ],
      "daily_total": 7565
    },
    // ... 일별 내역
  ],
  "category_total": 450000,
  "pagination": {
    "page": 1,
    "per_page": 31,
    "total_days": 31
  }
}
```

**쿼리 파라미터:**

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| period | string | ✅ | 조회 기간 (YYYY-MM) |
| category | string | ❌ | 카테고리 필터 (api_costs, cloud_costs, subscription_fee) |
| page | integer | ❌ | 페이지 번호 (기본: 1) |

#### 3.2.12 전체 비용 조회 (Market 전용)

```http
GET /mt/tenants/billing?period=2026-01
Headers:
  X-Market-API-Key: {market_master_key}

Response 200:
{
  "period": "2026-01",
  "overall_summary": {
    "total_tenants": 50,
    "total_revenue": 62500000,
    "total_api_costs": 22500000,
    "total_cloud_costs": 27500000,
    "total_subscription_fees": 12500000,
    "currency": "KRW"
  },
  "tenants": [
    {
      "tenant_id": "hallym_univ",
      "tenant_name": "한림대학교",
      "plan": "premium",
      "billing_summary": {
        "total_amount": 1250000,
        "api_costs": 450000,
        "cloud_costs": 550000,
        "subscription_fee": 250000,
        "status": "paid"
      }
    },
    {
      "tenant_id": "korea_univ",
      "tenant_name": "고려대학교",
      "plan": "standard",
      "billing_summary": {
        "total_amount": 850000,
        "api_costs": 320000,
        "cloud_costs": 380000,
        "subscription_fee": 150000,
        "status": "pending"
      }
    }
    // ... all tenants
  ],
  "rankings": {
    "by_total_cost": ["hallym_univ", "korea_univ", "snu", ...],
    "by_api_usage": ["korea_univ", "hallym_univ", "snu", ...],
    "by_efficiency": ["snu", "hallym_univ", "korea_univ", ...]  // 비용 대비 활용도
  },
  "cost_trends": {
    "monthly_growth_rate": 0.12,
    "api_cost_trend": [18500000, 20200000, 22500000],  // 최근 3개월
    "cloud_cost_trend": [25000000, 26200000, 27500000]
  }
}
```

---

## 4. manifest.yaml 규격

### 4.1 manifest 규격

```yaml
# manifest.yaml - 서비스 등록 명세서
version: "1.0"

# 서비스 기본 정보
service:
  id: "keli_tutor"
  name: "KELI TUTOR"
  description: "AI 기반 학습 튜터 서비스"
  version: "2.0.0"
  vendor: "K-University AI Lab"
  contact: "support@k-university.ai"

# API 엔드포인트
endpoints:
  # 서비스 기본 URL
  base_url: "https://keli.k-university.ai"

  # === 기본 API (필수) ===
  health: "/mt/health"
  activate: "/mt/tenant/{tenant_id}/activate"
  deactivate: "/mt/tenant/{tenant_id}/deactivate"
  status: "/mt/tenant/{tenant_id}/status"
  usage: "/mt/tenant/{tenant_id}/usage"

  # === 데이터/분석 API (필수) ===
  # 테넌트별 LRS 데이터 (Market, 대학 관리자 호출)
  tenant_lrs: "/mt/tenant/{tenant_id}/lrs"
  # 테넌트별 분석 리포트 (Market, 대학 관리자 호출)
  tenant_analytics: "/mt/tenant/{tenant_id}/analytics"
  # 전체 LRS (Market 전용)
  all_lrs: "/mt/tenants/lrs"
  # 전체 분석 (Market 전용)
  all_analytics: "/mt/tenants/analytics"

  # === 비용 API (필수) ===
  # 테넌트별 비용 요약 (Market, 대학 관리자 호출)
  tenant_billing: "/mt/tenant/{tenant_id}/billing"
  # 테넌트별 비용 상세 (Market, 대학 관리자 호출)
  tenant_billing_details: "/mt/tenant/{tenant_id}/billing/details"
  # 전체 비용 (Market 전용)
  all_billing: "/mt/tenants/billing"

  # 사용자 접속 URL 패턴
  # {tenant_id}가 실제 테넌트 ID로 치환됨
  user_access: "/{tenant_id}"

  # 대학 관리자 분석 대시보드 (선택)
  admin_dashboard: "/{tenant_id}/admin/analytics"

# 마켓-서비스 간 인증
auth:
  type: "api_key"
  header: "X-Market-API-Key"

# 대학 관리자 인증 (분석 대시보드 접근용)
tenant_admin_auth:
  type: "jwt"  # jwt 또는 university_sso
  # JWT 발급은 서비스에서 처리

# 요금제별 기능 정의
plans:
  basic:
    features:
      - "ai_chat"
      - "file_upload"
    limits:
      max_users: 100
      storage_gb: 10

  standard:
    features:
      - "ai_chat"
      - "file_upload"
      - "rag"
    limits:
      max_users: 300
      storage_gb: 50

  premium:
    features:
      - "ai_chat"
      - "file_upload"
      - "rag"
      - "quiz"
      - "discussion"
    limits:
      max_users: 1000
      storage_gb: 200

# 사용량 메트릭 정의 (마켓 대시보드 표시용)
usage_metrics:
  - key: "active_users"
    name: "활성 사용자"
    unit: "명"
  - key: "ai_tokens"
    name: "AI 토큰"
    unit: "tokens"
  - key: "storage_mb"
    name: "스토리지"
    unit: "MB"
```

### 4.2 manifest 필드 설명

| 섹션 | 필드 | 필수 | 설명 |
|------|------|------|------|
| service | id | ✅ | 서비스 고유 ID |
| service | name | ✅ | 표시명 |
| service | version | ✅ | 서비스 버전 |
| endpoints | base_url | ✅ | 서비스 기본 URL |
| endpoints | health | ✅ | 헬스체크 경로 |
| endpoints | activate | ✅ | 활성화 API 경로 |
| endpoints | deactivate | ✅ | 비활성화 API 경로 |
| endpoints | status | ✅ | 상태 조회 경로 |
| endpoints | usage | ✅ | 사용량 조회 경로 |
| endpoints | tenant_lrs | ✅ | 테넌트 LRS 조회 경로 |
| endpoints | tenant_analytics | ✅ | 테넌트 분석 조회 경로 |
| endpoints | tenant_billing | ✅ | 테넌트 비용 조회 경로 |
| endpoints | tenant_billing_details | ✅ | 테넌트 비용 상세 경로 |
| endpoints | all_lrs | ✅ | 전체 LRS 조회 (Market 전용) |
| endpoints | all_analytics | ✅ | 전체 분석 조회 (Market 전용) |
| endpoints | all_billing | ✅ | 전체 비용 조회 (Market 전용) |
| endpoints | user_access | ✅ | 사용자 접속 URL 패턴 |
| endpoints | admin_dashboard | ❌ | 관리자 대시보드 URL |
| auth | type | ✅ | Market-서비스 인증 방식 |
| tenant_admin_auth | type | ✅ | 대학 관리자 인증 방식 |
| plans | * | ✅ | 요금제별 기능/제한 |
| usage_metrics | * | ✅ | 사용량 메트릭 정의 |
| lrs_config | * | ✅ | LRS 설정 (아래 참조) |
| analytics_config | * | ✅ | 분석 설정 (아래 참조) |
| pricing_config | * | ✅ | 비용 설정 (아래 참조) |

### 4.3 데이터 격리 설정

```yaml
# manifest.yaml 계속

# 데이터 격리 방식
data_isolation:
  # 테넌트별 격리 수준
  level: "database_per_tenant"  # database_per_tenant, schema_per_tenant

  # 격리되는 데이터 유형
  isolated_data:
    - "user_data"       # 사용자 정보
    - "lrs_statements"  # 학습 활동 기록
    - "chat_history"    # 대화 이력
    - "files"           # 업로드 파일
    - "analytics"       # 분석 데이터

# LRS 설정
lrs_config:
  # xAPI 표준 준수
  xapi_version: "1.0.3"

  # 수집하는 statement 유형
  verbs:
    - "completed"
    - "answered"
    - "asked"
    - "viewed"
    - "interacted"

  # 데이터 보존 기간 (일)
  retention_days: 365

# 분석 설정
analytics_config:
  # 제공하는 분석 유형
  reports:
    - type: "engagement"
      name: "학습 참여도 분석"
      description: "DAU, MAU, 세션 시간 등"
    - type: "learning_outcomes"
      name: "학습 성과 분석"
      description: "완료율, 점수, 성취도"
    - type: "ai_usage"
      name: "AI 활용 분석"
      description: "대화 수, 만족도"

  # 실시간 분석 지원 여부
  realtime: false

  # 분석 업데이트 주기
  update_frequency: "daily"  # realtime, hourly, daily

# 비용 설정
pricing_config:
  # 통화
  currency: "KRW"

  # 요금제별 구독료
  subscription_fees:
    basic:
      monthly: 100000
      annual: 1000000  # 연간 할인
    standard:
      monthly: 150000
      annual: 1500000
    premium:
      monthly: 250000
      annual: 2500000

  # API 비용 (외부 API 사용 시)
  api_costs:
    # OpenAI
    openai_gpt4:
      input_per_1k_tokens: 30    # KRW
      output_per_1k_tokens: 60   # KRW
    openai_gpt35:
      input_per_1k_tokens: 1.5
      output_per_1k_tokens: 2
    openai_embedding:
      per_1k_tokens: 0.13

    # Claude
    claude_sonnet:
      input_per_1k_tokens: 3
      output_per_1k_tokens: 15
    claude_haiku:
      input_per_1k_tokens: 0.25
      output_per_1k_tokens: 1.25

  # 클라우드 비용
  cloud_costs:
    # 컴퓨팅
    compute:
      per_vcpu_hour: 50       # KRW
      per_gb_memory_hour: 10
    # 스토리지
    storage:
      per_gb_month: 100
    # 데이터베이스
    database:
      per_gb_month: 500
    # 네트워크
    network:
      per_gb_egress: 120

  # 추가 사용자 요금 (요금제 한도 초과 시)
  additional_user_fee:
    per_user_monthly: 1000

  # 비용 계산 주기
  billing_cycle: "monthly"  # monthly, annual

  # 청구서 생성일 (매월)
  billing_day: 1
```

---

## 5. 테넌트 라이프사이클

### 5.1 상태 다이어그램

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│ PENDING │───▶│ ACTIVE  │───▶│SUSPENDED│───▶│ DELETED │ │
└─────────┘    └─────────┘    └─────────┘    └─────────┘ │
                    │              │                     │
                    │              │ 재활성화            │
                    │              ▼                     │
                    └──────────────┘                     │
                                                         │
                              데이터 보존 기간 만료 시 ───┘
```

### 5.2 상태별 설명

| 상태 | 설명 | 서비스 접근 | 데이터 |
|------|------|------------|--------|
| PENDING | 활성화 대기 | ❌ | 없음 |
| ACTIVE | 정상 운영 | ✅ | 사용 가능 |
| SUSPENDED | 일시 중지 | ❌ | 보존 |
| DELETED | 완전 삭제 | ❌ | 삭제됨 |

### 5.3 라이프사이클 흐름

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│Service Market│    │   서비스     │    │    대학교    │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ ─────── 서비스 구독 시 ────────        │
       │                   │                   │
       │ 1. POST /activate │                   │
       │──────────────────▶│                   │
       │                   │                   │
       │                   │ (테넌트 생성      │
       │                   │  DB/자원 할당)    │
       │                   │                   │
       │ 2. 접속 URL 반환  │                   │
       │◀──────────────────│                   │
       │                   │                   │
       │ 3. 접속 링크 안내 │                   │
       │───────────────────────────────────────▶
       │                   │                   │
       │                   │ 4. 링크로 접속    │
       │                   │◀──────────────────│
       │                   │                   │
       │                   │ 5. 자체 로그인    │
       │                   │   처리            │
       │                   │                   │
       │                   │ 6. 서비스 이용    │
       │                   │◀─────────────────▶│
       │                   │                   │
       │ ─────── 구독 만료 시 ─────────        │
       │                   │                   │
       │ 7. POST /deactivate                   │
       │──────────────────▶│                   │
       │                   │                   │
       │                   │ (접근 차단        │
       │                   │  데이터 보존)     │
       │                   │                   │
       │ 8. 차단 완료      │                   │
       │◀──────────────────│                   │
       │                   │                   │
```

---

## 6. Service Market 구현 요구사항

### 6.1 서비스 등록 관리

```python
# 개념적 구현 (실제 구현은 service_market에서)

class ServiceRegistry:
    """서비스 등록 및 관리"""

    def register_service(self, manifest: dict) -> bool:
        """
        manifest.yaml 검증 및 서비스 등록

        1. manifest 스키마 검증
        2. 엔드포인트 접근 테스트 (health check)
        3. 서비스 정보 DB 저장
        4. API 키 발급
        """
        pass

    def validate_manifest(self, manifest: dict) -> ValidationResult:
        """manifest 유효성 검증"""
        pass

    def test_endpoints(self, base_url: str, endpoints: dict) -> bool:
        """엔드포인트 접근 테스트"""
        pass
```

### 6.2 테넌트 라이프사이클 관리

```python
class TenantLifecycleManager:
    """테넌트 라이프사이클 관리"""

    async def activate_tenant(
        self,
        service_id: str,
        tenant_id: str,
        plan: str,
        config: dict
    ) -> ActivationResult:
        """
        테넌트 활성화

        1. 서비스의 /activate API 호출
        2. 응답에서 access_url 추출
        3. 테넌트 정보 저장
        4. 대학에 접속 링크 안내
        """
        pass

    async def deactivate_tenant(
        self,
        service_id: str,
        tenant_id: str,
        reason: str,
        preserve_data: bool = True
    ) -> DeactivationResult:
        """
        테넌트 비활성화

        1. 서비스의 /deactivate API 호출
        2. 테넌트 상태 업데이트
        3. 대학에 알림
        """
        pass
```

### 6.3 모니터링 및 데이터 수집

```python
class MonitoringService:
    """서비스 모니터링 및 사용량 수집"""

    async def check_health(self, service_id: str) -> HealthStatus:
        """
        주기적 헬스체크 (1분마다)

        1. /health API 호출
        2. 상태 기록
        3. 연속 실패 시 알림
        """
        pass

    async def collect_usage(
        self,
        service_id: str,
        tenant_id: str,
        period: str
    ) -> UsageData:
        """
        사용량 데이터 수집

        1. /usage API 호출
        2. 대시보드 표시용 데이터 저장
        3. 과금 계산에 활용 (필요 시)
        """
        pass
```

---

## 7. 서비스 업체 구현 가이드

### 7.1 필수 구현 체크리스트

```
□ manifest.yaml 작성
□ GET  /mt/health 구현
□ POST /mt/tenant/{id}/activate 구현
□ POST /mt/tenant/{id}/deactivate 구현
□ GET  /mt/tenant/{id}/status 구현
□ GET  /mt/tenant/{id}/usage 구현
□ 테넌트별 접속 URL 라우팅
□ 인증 시스템 (자체 구현 또는 대학 연동)
```

### 7.2 FastAPI 구현 예시

```python
# mt_standard_api.py - 표준 API 구현 예시

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/mt")

# 요청/응답 모델
class ActivateRequest(BaseModel):
    tenant_id: str
    tenant_name: str
    plan: str
    features: List[str]
    config: Optional[dict] = {}
    contact: dict

class ActivateResponse(BaseModel):
    success: bool
    tenant_id: str
    access_url: str
    message: str

class DeactivateRequest(BaseModel):
    reason: str
    preserve_data: bool = True

class StatusResponse(BaseModel):
    tenant_id: str
    status: str
    plan: str
    features: List[str]
    created_at: datetime
    updated_at: datetime

class UsageResponse(BaseModel):
    tenant_id: str
    period: str
    usage: dict


# API Key 검증
def verify_api_key(api_key: str = Header(..., alias="X-Market-API-Key")):
    expected_key = os.getenv("MARKET_API_KEY")
    if api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


# 표준 API 구현
@router.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.post("/tenant/{tenant_id}/activate", response_model=ActivateResponse)
async def activate_tenant(
    tenant_id: str,
    request: ActivateRequest,
    api_key: str = Depends(verify_api_key)
):
    """테넌트 활성화"""
    # 1. 이미 존재하는지 확인
    if await tenant_exists(tenant_id):
        raise HTTPException(status_code=409, detail="Tenant already exists")

    # 2. 테넌트 생성 (DB, 초기 설정 등)
    await create_tenant(
        tenant_id=tenant_id,
        name=request.tenant_name,
        plan=request.plan,
        features=request.features,
        config=request.config
    )

    # 3. 접속 URL 생성
    base_url = os.getenv("SERVICE_BASE_URL")
    access_url = f"{base_url}/{tenant_id}"

    return ActivateResponse(
        success=True,
        tenant_id=tenant_id,
        access_url=access_url,
        message="Tenant activated successfully"
    )


@router.post("/tenant/{tenant_id}/deactivate")
async def deactivate_tenant(
    tenant_id: str,
    request: DeactivateRequest,
    api_key: str = Depends(verify_api_key)
):
    """테넌트 비활성화"""
    # 1. 존재 확인
    if not await tenant_exists(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")

    # 2. 비활성화 처리
    await suspend_tenant(
        tenant_id=tenant_id,
        reason=request.reason,
        preserve_data=request.preserve_data
    )

    return {
        "success": True,
        "tenant_id": tenant_id,
        "status": "deactivated",
        "data_preserved": request.preserve_data
    }


@router.get("/tenant/{tenant_id}/status", response_model=StatusResponse)
async def get_tenant_status(
    tenant_id: str,
    api_key: str = Depends(verify_api_key)
):
    """테넌트 상태 조회"""
    tenant = await get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return StatusResponse(
        tenant_id=tenant.id,
        status=tenant.status,
        plan=tenant.plan,
        features=tenant.features,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at
    )


@router.get("/tenant/{tenant_id}/usage", response_model=UsageResponse)
async def get_tenant_usage(
    tenant_id: str,
    period: str,
    api_key: str = Depends(verify_api_key)
):
    """사용량 조회"""
    usage = await get_usage_stats(tenant_id, period)

    return UsageResponse(
        tenant_id=tenant_id,
        period=period,
        usage={
            "active_users": usage.active_users,
            "total_sessions": usage.total_sessions,
            "api_calls": usage.api_calls,
            "ai_tokens": usage.ai_tokens,
            "storage_mb": usage.storage_mb
        }
    )
```

### 7.3 인증 구현 옵션

서비스 업체는 다음 중 선택하여 구현:

#### 옵션 A: 자체 로그인 시스템

```python
# 서비스 자체 로그인
@router.post("/{tenant_id}/auth/login")
async def login(tenant_id: str, credentials: LoginRequest):
    # 테넌트 DB에서 사용자 확인
    user = await verify_user(tenant_id, credentials)
    # JWT 토큰 발급
    token = create_jwt(user)
    return {"access_token": token}
```

#### 옵션 B: 대학 SSO 연동

```python
# 대학 SSO 리다이렉트
@router.get("/{tenant_id}/auth/sso")
async def sso_redirect(tenant_id: str):
    tenant = await get_tenant(tenant_id)
    # 대학별 SSO URL로 리다이렉트
    return RedirectResponse(tenant.sso_url)

@router.get("/{tenant_id}/auth/callback")
async def sso_callback(tenant_id: str, token: str):
    # 대학 SSO 토큰 검증
    user_info = await verify_university_token(tenant_id, token)
    # 서비스 토큰 발급
    service_token = create_jwt(user_info)
    return {"access_token": service_token}
```

---

## 8. 예상 시나리오

### 8.1 신규 서비스 등록

```
1. 서비스 업체: manifest.yaml 작성
2. 서비스 업체: 표준 API 5개 구현
3. 서비스 업체: Service Market에 등록 요청
4. Service Market: manifest 검증
5. Service Market: /health API 테스트
6. Service Market: 서비스 등록 완료, API 키 발급
7. 서비스 업체: API 키로 운영 시작

예상 소요: 1~2일
```

### 8.2 학교 서비스 구독

```
1. 대학 담당자: Service Market에서 서비스 선택
2. 대학 담당자: 요금제 선택 및 결제
3. Service Market: /activate API 호출
4. 서비스: 테넌트 생성, access_url 반환
5. Service Market: 대학에 접속 링크 안내
6. 대학: 링크를 포털에 등록
7. 사용자: 링크 클릭 → 서비스 접속 → 자체 로그인

예상 소요: 즉시 (자동화)
```

### 8.3 구독 만료

```
1. Service Market: 만료 7일 전 알림 발송
2. 대학: 갱신 또는 무시
3. (갱신 없을 경우)
4. Service Market: 만료일에 /deactivate 호출
5. 서비스: 접근 차단, 데이터 보존
6. Service Market: 대학에 만료 안내
7. (90일 후 데이터 삭제)
```

---

## 9. 장점 요약

| 관점 | 장점 |
|------|------|
| **Service Market** | 모든 데이터 접근 가능, 통합 분석/관리 |
| **서비스 업체** | 표준 API 구현, 대학별 격리 자율 운영 |
| **대학교** | 자기 데이터만 안전하게 접근, 분석 리포트 제공 |
| **데이터 격리** | 대학별 완전 분리, 교차 접근 불가 |
| **확장성** | 서비스/대학 추가 시 기존 구조 유지 |

---

## 10. 데이터 흐름 요약

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           데이터 흐름                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   [사용자 활동]                                                          │
│        │                                                                 │
│        ▼                                                                 │
│   [서비스: 대학별 격리 DB/LRS에 저장]                                    │
│        │                                                                 │
│        ├─────────────────────┬─────────────────────┐                    │
│        ▼                     ▼                     ▼                    │
│   ┌─────────┐           ┌─────────┐           ┌─────────┐              │
│   │ 한림 DB │           │ 고려 DB │           │ 서울 DB │              │
│   │ 한림 LRS│           │ 고려 LRS│           │ 서울 LRS│              │
│   └────┬────┘           └────┬────┘           └────┬────┘              │
│        │                     │                     │                    │
│        ▼                     ▼                     ▼                    │
│   [분석 서비스가 각 대학 데이터 분석]                                    │
│        │                     │                     │                    │
│        ├─────────────────────┴─────────────────────┤                    │
│        │                                           │                    │
│        ▼                                           ▼                    │
│   ┌──────────────┐                        ┌──────────────┐             │
│   │ Market API   │                        │ 대학 관리자   │             │
│   │ (전체 접근)   │                        │ (자기만 접근) │             │
│   └──────────────┘                        └──────────────┘             │
│        │                                           │                    │
│        ▼                                           ▼                    │
│   [통합 대시보드]                          [대학별 대시보드]             │
│   - 전체 서비스 현황                       - 해당 대학 현황              │
│   - 전체 대학 비교                         - 학습 성과 리포트            │
│   - 랭킹 분석                              - 사용자 분석                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 11. 다음 단계

### 11.1 구현 우선순위

1. **Service Market 측**
   - [ ] 표준 API 호출 클라이언트 구현
   - [ ] manifest.yaml 검증 로직
   - [ ] 서비스 등록 UI/API
   - [ ] 테넌트 라이프사이클 관리 UI
   - [ ] 통합 LRS/분석 대시보드

2. **기존 서비스 (keli_tutor, llm_chatbot)**
   - [ ] 대학별 격리 DB/LRS 구조 적용
   - [ ] 표준 API 래퍼 추가 (기본 + LRS + 분석)
   - [ ] manifest.yaml 작성
   - [ ] 대학 관리자용 분석 대시보드

3. **데이터/분석**
   - [ ] xAPI 표준 LRS 저장소 구현
   - [ ] 분석 엔진 구현 (참여도, 성과, AI 사용량)
   - [ ] 대학별 리포트 생성기

4. **문서화**
   - [ ] 서비스 업체용 연동 가이드
   - [ ] API 레퍼런스 문서
   - [ ] 데이터 격리 가이드

### 11.2 테스트 계획

```
1. 단위 테스트: 각 표준 API 동작 확인
2. 격리 테스트: 대학 A가 대학 B 데이터 접근 불가 확인
3. 권한 테스트: Market/서비스/대학 권한별 접근 확인
4. 통합 테스트: Market ↔ 서비스 연동 확인
5. E2E 테스트: 전체 플로우 (구독 → 활성화 → 사용 → 분석 → 만료)
```

---

## 12. 핵심 정리

### 12.1 3줄 요약

1. **서비스 업체**: 대학별로 격리된 DB/LRS를 운영하고, 표준 API로 데이터 제공
2. **대학교**: 자기 대학 데이터만 접근 가능, 분석 리포트 열람
3. **Service Market**: 모든 서비스/대학 데이터에 접근하여 통합 분석

### 12.2 API 체크리스트

```
서비스 업체가 구현해야 할 API:

=== 기본 API (5개) ===
□ GET  /mt/health                      서비스 상태 확인
□ POST /mt/tenant/{id}/activate        테넌트 활성화
□ POST /mt/tenant/{id}/deactivate      테넌트 비활성화
□ GET  /mt/tenant/{id}/status          테넌트 상태 조회
□ GET  /mt/tenant/{id}/usage           사용량 조회

=== 데이터/분석 API (4개) ===
□ GET  /mt/tenant/{id}/lrs             테넌트 LRS 조회
□ GET  /mt/tenant/{id}/analytics       테넌트 분석 조회
□ GET  /mt/tenants/lrs                 전체 LRS (Market 전용)
□ GET  /mt/tenants/analytics           전체 분석 (Market 전용)

=== 비용 API (3개) ← NEW ===
□ GET  /mt/tenant/{id}/billing         테넌트 비용 조회 (대학, Market)
□ GET  /mt/tenants/billing             전체 비용 조회 (Market 전용)
□ GET  /mt/tenant/{id}/billing/details 비용 상세 내역 (대학, Market)
```

---

**문서 끝**
