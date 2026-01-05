# Multi-Tenant PaaS 설계 컨설팅 요청서 (v2)

> LTI 스타일 표준 인터페이스 기반 설계 검토 요청

**작성일**: 2026-01-03
**버전**: 2.0
**변경사항**: 프레임워크 방식 → LTI 스타일 표준 API 방식으로 전환

---

## 1. 설계 방향 변경

### 1.1 이전 방식 (프레임워크)

```
서비스 업체가 할 일:
1. pip install mt_paas
2. 코드에 프레임워크 통합
3. config.yaml 작성
4. 프레임워크 API 학습 및 적용

문제점:
- 서비스마다 프레임워크 버전 관리 필요
- 프레임워크 업데이트 시 모든 서비스 재배포
- 서비스 업체의 학습 부담
```

### 1.2 새로운 방식 (LTI 스타일)

```
서비스 업체가 할 일:
1. manifest.yaml 작성
2. 표준 API 4~5개 구현
3. Service Market에 등록
4. 끝! (자동 연동)

장점:
- 서비스는 비즈니스 로직만 집중
- 마켓이 중앙에서 정책 제어
- 표준만 맞추면 자동으로 붙음
```

---

## 2. LTI 스타일이란?

### 2.1 LTI (Learning Tools Interoperability) 개념

```
┌─────────────────┐         ┌─────────────────┐
│      LMS        │         │   외부 도구      │
│  (Canvas 등)    │ ──────▶ │  (Kahoot 등)    │
│                 │  표준    │                 │
│  "이 규격 맞춰" │  API    │  "네, 맞췄어요" │
└─────────────────┘         └─────────────────┘

LMS가 외부 도구를 "플러그 앤 플레이"로 연동
→ 표준만 맞추면 자동으로 붙음
```

### 2.2 우리 시스템에 적용

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Market                            │
│                                                              │
│  "이 표준 API 구현하면 자동으로 연동해줄게"                    │
│                                                              │
│  • 서비스 등록: manifest.yaml 검증                           │
│  • 테넌트 생성: /mt/tenant/activate 호출                     │
│  • 구독 만료: /mt/tenant/deactivate 호출                     │
│  • 상태 확인: /mt/health 주기적 호출                         │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ keli_tutor  │      │ llm_chatbot │      │  새 서비스   │
│             │      │             │      │             │
│ 표준 API    │      │ 표준 API    │      │ 표준 API    │
│ 구현        │      │ 구현        │      │ 구현        │
└─────────────┘      └─────────────┘      └─────────────┘

서비스는 표준 API만 구현하면 마켓이 알아서 제어
```

---

## 3. 표준 인터페이스 규격 (초안)

### 3.1 manifest.yaml (서비스 명세서)

서비스가 마켓에 제출하는 명세서

```yaml
# manifest.yaml
version: "1.0"

# 서비스 기본 정보
service:
  id: "keli_tutor"
  name: "KELI TUTOR"
  description: "AI 기반 학습 튜터"
  version: "1.0.0"
  vendor: "K-University AI Lab"

# 서비스 접근 정보
endpoints:
  base_url: "https://keli.k-university.ai"

  # 필수 API (마켓이 호출)
  health: "/mt/health"
  tenant_activate: "/mt/tenant/{tenant_id}/activate"
  tenant_deactivate: "/mt/tenant/{tenant_id}/deactivate"
  tenant_status: "/mt/tenant/{tenant_id}/status"

  # 선택 API
  usage_report: "/mt/tenant/{tenant_id}/usage"

  # 사용자 접근 URL
  user_access: "/app/{tenant_id}"

# 인증 방식
auth:
  type: "api_key"  # api_key, oauth2, jwt
  header: "X-Market-API-Key"

# 지원하는 격리 수준
isolation:
  supported:
    - "DATABASE_PER_TENANT"
    - "DOCKER_PER_TENANT"
  default: "DATABASE_PER_TENANT"

