# 오픈소스화를 위한 연동 및 테스트 인터페이스 체크 결과

> 작성일: 2026-01-30
> 대상 프로젝트: multi_tenant_paas, advisor, llm_chatbot

---

## 1. 현재 상태 요약

| 항목 | multi_tenant_paas | advisor | llm_chatbot |
|------|-------------------|---------|-------------|
| **mt_paas 사용** | - | ❌ 자체구현 | ❌ 자체구현 |
| **Standard API** | ✅ 정의됨 | ❌ 커스텀 | ❌ 커스텀 |
| **테스트 도구** | ✅ 있음 | ❌ 없음 | ❌ 없음 |
| **문서화** | ✅ 양호 | ⚠️ 부분 | ⚠️ 부분 |

**핵심 문제**: advisor와 llm_chatbot이 mt_paas를 사용하지 않고 각자 멀티테넌트를 구현함

---

## 2. 주요 문제점

### 2.1 코드 중복

```
advisor/backend/database/tenant_manager.py    → 1,051줄
llm_chatbot/backend/database/tenant_manager.py → 1,119줄
-------------------------------------------------
거의 동일한 기능을 각각 구현 (2,170줄 중복)
```

### 2.2 인터페이스 불일치

| 기능 | mt_paas 표준 | advisor 현재 | llm_chatbot 현재 |
|------|-------------|-------------|-----------------|
| 테넌트 생성 | `POST /mt/tenant/{id}/activate` | `POST /api/marketplace/demo/request` | `POST /api/marketplace/demo/provision` |
| 테넌트 삭제 | `POST /mt/tenant/{id}/deactivate` | 커스텀 | `POST /api/marketplace/demo/deprovision` |
| 상태 조회 | `GET /mt/tenant/{id}/status` | 커스텀 | 커스텀 |
| 인증 헤더 | `X-Market-API-Key` | `X-Marketplace-Key` | `X-API-Key` |

### 2.3 테스트 도구 미활용

- mt_paas에 SDK/CLI/Simulator 있으나 실제 서비스에서 검증 안됨
- advisor/llm_chatbot에 연동 테스트 코드 없음

### 2.4 대시보드/관리 API 부재 (신규 발견)

**문제:** 테넌트 어드민에서 제공하는 기능이 Service Market 대시보드에서도 필요함

**Service Market이 기대하는 API:**
```
/api/tenant/webhook/auto-provision  → 테넌트 자동 생성 (있음)
/api/tenant/stats/{tenant_id}       → 사용 통계 (없음)
/api/tenant/users/{tenant_id}       → 사용자 목록 (없음)
/api/tenant/courses/{tenant_id}     → 코스 목록 (없음)
/api/tenant/discussions/{tenant_id} → 토론 목록 (없음)
```

**advisor/llm_chatbot의 테넌트 어드민 기능 (Service Market에서 접근 필요):**

| 기능 | advisor | llm_chatbot | Service Market 필요 |
|------|---------|-------------|-------------------|
| 대시보드 통계 | `/admin/dashboard` | `/admin/dashboard` | ✅ 필요 |
| 사용자 목록 | `/admin/users` | `/admin/users` | ✅ 필요 |
| 사용자 생성 | ❌ | `/admin/users` POST | ✅ 필요 |
| 비용 분석 | `/admin/dashboard/costs` | `/admin/dashboard/costs` | ✅ 필요 |
| 사용 패턴 | `/admin/dashboard/usage-patterns` | 동일 | ⚠️ 선택 |
| 사용 한도 | `/admin/limits` | `/admin/limits` | ✅ 필요 |

**현재 mt_paas Standard API 범위:**
```
현재 정의된 API (테넌트 생명주기만)
├── GET  /mt/health                     ✅
├── POST /mt/tenant/{id}/activate       ✅
├── POST /mt/tenant/{id}/deactivate     ✅
├── GET  /mt/tenant/{id}/status         ✅
└── GET  /mt/tenant/{id}/usage          ✅

누락된 API (대시보드/관리 기능)
├── GET  /mt/tenant/{id}/stats          ❌ 필요
├── GET  /mt/tenant/{id}/stats/costs    ❌ 필요
├── GET  /mt/tenant/{id}/users          ❌ 필요
├── POST /mt/tenant/{id}/users          ❌ 필요
├── GET  /mt/tenant/{id}/resources      ❌ 필요
└── GET  /mt/tenant/{id}/settings       ❌ 필요
```

