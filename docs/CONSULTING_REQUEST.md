# Multi-Tenant PaaS 도입 검토 요청서

> 멀티테넌트 공통 플랫폼 구축 필요성에 대한 컨설팅 요청

**작성일**: 2026-01-03
**작성자**: 개발팀
**검토 요청**: 아키텍처 방향성 및 도입 필요성

---

## 1. 현재 상황

### 1.1 운영 중인 서비스 현황

| 서비스 | 용도 | 멀티테넌트 | 구현 방식 |
|--------|------|-----------|----------|
| **service_market** | 서비스 판매/관리 플랫폼 | - | 중앙 관리 시스템 |
| **keli_tutor** | AI 학습 튜터 | O | Docker-Per-Tenant |
| **llm_chatbot** | Multi-LLM 챗봇 | O | Database-Per-Tenant (자체 구현) |
| **advisor** | 학사정보 RAG 챗봇 | O | Database-Per-Tenant (llm_chatbot 복사) |
| **video_rag** | 비디오 Q&A | X | 단일 테넌트 |
| **dashboard_v2** | 관리 대시보드 | X | 단일 테넌트 |

### 1.2 현재 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    service_market (8505)                     │
│                                                              │
│  • 테넌트 생성/삭제 API                                       │
│  • 구독(요금제) 관리                                          │
│  • Docker 기반 프로비저닝                                     │
│  • 포트 할당 (10200~, 10300~, ...)                           │
└─────────────────────────────────────────────────────────────┘
         │                           │
         │ Docker 프로비저닝          │ (연동 없음)
         ▼                           ▼
┌─────────────────┐         ┌─────────────────────────────────┐
│   keli_tutor    │         │  llm_chatbot / advisor          │
│                 │         │                                  │
│ Docker-Per-     │         │  Database-Per-Tenant            │
│ Tenant          │         │  (각자 tenant_manager.py 보유)   │
│                 │         │                                  │
│ 테넌트 A: 10200 │         │  자체 멀티테넌트 구현             │
│ 테넌트 B: 10300 │         │  service_market과 별개 운영       │
│ 테넌트 C: 10400 │         │                                  │
└─────────────────┘         └─────────────────────────────────┘
```

### 1.3 각 방식의 특징

#### Docker-Per-Tenant (keli_tutor)

```
테넌트당 컨테이너 구성:
┌─────────────────────────────────────┐
│ 테넌트 A (hallym_univ)              │
├─────────────────────────────────────┤
│ • Frontend    (10200)               │
│ • Backend     (10201)               │
│ • PostgreSQL  (10202)               │
│ • Redis       (10203)               │
│ • ChromaDB    (10204)               │
│ • Celery Worker                     │
│ • Consumer                          │
└─────────────────────────────────────┘
× 테넌트 수 = 총 컨테이너 수
```

**장점**:
- 완전한 격리 (보안, 장애)
- 테넌트별 독립 배포/롤백 가능
- 테넌트별 리소스 제한 용이

**단점**:
- 리소스 오버헤드 큼 (테넌트당 7개 컨테이너)
- 포트 관리 복잡
- 전체 업데이트 시 모든 컨테이너 재배포 필요

#### Database-Per-Tenant (llm_chatbot, advisor)

```
단일 애플리케이션 인스턴스:
┌─────────────────────────────────────┐
│ llm_chatbot (Backend: 8600)         │
├─────────────────────────────────────┤
│ 요청 → 테넌트 식별 → 해당 DB 연결   │
│                                      │
│ Central DB: llm_chatbot_central      │
│ Tenant A DB: tenant_hallym           │
│ Tenant B DB: tenant_korea            │
│ Tenant C DB: tenant_snu              │
└─────────────────────────────────────┘
```

**장점**:
- 리소스 효율적 (단일 인스턴스)
- 배포 단순 (한 번에 전체 업데이트)
- 포트 관리 간단

**단점**:
- 코드 레벨 격리 (실수 시 데이터 혼입 위험)
- 장애 시 전체 테넌트 영향

---

## 2. 문제점

### 2.1 코드 중복

llm_chatbot과 advisor가 **동일한 멀티테넌트 코드**를 각각 보유:

```
llm_chatbot/backend/               advisor/backend/
├── database/                      ├── database/
│   ├── tenant_manager.py    ≈     │   ├── tenant_manager.py
│   └── multi_tenant.py      ≈     │   └── multi_tenant.py
├── core/middleware/               ├── core/middleware/
│   └── tenant.py            ≈     │   └── tenant.py
└── ...                            └── ...
```

**문제**:
- 버그 발견 시 두 곳 모두 수정 필요
- 기능 개선 시 복사-붙여넣기
- 버전 불일치 위험

### 2.2 신규 서비스 추가 시 부담

새로운 멀티테넌트 서비스를 만들려면:

1. llm_chatbot에서 tenant 관련 코드 복사
2. 프로젝트에 맞게 수정
3. 테스트
4. 유지보수 대상 추가

### 2.3 service_market과의 연동 부재

```
현재:
┌──────────────┐     ┌──────────────┐
│service_market│     │ llm_chatbot  │
│              │ ╳   │              │
│ 테넌트 관리   │     │ 자체 테넌트   │
└──────────────┘     └──────────────┘
     별개로 운영, 동기화 안 됨
