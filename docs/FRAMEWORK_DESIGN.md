# Multi-Tenant PaaS 프레임워크 설계서

> 서비스 업체를 위한 표준화된 멀티테넌트 온보딩 프레임워크

**작성일**: 2026-01-03
**버전**: 0.2
**상태**: 컨설팅 반영 완료

---

## 1. 프레임워크 개요

### 1.1 목적

**두 가지 목표 동시 달성:**

1. **내부 효율화**: llm_chatbot, advisor 등 기존 서비스의 중복 코드 통합
2. **플랫폼화**: 외부 서비스 업체가 mt_paas 규격에 맞춰 쉽게 온보딩

### 1.2 핵심 가치

```
┌─────────────────────────────────────────────────────────────┐
│                    service_market                            │
│                                                              │
│  "mt_paas 규격에 맞춰서 개발해오면 우리가 관리해줄게"          │
│                                                              │
│  • 테넌트 관리 자동화                                         │
│  • 구독/과금 통합                                             │
│  • 모니터링/보안 감사                                         │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ mt_paas 프레임워크 제공
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              서비스 업체 (내부/외부 모두)                      │
│                                                              │
│  from mt_paas import ServiceMarketFramework                 │
│                                                              │
│  → 테넌트 인식: 자동                                         │
│  → DB 분리: 자동                                             │
│  → 권한/만료 체크: 자동                                       │
│  → 비즈니스 로직만 집중!                                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 서비스 업체 관점의 변화

| 항목 | 기존 (각자 구현) | mt_paas 도입 후 |
|------|-----------------|----------------|
| **테넌트 인식** | URL, Header 분석 직접 코딩 | `request.tenant`로 자동 주입 |
| **DB 분리** | 테넌트별 연결/전환 로직 구현 | `get_db()` 호출 시 자동 연결 |
| **권한/만료** | 마켓 API 호출 로직 직접 작성 | 프레임워크가 자동 체크/차단 |
| **활동 로그** | 직접 구현 또는 없음 | `log_activity()` 호출로 자동 전송 |

---

## 2. 프레임워크 3대 구성 요소

### 2.1 테넌트 컨텍스트 SDK (The Library)

서비스 업체가 `pip install`로 설치하는 라이브러리

```
mt_paas/
├── core/
│   ├── framework.py      # ServiceMarketFramework 메인 클래스
│   ├── manager.py        # TenantManager
│   ├── models.py         # Tenant, Subscription 모델
│   └── database.py       # DatabaseRouter (테넌트별 DB 연결)
│
├── middleware/
│   ├── tenant.py         # TenantMiddleware (테넌트 식별)
│   ├── auth.py           # 인증/권한 체크
│   └── subscription.py   # 구독 상태/만료 체크
│
└── integrations/
    ├── marketplace.py    # MarketplaceClient (마켓 API 연동)
    └── activity_log.py   # 활동 로그 (xAPI 등)
```

### 2.2 인프라 청사진 (The Infrastructure Template)

Docker-Per-Tenant를 위한 표준 템플릿

```
mt_paas/
└── templates/
    ├── docker-compose.template.yml   # 컨테이너 세트 표준 규격
    ├── .env.template                 # 환경변수 템플릿
    └── provisioning/
        ├── create_tenant.py          # 테넌트 생성 스크립트
        └── destroy_tenant.py         # 테넌트 삭제 스크립트
```

### 2.3 중앙 관제 인터페이스 (The Control Plane)

마켓과 서비스 간 통신 규약

```
mt_paas/
└── control/
    ├── heartbeat.py      # 서비스 상태 보고
    ├── kill_switch.py    # 원격 차단 (만료/위반 시)
    └── audit.py          # 보안 감사 로그
```

---

## 3. 서비스 설정 파일 규격 (config.yaml)

서비스 업체가 mt_paas를 사용할 때 작성해야 하는 설정 파일

### 3.1 기본 구조

```yaml
# mt_paas_config.yaml