---

## 3. 목표 아키텍처

### 3.1 확장된 Standard API v2

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Service Market                               │
│                              │                                       │
│                    Standard API v2 (확장)                            │
│                   (X-Market-API-Key 헤더)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  [생명주기 관리] - 기존                                               │
│  ├── GET  /mt/health                    → 상태 체크                  │
│  ├── POST /mt/tenant/{id}/activate      → 테넌트 생성                │
│  ├── POST /mt/tenant/{id}/deactivate    → 테넌트 삭제                │
│  ├── GET  /mt/tenant/{id}/status        → 상태 조회                  │
│  └── GET  /mt/tenant/{id}/usage         → 사용량 조회                │
│                                                                      │
│  [대시보드 API] - 신규                                                │
│  ├── GET  /mt/tenant/{id}/stats         → 대시보드 통계              │
│  ├── GET  /mt/tenant/{id}/stats/costs   → 비용 분석                  │
│  └── GET  /mt/tenant/{id}/stats/top-users → 활성 사용자              │
│                                                                      │
│  [사용자 관리 API] - 신규                                             │
│  ├── GET  /mt/tenant/{id}/users         → 사용자 목록                │
│  ├── POST /mt/tenant/{id}/users         → 사용자 생성                │
│  ├── PUT  /mt/tenant/{id}/users/{uid}   → 사용자 수정                │
│  └── DELETE /mt/tenant/{id}/users/{uid} → 사용자 삭제                │
│                                                                      │
│  [리소스/설정 API] - 신규                                             │
│  ├── GET  /mt/tenant/{id}/resources     → 리소스 목록 (코스,토론 등)  │
│  ├── GET  /mt/tenant/{id}/settings      → 테넌트 설정                │
│  └── PUT  /mt/tenant/{id}/settings      → 설정 변경                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
          advisor       llm_chatbot      기타 서비스
       (mt_paas 사용)   (mt_paas 사용)   (mt_paas 사용)
```

### 3.2 Service Market 호환 Alias (기존 경로 지원)

```
Service Market 기존 경로              →  mt_paas 표준 경로
───────────────────────────────────────────────────────────────
/api/tenant/webhook/auto-provision   → POST /mt/tenant/{id}/activate
/api/tenant/stats/{id}               → GET  /mt/tenant/{id}/stats
/api/tenant/users/{id}               → GET  /mt/tenant/{id}/users
/api/tenant/courses/{id}             → GET  /mt/tenant/{id}/resources?type=course
/api/tenant/discussions/{id}         → GET  /mt/tenant/{id}/resources?type=discussion
```

### 3.3 인증 체계 통일

```
┌─────────────────┐     X-Market-API-Key     ┌─────────────────┐
│  Service Market │ ──────────────────────→  │  서비스          │
│  (대시보드)      │                          │  (advisor 등)    │
│                 │  ←────────────────────── │                 │
│                 │     JSON Response        │                 │
└─────────────────┘                          └─────────────────┘
```

---

## 4. 서비스별 리팩토링 가이드

### 4.1 advisor 리팩토링 (예상 11-16일)

**변경 전 (커스텀):**
```python
from database.tenant_manager import onboard_tenant, get_tenant_by_api_key
```

**변경 후 (mt_paas 사용):**
```python
from mt_paas import setup_multi_tenant
from mt_paas.standard_api import StandardAPIHandler, create_standard_router

class AdvisorHandler(StandardAPIHandler):
    async def activate_tenant(self, request): ...
    async def deactivate_tenant(self, tenant_id, request): ...
    async def get_tenant_status(self, tenant_id): ...
    async def get_tenant_usage(self, tenant_id, period): ...