```

- llm_chatbot의 테넌트와 service_market의 테넌트가 별도 관리
- 구독 상태, 사용량 등 통합 관리 어려움

### 2.4 keli_tutor 확장 시 고려사항

keli_tutor도 멀티테넌트로 서비스해야 하는 상황에서:

**현재 (Docker-Per-Tenant)**:
- service_market이 프로비저닝
- keli_tutor 자체에는 멀티테넌트 코드 없음
- 테넌트 10개 = 컨테이너 70개

**고려 필요**:
- 테넌트 수 증가 시 리소스 관리
- Database-Per-Tenant로 전환 여부
- 전환 시 mt_paas 활용 가능성

---

## 3. 제안: Multi-Tenant PaaS (mt_paas)

### 3.1 개념

```
┌─────────────────────────────────────────────────────────────┐
│                  multi_tenant_paas (공통 모듈)               │
│                                                              │
│  pip install로 각 서비스에서 import하여 사용                  │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    core     │  │ middleware  │  │integrations │         │
│  │             │  │             │  │             │         │
│  │ • Manager   │  │ • Tenant    │  │ • Market-   │         │
│  │ • Models    │  │   Identify  │  │   place     │         │
│  │ • Lifecycle │  │ • Auth      │  │   Client    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
         │                   │                   │
         ▼                   ▼                   ▼
   ┌──────────┐        ┌──────────┐        ┌──────────┐
   │keli_tutor│        │llm_chat- │        │ advisor  │
   │          │        │   bot    │        │          │
   │ import   │        │ import   │        │ import   │
   │ mt_paas  │        │ mt_paas  │        │ mt_paas  │
   └──────────┘        └──────────┘        └──────────┘
```

### 3.2 사용 예시

```python
# 각 서비스에서 (llm_chatbot, advisor, keli_tutor 등)
from mt_paas.core import TenantManager
from mt_paas.middleware import TenantMiddleware
from mt_paas.integrations import MarketplaceClient

# FastAPI 앱에 적용
app.add_middleware(TenantMiddleware, ...)

# 테넌트별 DB 세션
async with tenant_manager.get_session(tenant_id) as db:
    ...