# 요금제별 기능
features:
  basic:
    - "ai_chat"
    - "file_upload"
  standard:
    - "ai_chat"
    - "file_upload"
    - "rag"
    - "discussion"
  premium:
    - "ai_chat"
    - "file_upload"
    - "rag"
    - "discussion"
    - "quiz"
    - "api_integration"

# 필요 리소스 (프로비저닝 참고용)
resources:
  min_memory: "2GB"
  min_cpu: "1 core"
  storage: "10GB per tenant"
```

### 3.2 표준 API 규격

서비스가 구현해야 하는 API

#### 3.2.1 헬스체크 (필수)

```
GET /mt/health

Response 200:
{
  "status": "healthy",           // healthy, degraded, unhealthy
  "version": "1.0.0",
  "timestamp": "2026-01-03T12:00:00Z"
}
```

#### 3.2.2 테넌트 활성화 (필수)

```
POST /mt/tenant/{tenant_id}/activate
Headers:
  X-Market-API-Key: {api_key}

Request:
{
  "tenant_id": "hallym_univ",
  "tenant_name": "한림대학교",
  "plan": "premium",
  "features": ["ai_chat", "rag", "quiz"],
  "config": {
    "max_users": 500,
    "storage_limit_gb": 100
  },
  "admin": {
    "email": "admin@hallym.ac.kr",
    "name": "홍길동"
  }
}

Response 200:
{
  "status": "activated",
  "tenant_id": "hallym_univ",
  "access_url": "https://hallym.keli.k-university.ai",
  "admin_credentials": {
    "temp_password": "..."   // 또는 이메일 발송
  }
}

Response 409 (이미 존재):
{
  "error": "tenant_already_exists",
  "message": "Tenant hallym_univ already exists"
}
```

#### 3.2.3 테넌트 비활성화 (필수)

```
POST /mt/tenant/{tenant_id}/deactivate
Headers:
  X-Market-API-Key: {api_key}

Request:
{
  "reason": "subscription_expired",  // subscription_expired, admin_request, violation
  "preserve_data": true,             // 데이터 보존 여부
  "deactivate_at": "2026-01-03T12:00:00Z"  // 즉시 또는 예약
}

Response 200:
{
  "status": "deactivated",
  "tenant_id": "hallym_univ",
  "data_preserved": true,
  "reactivation_deadline": "2026-04-03T12:00:00Z"  // 데이터 보존 기한
}
```

#### 3.2.4 테넌트 상태 조회 (필수)

```
GET /mt/tenant/{tenant_id}/status
Headers:
  X-Market-API-Key: {api_key}

Response 200:
{
  "tenant_id": "hallym_univ",
  "status": "active",           // active, suspended, deactivated
  "plan": "premium",
  "created_at": "2026-01-01T00:00:00Z",
  "users": {
    "total": 150,
    "active_today": 45
  },
  "storage": {
    "used_gb": 25.5,
    "limit_gb": 100
  }
}
```

#### 3.2.5 사용량 보고 (선택)

```
GET /mt/tenant/{tenant_id}/usage?period=monthly
Headers:
  X-Market-API-Key: {api_key}

Response 200:
{
  "tenant_id": "hallym_univ",
  "period": "2026-01",
  "usage": {
    "api_calls": 15000,
    "ai_tokens": 500000,
    "storage_gb": 25.5,
    "active_users": 150
  }
}
```

---

## 4. 마켓 ↔ 서비스 연동 흐름

### 4.1 서비스 등록

```
┌──────────────┐                    ┌──────────────┐
│ 서비스 업체  │                    │Service Market│
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       │ 1. manifest.yaml 제출             │
       │──────────────────────────────────▶│
       │                                   │
       │                    2. manifest 검증
       │                    3. /mt/health 호출하여 확인
       │◀──────────────────────────────────│
       │                                   │
       │ 4. 검증 통과, 서비스 등록 완료     │
       │◀──────────────────────────────────│
       │                                   │