```

**수정 필요 파일:**

| 파일 | 크기 | 작업 내용 |
|------|------|----------|
| `database/tenant_manager.py` | 1,051줄 | mt_paas.core로 대체 |
| `database/multi_tenant.py` | 18KB | mt_paas.database로 대체 |
| `core/middleware/tenant.py` | 226줄 | mt_paas 미들웨어 사용 |
| `routers/marketplace.py` | 26KB | StandardAPIHandler 구현 |
| `routers/admin.py` | 38KB | 테넌트 관련 부분 수정 |
| `routers/super_admin.py` | 47KB | 테넌트 관련 부분 수정 |
| `routers/auth.py` | 9KB | 테넌트 컨텍스트 수정 |
| `config.py` | - | mt_paas 설정 통합 |
| `server.py` | - | 미들웨어 등록 변경 |
| `docker-compose.yml` | - | 환경변수 업데이트 |

### 4.2 llm_chatbot 리팩토링 (예상 8-12일)

**수정 필요 파일:**

| 파일 | 크기 | 작업 내용 |
|------|------|----------|
| `database/tenant_manager.py` | 1,119줄 | mt_paas.core로 대체 |
| `database/multi_tenant.py` | 525줄 | mt_paas.database로 대체 |
| `core/middleware/tenant.py` | 227줄 | mt_paas 미들웨어 사용 |
| `routers/marketplace.py` | 1,140줄 | StandardAPIHandler 구현 |
| `routers/tenant_webhook.py` | 46줄 | 표준 라우터 사용 |
| `server.py` | 351줄 | 미들웨어 등록 변경 |

---

## 5. 테스트 도구 통합

### 5.1 mt_paas 테스트 SDK 활용

```bash
# CLI로 서비스 검증
cd multi_tenant_paas/sandbox/sdk
python cli.py test --target http://advisor:8000 --key $API_KEY
```

### 5.2 예상 테스트 결과

```
╔══════════════════════════════════════════════════╗
║  Service Market Integration Test Report          ║
╠══════════════════════════════════════════════════╣
║  ✅ Health Check          PASS (45ms)            ║
║  ✅ Tenant Activation     PASS (234ms)           ║
║  ✅ Tenant Status         PASS (89ms)            ║
║  ✅ API Key Validation    PASS (12ms)            ║
║  ✅ Response Format       PASS                   ║
╠══════════════════════════════════════════════════╣
║  Score: 5/5 (100%)                               ║
╚══════════════════════════════════════════════════╝
```

### 5.3 테스트 시나리오

| 테스트 | 설명 | 검증 항목 |
|--------|------|----------|
| Health Check | 서비스 가용성 | 응답 코드, 응답 시간 |
| Webhook Basic | 표준 페이로드 처리 | 필수 필드, 형식 |
| API Key Validation | 보안 검증 | 401 응답 |
| Response Format | Pydantic 스키마 검증 | 타입, 필드 |
| Tenant Reuse | 이메일 기반 테넌트 재사용 | 중복 방지 |

---

## 6. 오픈소스 준비 체크리스트

### 6.1 mt_paas 라이브러리

| 항목 | 상태 | 비고 |
|------|------|------|
| Standard API 정의 | ✅ 완료 | handler.py, models.py |
| 테스트 SDK | ✅ 완료 | sandbox/sdk/ |
| 샘플 서비스 | ✅ 완료 | sandbox/sample_service/ |
| README 문서 | ✅ 완료 | README.md |
| 퀵스타트 가이드 | ✅ 완료 | AI_SERVICE_QUICKSTART.md |
| CHANGELOG | ❌ 필요 | 버전 변경 이력 |
| CONTRIBUTING | ❌ 필요 | 기여 가이드 |
| CI/CD | ❌ 필요 | GitHub Actions |
| PyPI 배포 | ❌ 필요 | pip install mt-paas |
| 라이선스 | ✅ 완료 | MIT |

### 6.2 advisor / llm_chatbot 서비스

| 항목 | advisor | llm_chatbot |
|------|---------|-------------|
| mt_paas 연동 | ❌ 리팩토링 필요 | ❌ 리팩토링 필요 |
| Standard API 준수 | ❌ | ❌ |
| 연동 테스트 코드 | ❌ | ❌ |
| 설치 문서 | ⚠️ 부분 | ⚠️ 부분 |
| Docker Compose | ✅ | ✅ |
| 환경변수 문서 | ⚠️ 부분 | ⚠️ 부분 |

---

## 7. 권장 작업 순서

### Phase 1: mt_paas 보완 (1주)

```
├── CHANGELOG.md 작성
├── CONTRIBUTING.md 작성
├── GitHub Actions CI/CD 설정
├── PyPI 배포 준비
└── API 문서 (OpenAPI/Swagger)
```

### Phase 2: llm_chatbot 리팩토링 (2주)

> llm_chatbot을 먼저 진행 (구조가 더 단순)

```
├── mt_paas 의존성 추가
├── StandardAPIHandler 구현
├── tenant_manager.py 교체
├── middleware 교체
└── 연동 테스트 통과
```

### Phase 3: advisor 리팩토링 (2-3주)

```
├── mt_paas 의존성 추가
├── StandardAPIHandler 구현
├── tenant_manager.py 교체
├── middleware 교체
└── 연동 테스트 통과
```

### Phase 4: 통합 테스트 및 문서화 (1주)

```
├── 두 서비스 동시 테스트
├── 설치/운영 가이드 작성
├── 트러블슈팅 가이드
└── GitHub 공개 준비
```

---

## 8. 예상 일정

| 단계 | 작업 | 예상 기간 |
|------|------|----------|
| Phase 1 | mt_paas 보완 | 1주 |
| Phase 2 | llm_chatbot 리팩토링 | 2주 |
| Phase 3 | advisor 리팩토링 | 2-3주 |
| Phase 4 | 통합 테스트/문서화 | 1주 |
| **총계** | | **6-7주** |

---

## 9. 결론

### 현재 상태

**오픈소스화 준비 불가** - 각 서비스가 자체 멀티테넌트 구현을 사용하여 인터페이스가 불일치함

### 주요 문제 3가지

1. **코드 중복**: tenant_manager.py가 각 서비스에 중복 구현 (2,170줄)
2. **인터페이스 불일치**: 프로비저닝 API 경로, 인증 헤더가 모두 다름
3. **대시보드 API 부재**: Service Market이 테넌트 통계/사용자 관리를 할 수 없음

### 해결책

1. **mt_paas Standard API v2 확장**
   - 기존 생명주기 API 유지
   - 대시보드/통계 API 추가 (`/mt/tenant/{id}/stats`)
   - 사용자 관리 API 추가 (`/mt/tenant/{id}/users`)
   - 리소스/설정 API 추가
   - → 상세 내용: [STANDARD_API_EXTENSION_PLAN.md](./STANDARD_API_EXTENSION_PLAN.md)

2. **advisor, llm_chatbot 리팩토링**
   - `StandardAPIHandler` 상속하여 확장된 메서드 구현
   - 기존 admin.py 로직을 핸들러로 이동
   - 테스트 SDK로 연동 검증

3. **Service Market 업데이트**
   - 표준 API 경로로 호출 변경
   - 대시보드에서 테넌트별 통계/사용자 관리 UI 추가

### 기대 효과

| 항목 | 현재 | 변경 후 |
|------|------|---------|
| tenant_manager.py | 2,170줄 (중복) | 0줄 (mt_paas 사용) |
| marketplace.py | 27KB + 1.1KB | ~5KB (핸들러만) |
| 새 서비스 연동 | 2-3주 | 2-3일 |
| 인터페이스 | 서비스별 상이 | 표준화 |
| Service Market 대시보드 | 제한적 | 전체 기능 지원 |

---

## 10. 참고 자료

### 관련 문서

- [README.md](../README.md) - 프로젝트 개요
- [AI_SERVICE_QUICKSTART.md](./AI_SERVICE_QUICKSTART.md) - 빠른 시작 가이드
- [ADVISOR_MULTI_TENANT_GUIDE.md](./ADVISOR_MULTI_TENANT_GUIDE.md) - Advisor 연동 가이드
- [STANDARD_API_EXTENSION_PLAN.md](./STANDARD_API_EXTENSION_PLAN.md) - **Standard API 확장 계획** (신규)

### 핵심 파일 위치

**mt_paas:**
- `/home/aiedu/workspace/multi_tenant_paas/mt_paas/standard_api/handler.py`
- `/home/aiedu/workspace/multi_tenant_paas/mt_paas/standard_api/models.py`
- `/home/aiedu/workspace/multi_tenant_paas/sandbox/sdk/`

**advisor:**
- `/data/aiedu-workspace/advisor/backend/database/tenant_manager.py`
- `/data/aiedu-workspace/advisor/backend/routers/marketplace.py`

**llm_chatbot:**
- `/home/aiedu/workspace/llm_chatbot/backend/database/tenant_manager.py`
- `/home/aiedu/workspace/llm_chatbot/backend/routers/marketplace.py`