# service_market과 동기화
await marketplace_client.sync_status(tenant_id, "active")
```

### 3.3 기대 효과

| 항목 | 현재 | mt_paas 도입 후 |
|------|------|----------------|
| 코드 중복 | llm_chatbot, advisor 각각 구현 | 공통 모듈 1개 |
| 신규 서비스 | 복사-붙여넣기 | pip install 후 import |
| 버그 수정 | 모든 서비스에 적용 | 공통 모듈 1곳만 수정 |
| service_market 연동 | 별개 운영 | 통합 가능 |

---

## 4. 검토 요청 사항

### Q1. 도입 필요성

mt_paas 공통 모듈을 만드는 것이 **실제로 도움이 될까요?**

고려 사항:
- 현재 멀티테넌트 서비스: 3개 (keli_tutor, llm_chatbot, advisor)
- 향후 추가 예정 서비스가 있는지?
- 현재 코드 중복으로 인한 실제 문제 발생 빈도?

### Q2. 적용 범위

어떤 서비스에 우선 적용해야 할까요?

| 옵션 | 설명 | 작업량 |
|------|------|--------|
| A | llm_chatbot + advisor만 | 중간 (기존 코드 교체) |
| B | keli_tutor 포함 전체 | 높음 (keli_tutor 수정 필요) |
| C | 신규 서비스부터 적용 | 낮음 (기존 코드 유지) |

### Q3. 멀티테넌트 방식 통일

keli_tutor를 Database-Per-Tenant로 전환해야 할까요?

| 옵션 | 방식 | 장점 | 단점 |
|------|------|------|------|
| 유지 | Docker-Per-Tenant | 완전 격리, 변경 없음 | 리소스 많이 필요 |
| 전환 | Database-Per-Tenant | 리소스 효율적 | 코드 수정 필요 |
| 하이브리드 | 둘 다 지원 | 유연함 | 복잡도 증가 |

### Q4. 우선순위

제한된 리소스에서 무엇을 먼저 해야 할까요?

1. mt_paas 개발 → 서비스 적용
2. service_market 기능 강화 (mt_paas 없이)
3. 현재 구조 유지, 필요할 때 재검토
4. 기타 의견

### Q5. ROI (투자 대비 효과)

mt_paas 개발에 투자하는 시간 대비 얻는 이점이 충분한가요?

**투자**:
- 공통 모듈 설계 및 구현: ?일
- 기존 서비스 마이그레이션: ?일
- 테스트 및 안정화: ?일

**이점**:
- 코드 중복 제거
- 신규 서비스 개발 속도 향상
- 유지보수 단순화

---

## 5. 현재 진행 상황

### 5.1 생성된 파일

```
~/workspace/multi_tenant_paas/
├── README.md                 # 프로젝트 개요
├── pyproject.toml           # 패키지 설정
├── docs/
│   ├── DESIGN.md            # 상세 설계 문서
│   └── CONSULTING_REQUEST.md # 본 문서
└── mt_paas/
    ├── __init__.py
    ├── setup.py
    └── core/
        ├── __init__.py
        └── models.py        # Tenant, Subscription 모델 (초안)
```

### 5.2 할당된 포트 범위

- **10100 ~ 10200**: mt_paas 테스트용 (예약)
- 기존 keli_tutor 테넌트: 10200~ (유지)

---

## 6. 결정 필요 사항 요약

| 번호 | 질문 | 옵션 |
|------|------|------|
| 1 | mt_paas 도입할 것인가? | 예 / 아니오 / 보류 |
| 2 | 어떤 서비스에 적용? | A: llm+advisor / B: 전체 / C: 신규만 |
| 3 | keli_tutor 방식 전환? | 유지 / 전환 / 하이브리드 |
| 4 | 우선순위? | 1~4 중 선택 |
| 5 | 진행 여부? | 진행 / 보류 / 재검토 |

---

## 7. 참고 문서

- [기존 개발자 가이드](../service_market/docs/developer-guide-complete.md)
- [테넌트 온보딩 프로세스](../service_market/docs/tenant-onboarding-process.md)
- [mt_paas 상세 설계](./DESIGN.md)

---

**피드백 요청드립니다.**