# ============================================================
# 서비스 기본 정보
# ============================================================
service:
  id: "keli_tutor"                    # 서비스 고유 ID
  name: "KELI TUTOR"                  # 서비스 표시명
  version: "1.0.0"                    # 서비스 버전
  description: "AI 기반 학습 튜터"

# ============================================================
# Service Market 연동
# ============================================================
marketplace:
  api_url: "https://market.k-university.ai/api/v1"
  api_key: "${MARKETPLACE_API_KEY}"   # 환경변수 참조

  # 상태 보고 주기
  heartbeat_interval: 60              # 초 단위

  # 구독 체크
  subscription_check: true
  grace_period_hours: 24              # 만료 후 유예 기간

# ============================================================
# 테넌트 격리 방식
# ============================================================
isolation:
  # 격리 모드 선택
  # - DATABASE_PER_TENANT: DB만 분리 (리소스 효율적)
  # - DOCKER_PER_TENANT: 컨테이너 완전 분리 (보안 최고)
  # - SCHEMA_PER_TENANT: 스키마 분리 (중간)
  mode: "DATABASE_PER_TENANT"

  # Docker-Per-Tenant 전용 설정
  docker:
    port_range_start: 10200
    port_range_size: 100              # 테넌트당 포트 수
    compose_template: "templates/docker-compose.template.yml"

# ============================================================
# 데이터베이스 설정
# ============================================================
database:
  # Central DB (테넌트 메타정보)
  central:
    url: "postgresql://localhost:5432/mt_paas_central"
    pool_size: 10

  # Tenant DB 설정
  tenant:
    url_template: "postgresql://localhost:5432/tenant_{tenant_id}"
    pool_size_per_tenant: 5

  # Vector DB (RAG용)
  vector:
    type: "qdrant"                    # qdrant, chroma, milvus
    url: "http://localhost:6333"
    collection_prefix: "tenant_"

# ============================================================
# 테넌트 식별 방법
# ============================================================
tenant_identification:
  # 우선순위 순서대로 시도
  methods:
    - type: "header"
      name: "X-Tenant-ID"
    - type: "subdomain"               # hallym.keli.k-university.ai
      extract_pattern: "^([^.]+)"
    - type: "jwt_claim"
      claim_name: "tenant_id"
    - type: "query_param"
      name: "tenant_id"

# ============================================================
# 인증 설정
# ============================================================
auth:
  jwt:
    secret: "${JWT_SECRET}"
    algorithm: "HS256"
    expiry_hours: 24

  # 마켓 SSO 연동
  marketplace_sso:
    enabled: true
    callback_url: "/auth/marketplace/callback"

# ============================================================
# 기능 플래그 (요금제별 제어)
# ============================================================
features:
  # 마켓에서 구독 정보로 자동 제어
  controlled_by_subscription: true

  # 기본값 (구독 정보 없을 때)
  defaults:
    ai_chat: true
    file_upload: true
    rag: false
    discussion: false
    quiz: false
    api_integration: false

# ============================================================
# 보안 설정
# ============================================================
security:
  # 테넌트 간 접근 감시
  cross_tenant_audit: true

  # 민감 데이터 암호화
  encryption:
    enabled: true
    key: "${AES_SECRET_KEY}"

  # Rate Limiting (요금제별)
  rate_limit:
    enabled: true
    default_rpm: 60                   # requests per minute

# ============================================================
# 로깅 및 모니터링
# ============================================================
logging:
  level: "INFO"

  # 활동 로그 (LRS)
  activity_log:
    enabled: true
    endpoint: "https://lrs.k-university.ai/xapi"

  # 사용량 보고
  usage_report:
    enabled: true
    interval_minutes: 5