```

### 4.2 테넌트 생성 (학교 구독 시)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    학교      │    │Service Market│    │   서비스     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1. 서비스 구독    │                   │
       │──────────────────▶│                   │
       │                   │                   │
       │                   │ 2. /mt/tenant/activate
       │                   │──────────────────▶│
       │                   │                   │
       │                   │ 3. 테넌트 생성 완료
       │                   │◀──────────────────│
       │                   │                   │
       │ 4. 접속 정보 안내 │                   │
       │◀──────────────────│                   │
       │                   │                   │
```

### 4.3 구독 만료

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│Service Market│    │   서비스     │    │    학교      │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1. 만료 7일 전    │                   │
       │   알림 발송 ──────────────────────────▶
       │                   │                   │
       │ 2. 만료일 도래    │                   │
       │ /mt/tenant/deactivate                 │
       │──────────────────▶│                   │
       │                   │                   │
       │                   │ 3. 서비스 차단    │
       │                   │   (데이터 보존)   │
       │                   │                   │
       │ 4. 갱신 안내 ─────────────────────────▶
       │                   │                   │
```

### 4.4 상태 모니터링 (주기적)

```
┌──────────────┐                    ┌──────────────┐
│Service Market│                    │   서비스     │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       │ 매 1분마다 /mt/health 호출        │
       │──────────────────────────────────▶│
       │                                   │
       │ healthy / degraded / unhealthy    │
       │◀──────────────────────────────────│
       │                                   │
       │ unhealthy 3회 연속 시             │
       │ → 관리자 알림                     │
       │ → 대시보드에 상태 표시            │
       │                                   │
```

---

## 5. 규모 확장 시나리오

### 5.1 학교 100개, 서비스 20개 상황

```
┌─────────────────────────────────────────────────────────────┐
│                    Service Market                            │
│                                                              │
│  중앙 제어:                                                   │
│  • 100개 학교 × 20개 서비스 = 2,000개 테넌트 관리            │
│  • 정책 변경 시 마켓만 수정 (서비스 변경 없음)                │
│  • 일괄 모니터링, 일괄 과금                                   │
└─────────────────────────────────────────────────────────────┘
         │
         │ 표준 API로 제어
         ▼
┌─────────────────────────────────────────────────────────────┐
│  서비스들 (각자 독립 운영)                                    │
│                                                              │
│  • 표준 API만 구현하면 끝                                     │
│  • 마켓 정책 변경에 영향 없음                                 │
│  • 비즈니스 로직만 집중                                       │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 새 서비스 추가 시

```
1. 서비스 업체: manifest.yaml 작성 (30분)
2. 서비스 업체: 표준 API 4개 구현 (1~2일)
3. Service Market: manifest 검증, 자동 등록 (자동)
4. 학교: 마켓에서 서비스 구독 (클릭)
5. Service Market: /mt/tenant/activate 호출 (자동)
6. 서비스: 테넌트 생성 (자동)
7. 끝!

총 서비스 업체 작업: 1~2일
마켓 관리자 작업: 거의 없음
```

### 5.3 마켓 정책 변경 시

```
예: "모든 테넌트에 사용량 리포트 의무화"

프레임워크 방식:
- 20개 서비스 모두 업데이트 필요
- 각 서비스 재배포 필요
- 버전 호환성 문제 발생 가능

LTI 스타일:
- manifest에 usage_report 필수 여부 추가
- 마켓이 /mt/tenant/{id}/usage 호출 시작
- 서비스는 이미 구현되어 있거나, 구현 요청만 받음
- 서비스 재배포 불필요
```

---

## 6. 이전 방식과 비교