# ============================================================
# 서비스별 커스텀 설정 (서비스 업체가 추가)
# ============================================================
custom:
  # 예: keli_tutor 전용 설정
  llm:
    default_model: "gpt-4"
    fallback_model: "gpt-3.5-turbo"

  rag:
    chunk_size: 500
    overlap: 50
```

### 3.2 환경별 오버라이드

```yaml
# mt_paas_config.dev.yaml (개발 환경)
database:
  central:
    url: "postgresql://localhost:5432/mt_paas_central_dev"
  tenant:
    url_template: "postgresql://localhost:5432/tenant_dev_{tenant_id}"

marketplace:
  api_url: "http://localhost:8505/api/v1"

logging:
  level: "DEBUG"
```

```yaml
# mt_paas_config.prod.yaml (운영 환경)
database:
  central:
    url: "postgresql://db.k-university.ai:5432/mt_paas_central"
    pool_size: 50

security:
  rate_limit:
    enabled: true
    default_rpm: 100
```

---

## 4. 서비스 업체 사용 예시

### 4.1 기본 사용법

```python
# main.py
from fastapi import FastAPI
from mt_paas import ServiceMarketFramework

# 1. 프레임워크 초기화
framework = ServiceMarketFramework(
    config_path="mt_paas_config.yaml"
)

# 2. FastAPI 앱 생성 (프레임워크가 미들웨어 자동 등록)
app = framework.create_app()

# 3. 비즈니스 로직 작성 (테넌트 걱정 없이!)
@app.get("/courses")
async def get_courses(tenant = framework.get_current_tenant()):
    # DB는 이미 해당 테넌트 것으로 연결됨
    db = framework.get_tenant_db()
    courses = await db.execute(select(Course))
    return courses

@app.post("/chat")
async def chat(message: str, tenant = framework.get_current_tenant()):
    # 비즈니스 로직만 집중
    response = await ai_chat(message)

    # 활동 로그 자동 전송
    framework.log_activity(
        verb="asked",
        object="ai_tutor",
        result={"message_length": len(response)}
    )

    return {"response": response}
```

### 4.2 격리 모드별 동작

```python
# config에서 isolation.mode에 따라 자동으로 다르게 동작

# DATABASE_PER_TENANT 모드
db = framework.get_tenant_db()
# → postgresql://localhost/tenant_hallym 에 연결

# DOCKER_PER_TENANT 모드
db = framework.get_tenant_db()
# → 해당 테넌트 컨테이너의 DB (10202 포트) 에 연결
```

### 4.3 구독 상태 체크 (자동)

```python
# 미들웨어가 모든 요청에서 자동 체크
# 만료된 테넌트는 자동으로 403 응답

# 수동으로 체크하고 싶을 때
@app.get("/premium-feature")
async def premium_feature(tenant = framework.get_current_tenant()):
    # 특정 기능 사용 가능 여부 체크
    if not framework.has_feature("quiz"):
        raise HTTPException(403, "이 기능은 Premium 요금제에서 사용 가능합니다")

    return await generate_quiz()
```

---

## 5. Control Plane API

### 5.1 Heartbeat (서비스 → 마켓)

```python
# 프레임워크가 자동으로 주기적 호출
POST /api/v1/services/{service_id}/heartbeat

{
    "service_id": "keli_tutor",
    "status": "healthy",
    "active_tenants": ["hallym", "korea", "snu"],
    "metrics": {
        "requests_per_minute": 150,
        "error_rate": 0.01,
        "avg_response_time_ms": 250
    },
    "timestamp": "2026-01-03T12:00:00Z"
}
```

### 5.2 Kill-Switch (마켓 → 서비스)

```python
# 마켓에서 테넌트 차단 명령
POST /api/v1/services/{service_id}/tenants/{tenant_id}/block

{
    "reason": "subscription_expired",
    "block_at": "2026-01-03T12:00:00Z",
    "grace_period_hours": 24,
    "message": "구독이 만료되었습니다. 갱신해주세요."
}

# 서비스는 해당 테넌트 요청에 자동으로 차단 응답
```

### 5.3 보안 감사 로그 (서비스 → 마켓)

```python
# 의심스러운 활동 감지 시 자동 보고
POST /api/v1/audit/alerts

{
    "service_id": "keli_tutor",
    "alert_type": "cross_tenant_access_attempt",
    "severity": "high",
    "details": {
        "source_tenant": "hallym",
        "target_tenant": "korea",
        "endpoint": "/api/courses/123",
        "ip_address": "123.45.67.89"
    },
    "timestamp": "2026-01-03T12:00:00Z"
}
```

---

## 6. 구현 로드맵

### Phase 1: 핵심 SDK (2주)

- [ ] ServiceMarketFramework 기본 클래스
- [ ] config.yaml 파서
- [ ] TenantMiddleware (테넌트 식별)
- [ ] DatabaseRouter (테넌트별 DB 연결)
- [ ] MarketplaceClient (마켓 API 연동)

### Phase 2: 기존 서비스 마이그레이션 (2주)

- [ ] llm_chatbot에 mt_paas 적용
- [ ] advisor에 mt_paas 적용
- [ ] 기존 tenant_manager.py 제거

### Phase 3: Control Plane (1주)

- [ ] Heartbeat 자동 보고
- [ ] Kill-Switch 수신/처리
- [ ] 보안 감사 로그

### Phase 4: keli_tutor 연동 (2주)

- [ ] keli_tutor에 mt_paas 적용
- [ ] Docker-Per-Tenant 템플릿 표준화
- [ ] service_market 프로비저닝 연동

### Phase 5: 문서화 및 외부 공개 (1주)

- [ ] 서비스 업체용 개발 가이드
- [ ] API 문서
- [ ] 예제 프로젝트

---

## 7. 파일 구조 (최종)

```
~/workspace/multi_tenant_paas/
├── README.md
├── pyproject.toml
├── mt_paas_config.example.yaml      # 설정 파일 예시
│
├── docs/
│   ├── FRAMEWORK_DESIGN.md          # 본 문서
│   ├── CONSULTING_REQUEST.md        # 컨설팅 요청서
│   ├── DEVELOPER_GUIDE.md           # 서비스 업체용 가이드
│   └── API_REFERENCE.md             # API 문서
│
├── mt_paas/
│   ├── __init__.py
│   ├── framework.py                 # ServiceMarketFramework
│   │
│   ├── core/
│   │   ├── manager.py               # TenantManager
│   │   ├── models.py                # Tenant, Subscription
│   │   ├── database.py              # DatabaseRouter
│   │   └── config.py                # ConfigLoader
│   │
│   ├── middleware/
│   │   ├── tenant.py                # TenantMiddleware
│   │   ├── auth.py                  # AuthMiddleware
│   │   └── subscription.py          # SubscriptionMiddleware
│   │
│   ├── integrations/
│   │   ├── marketplace.py           # MarketplaceClient
│   │   └── activity_log.py          # ActivityLogger
│   │
│   ├── control/
│   │   ├── heartbeat.py             # HeartbeatService
│   │   ├── kill_switch.py           # KillSwitchHandler
│   │   └── audit.py                 # AuditLogger
│   │
│   └── templates/
│       ├── docker-compose.template.yml
│       └── .env.template
│
├── examples/
│   ├── basic_service/               # 기본 사용 예제
│   └── keli_tutor_integration/      # keli_tutor 연동 예제
│
└── tests/
    ├── test_framework.py
    ├── test_middleware.py
    └── test_marketplace.py
```

---

## 8. 다음 단계

config.yaml 규격이 확정되면:

1. **ConfigLoader 구현** - YAML 파싱 및 환경별 오버라이드
2. **ServiceMarketFramework 구현** - 메인 진입점
3. **TenantMiddleware 구현** - 테넌트 식별 로직

**진행할까요?**