| 항목 | 프레임워크 방식 | LTI 스타일 |
|------|---------------|-----------|
| **서비스 업체 작업** | pip install + 코드 통합 | manifest + API 4개 |
| **학습 곡선** | 프레임워크 API 학습 필요 | API 스펙만 보면 됨 |
| **마켓 정책 변경** | 모든 서비스 업데이트 | 마켓만 수정 |
| **버전 관리** | 서비스별 프레임워크 버전 | 표준 API 버전만 관리 |
| **장애 격리** | 프레임워크 버그 → 전체 영향 | 서비스별 독립 |
| **확장성** | 서비스 증가 시 관리 복잡 | 표준만 지키면 자동 연동 |

---

## 7. 검토 요청 사항

### Q1. LTI 스타일 전환 적절성

프레임워크 방식에서 LTI 스타일로 전환하는 것이 적절한가요?

고려 사항:
- 현재 서비스: keli_tutor, llm_chatbot, advisor
- 향후 외부 서비스 업체 유입 예상
- 학교 수 증가 예상

### Q2. 표준 API 규격

제안된 표준 API 4개가 충분한가요?

```
필수:
1. GET  /mt/health
2. POST /mt/tenant/{id}/activate
3. POST /mt/tenant/{id}/deactivate
4. GET  /mt/tenant/{id}/status

선택:
5. GET  /mt/tenant/{id}/usage
```

추가로 필요한 API가 있을까요?

### Q3. manifest.yaml 규격

제안된 manifest 구조가 적절한가요?
추가하거나 제거할 항목이 있을까요?

### Q4. 기존 서비스 전환

기존 서비스(keli_tutor, llm_chatbot, advisor)를 LTI 스타일로 전환하는 방법:

| 옵션 | 설명 |
|------|------|
| A | 기존 서비스에 표준 API 추가 (래퍼) |
| B | 새 버전으로 재개발 |
| C | 신규 서비스부터 적용, 기존은 유지 |

어떤 방식이 적절할까요?

### Q5. 인증/보안

서비스 ↔ 마켓 간 인증 방식:

| 옵션 | 설명 |
|------|------|
| API Key | 단순, 관리 쉬움 |
| OAuth 2.0 | 표준, 토큰 갱신 |
| mTLS | 최고 보안, 복잡 |

어떤 방식을 권장하시나요?

### Q6. 데이터 격리

Docker-Per-Tenant vs Database-Per-Tenant를 서비스가 선택하도록 하는 것이 맞을까요?
아니면 마켓이 강제해야 할까요?

---

## 8. 현재 진행 상황

### 8.1 생성된 파일

```
~/workspace/multi_tenant_paas/
├── README.md
├── pyproject.toml
├── mt_paas_config.example.yaml      # 이전 방식 (프레임워크)
│
├── docs/
│   ├── CONSULTING_REQUEST.md        # v1 (프레임워크 방식)
│   ├── CONSULTING_REQUEST_v2.md     # v2 (LTI 스타일) ← 현재 문서
│   ├── DESIGN.md
│   └── FRAMEWORK_DESIGN.md          # 이전 방식 설계
│
└── mt_paas/
    └── (이전 방식 코드 - 전환 필요)
```

### 8.2 다음 단계 (검토 후)

1. manifest.yaml 규격 확정
2. 표준 API 규격 확정
3. Service Market 측 구현 (API 호출 로직)
4. 샘플 서비스 구현 (표준 API)
5. keli_tutor에 표준 API 래퍼 추가

---

## 9. 요약

| 번호 | 질문 | 옵션 |
|------|------|------|
| 1 | LTI 스타일 전환? | 적절 / 부적절 / 수정 필요 |
| 2 | 표준 API 규격? | 충분 / 추가 필요 / 수정 필요 |
| 3 | manifest 규격? | 적절 / 수정 필요 |
| 4 | 기존 서비스 전환? | A: 래퍼 추가 / B: 재개발 / C: 신규만 |
| 5 | 인증 방식? | API Key / OAuth / mTLS |
| 6 | 격리 수준 선택? | 서비스 선택 / 마켓 강제 |

---

**피드백 요청드립니다.**
