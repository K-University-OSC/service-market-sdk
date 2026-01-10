# Multi-Tenant PaaS 서비스 연동 완전 가이드

> 서비스 개발자를 위한 Service Market 연동, 표준 API 구현, 데이터 격리 완전 가이드

**문서 버전**: 1.0
**최종 수정일**: 2026-01-03
**대상 독자**: 서비스 개발자, 운영 담당자

---

# 목차

## Part 0: 주요 비즈니스 플로우 (한눈에 보기)
0. [서비스 등록 플로우](#01-서비스-등록-플로우)
1. [테넌트 활성화 플로우](#02-테넌트-활성화-플로우)
2. [사용자 서비스 이용 플로우](#03-사용자-서비스-이용-플로우)
3. [데이터 조회 플로우](#04-데이터-조회-플로우)
4. [테넌트 비활성화 플로우](#05-테넌트-비활성화-플로우)

## Part 1: 시스템 이해
1. [시스템 개요](#1-시스템-개요)
2. [아키텍처 구조](#2-아키텍처-구조)
3. [역할별 접근 권한](#3-역할별-접근-권한)

## Part 2: 서비스 연동
4. [manifest.yaml 작성](#4-manifestyaml-작성)
5. [표준 API 구현](#5-표준-api-구현)
6. [Service Market 등록](#6-service-market-등록)

## Part 3: 데이터 관리
7. [대학별 데이터 격리](#7-대학별-데이터-격리)
8. [LRS 데이터 관리](#8-lrs-데이터-관리)
9. [분석 서비스 구현](#9-분석-서비스-구현)

## Part 4: 운영 가이드
10. [모니터링](#10-모니터링)
11. [트러블슈팅](#11-트러블슈팅)

## Part 5: 부록
12. [API 체크리스트](#12-api-체크리스트)
13. [코드 예시](#13-코드-예시)
14. [자주 묻는 질문](#14-자주-묻는-질문)

---

# Part 0: 주요 비즈니스 플로우 (한눈에 보기)

## 0.1 서비스 등록 플로우

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 서비스 업체  │    │Service Market│    │   서비스     │
│  (개발자)    │    │   (마켓)     │    │  (백엔드)    │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1. manifest.yaml  │                   │
       │    작성           │                   │
       │                   │                   │
       │ 2. 표준 API 구현  │                   │
       │    (9개 엔드포인트)│                   │
       │                   │                   │
       │ 3. 서비스 등록 요청                   │
       │   (manifest 제출) │                   │
       │──────────────────>│                   │
       │                   │                   │
       │                   │ 4. manifest 검증  │
       │                   │                   │
       │                   │ 5. GET /mt/health │
       │                   │──────────────────>│
       │                   │                   │
       │                   │ 6. 헬스체크 응답  │
       │                   │<──────────────────│
       │                   │                   │
       │                   │ 7. 서비스 등록    │
       │                   │    DB 저장        │
       │                   │                   │
       │                   │ 8. API 키 발급    │
       │                   │                   │
       │ 9. 등록 완료 알림 │                   │
       │   (API 키 전달)   │                   │
       │<──────────────────│                   │
       │                   │                   │
```

**서비스 등록 시 필요한 파일:**
```yaml
# manifest.yaml
version: "1.0"
service:
  id: "my_ai_service"
  name: "My AI Service"
  description: "AI 기반 학습 서비스"
  version: "1.0.0"
  vendor: "My Company"
  contact: "support@mycompany.com"

endpoints:
  base_url: "https://myservice.k-university.ai"
  health: "/mt/health"
  activate: "/mt/tenant/{tenant_id}/activate"
  deactivate: "/mt/tenant/{tenant_id}/deactivate"
  status: "/mt/tenant/{tenant_id}/status"
  usage: "/mt/tenant/{tenant_id}/usage"
  tenant_lrs: "/mt/tenant/{tenant_id}/lrs"
  tenant_analytics: "/mt/tenant/{tenant_id}/analytics"
  all_lrs: "/mt/tenants/lrs"
  all_analytics: "/mt/tenants/analytics"
  user_access: "/{tenant_id}"
```

**등록 완료 후 받는 정보:**
```json
{
  "service_id": "my_ai_service",
  "status": "registered",
  "api_key": "mk_live_abc123xyz456...",
  "registered_at": "2026-01-03T12:00:00Z",
  "dashboard_url": "https://market.k-university.ai/services/my_ai_service"
}
```

---

## 0.2 테넌트 활성화 플로우

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    대학교    │    │Service Market│    │   서비스     │    │  서비스 DB   │
│  (관리자)    │    │   (마켓)     │    │  (백엔드)    │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │ 1. 서비스 구독    │                   │                   │
       │   요청 (결제)     │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 2. 결제 확인      │                   │
       │                   │                   │                   │
       │                   │ 3. POST /mt/tenant/{id}/activate      │
       │                   │   {tenant_id, name, plan, features}   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 4. 테넌트용 DB 생성
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ 5. CREATE DATABASE
       │                   │                   │                   │    tenant_hallym
       │                   │                   │                   │
       │                   │                   │ 6. 테넌트용 LRS    │
       │                   │                   │    스키마 생성     │
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │                   │                   │ 7. 초기 설정      │
       │                   │                   │    저장            │
       │                   │                   │                   │
       │                   │ 8. 활성화 완료    │                   │
       │                   │   {access_url}    │                   │
       │                   │<──────────────────│                   │
       │                   │                   │                   │
       │ 9. 접속 정보 안내 │                   │                   │
       │   (URL, 안내서)   │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
```

**Market → 서비스로 전달되는 활성화 요청:**
```json
{
  "tenant_id": "hallym_univ",
  "tenant_name": "한림대학교",
  "plan": "premium",
  "features": ["ai_chat", "rag", "quiz", "discussion"],
  "config": {
    "max_users": 500,
    "storage_limit_gb": 100
  },
  "contact": {
    "email": "admin@hallym.ac.kr",
    "name": "김교수"
  }
}
```

**서비스 → Market으로 반환되는 응답:**
```json
{
  "success": true,
  "tenant_id": "hallym_univ",
  "access_url": "https://myservice.k-university.ai/hallym",
  "message": "Tenant activated successfully"
}
```

**서비스 내부에서 생성되는 리소스:**
```sql
-- 1. 테넌트 전용 데이터베이스
CREATE DATABASE tenant_hallym_univ;

-- 2. 테넌트 설정 테이블 (Central DB)
INSERT INTO tenants (id, name, plan, features, status, created_at)
VALUES ('hallym_univ', '한림대학교', 'premium',
        '["ai_chat","rag","quiz"]', 'active', NOW());

-- 3. 테넌트 DB에 필요한 테이블들
-- (tenant_hallym_univ 데이터베이스 내)
CREATE TABLE users (...);
CREATE TABLE lrs_statements (...);
CREATE TABLE chat_history (...);
CREATE TABLE analytics_data (...);
```

---

## 0.3 사용자 서비스 이용 플로우

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    사용자    │    │   대학 SSO   │    │   서비스     │    │  테넌트 DB   │
│   (학생)     │    │              │    │  (백엔드)    │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │ 1. 서비스 접속    │                   │                   │
       │   /hallym         │                   │                   │
       │──────────────────────────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 2. 테넌트 확인    │
       │                   │                   │    (hallym_univ)  │
       │                   │                   │                   │
       │ 3. 로그인 필요    │                   │                   │
       │   (대학 SSO 리다이렉트)               │                   │
       │<──────────────────────────────────────│                   │
       │                   │                   │                   │
       │ 4. 대학 로그인    │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │ 5. 인증 성공      │                   │                   │
       │   (사용자 정보)   │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
       │ 6. 서비스 토큰 요청                   │                   │
       │   (대학 토큰 포함)│                   │                   │
       │──────────────────────────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 7. 대학 토큰 검증 │
       │                   │                   │                   │
       │                   │                   │ 8. 사용자 생성/조회
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ 9. tenant_hallym_univ
       │                   │                   │                   │    .users INSERT/SELECT
       │                   │                   │                   │
       │                   │                   │ 10. 서비스 JWT 발급
       │                   │                   │                   │
       │ 11. 로그인 완료   │                   │                   │
       │    (서비스 이용)  │                   │                   │
       │<──────────────────────────────────────│                   │
       │                   │                   │                   │
       │ 12. 서비스 이용   │                   │                   │
       │    (AI 채팅 등)   │                   │                   │
       │──────────────────────────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 13. 활동 기록     │
       │                   │                   │    (LRS 저장)     │
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ 14. tenant_hallym_univ
       │                   │                   │                   │    .lrs_statements INSERT
       │                   │                   │                   │
```

**사용자 활동 시 저장되는 LRS 데이터:**
```json
{
  "id": "stmt_uuid_123",
  "actor": {
    "name": "홍길동",
    "account": {
      "name": "student001",
      "homePage": "https://hallym.ac.kr"
    }
  },
  "verb": {
    "id": "http://adlnet.gov/expapi/verbs/asked",
    "display": {"ko-KR": "질문함"}
  },
  "object": {
    "id": "https://myservice.k-university.ai/hallym/chat/session_123",
    "definition": {
      "name": {"ko-KR": "AI 튜터 대화"}
    }
  },
  "result": {
    "response": "미분의 정의가 무엇인가요?",
    "extensions": {
      "ai_response_quality": 4.5
    }
  },
  "timestamp": "2026-01-03T14:30:00Z",
  "context": {
    "extensions": {
      "tenant_id": "hallym_univ",
      "session_id": "session_123"
    }
  }
}
```

---

## 0.4 데이터 조회 플로우

### 0.4.1 대학 관리자가 자기 대학 데이터 조회

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  대학 관리자 │    │   서비스     │    │  테넌트 DB   │
│  (한림대)    │    │  (백엔드)    │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1. 분석 대시보드  │                   │
       │   접속            │                   │
       │──────────────────>│                   │
       │                   │                   │
       │                   │ 2. JWT 검증       │
       │                   │   (tenant_id:     │
       │                   │    hallym_univ)   │
       │                   │                   │
       │                   │ 3. 테넌트 DB 조회 │
       │                   │──────────────────>│
       │                   │                   │
       │                   │                   │ 4. tenant_hallym_univ
       │                   │                   │    에서만 조회
       │                   │                   │
       │                   │ 5. 분석 데이터    │
       │                   │<──────────────────│
       │                   │                   │
       │ 6. 대시보드 표시  │                   │
       │   (자기 대학만)   │                   │
       │<──────────────────│                   │
       │                   │                   │
```

### 0.4.2 Service Market이 전체 데이터 조회

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│Service Market│    │   서비스     │    │  Central DB  │
│   (마켓)     │    │  (백엔드)    │    │ + 테넌트 DBs │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       │ 1. GET /mt/tenants/analytics          │
       │   (전체 분석 요청)│                   │
       │──────────────────>│                   │
       │                   │                   │
       │                   │ 2. Market API Key │
       │                   │    검증           │
       │                   │                   │
       │                   │ 3. 모든 테넌트    │
       │                   │    목록 조회      │
       │                   │──────────────────>│
       │                   │                   │
       │                   │ 4. 각 테넌트 DB   │
       │                   │    분석 데이터 수집│
       │                   │──────────────────>│
       │                   │                   │
       │                   │                   │ 5. tenant_hallym
       │                   │                   │    tenant_korea
       │                   │                   │    tenant_snu
       │                   │                   │    ... 모두 조회
       │                   │                   │
       │                   │ 6. 통합 데이터    │
       │                   │<──────────────────│
       │                   │                   │
       │ 7. 전체 분석 결과 │                   │
       │   (모든 대학 포함)│                   │
       │<──────────────────│                   │
       │                   │                   │
```

**Market이 받는 전체 분석 데이터:**
```json
{
  "period": "2026-01",
  "overall_summary": {
    "total_tenants": 50,
    "total_users": 25000,
    "total_active_users": 18000,
    "avg_completion_rate": 0.68
  },
  "tenants": [
    {
      "tenant_id": "hallym_univ",
      "tenant_name": "한림대학교",
      "summary": {
        "total_users": 500,
        "active_users": 350,
        "completion_rate": 0.72
      }
    },
    {
      "tenant_id": "korea_univ",
      "tenant_name": "고려대학교",
      "summary": {
        "total_users": 800,
        "active_users": 620,
        "completion_rate": 0.75
      }
    }
    // ... 모든 대학
  ],
  "rankings": {
    "by_active_users": ["korea_univ", "snu", "hallym_univ"],
    "by_completion_rate": ["snu", "hallym_univ", "korea_univ"]
  }
}
```

---

## 0.5 테넌트 비활성화 플로우

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│Service Market│    │   서비스     │    │  Central DB  │    │  테넌트 DB   │
│   (마켓)     │    │  (백엔드)    │    │              │    │              │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │  === 구독 만료 감지 ===               │                   │
       │                   │                   │                   │
       │ 1. POST /mt/tenant/{id}/deactivate    │                   │
       │   {reason: "subscription_expired",    │                   │
       │    preserve_data: true}               │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 2. API Key 검증   │                   │
       │                   │                   │                   │
       │                   │ 3. 테넌트 상태    │                   │
       │                   │    업데이트       │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 4. UPDATE tenants
       │                   │                   │    SET status =
       │                   │                   │    'suspended'    │
       │                   │                   │                   │
       │                   │ 5. (데이터 보존)  │                   │
       │                   │    접근만 차단    │                   │
       │                   │──────────────────────────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ 6. 접근 권한만 제거
       │                   │                   │                   │    (데이터 유지)
       │                   │                   │                   │
       │ 7. 비활성화 완료  │                   │                   │
       │   {data_preserved:│                   │                   │
       │    true,          │                   │                   │
       │    retention_until│                   │                   │
       │    : "2026-04-03"}│                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
       │ === 데이터 보존 기간 만료 (90일 후) ===                   │
       │                   │                   │                   │
       │ 8. 완전 삭제 요청 │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 9. 테넌트 DB 삭제 │                   │
       │                   │──────────────────────────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ 10. DROP DATABASE
       │                   │                   │                   │     tenant_hallym_univ
       │                   │                   │                   │
       │                   │ 11. Central DB    │                   │
       │                   │     기록 삭제     │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 12. DELETE FROM   │
       │                   │                   │     tenants       │
       │                   │                   │                   │
       │ 13. 삭제 완료     │                   │                   │
       │<──────────────────│                   │                   │
       │                   │                   │                   │
```

**비활성화 요청 (Market → 서비스):**
```json
{
  "reason": "subscription_expired",
  "preserve_data": true
}
```

**비활성화 응답 (서비스 → Market):**
```json
{
  "success": true,
  "tenant_id": "hallym_univ",
  "status": "deactivated",
  "data_preserved": true,
  "data_retention_until": "2026-04-03T00:00:00Z"
}
```

**비활성화 시 처리 사항:**
```sql
-- 1. 테넌트 상태 변경 (Central DB)
UPDATE tenants
SET status = 'suspended',
    deactivated_at = NOW(),
    deactivation_reason = 'subscription_expired'
WHERE id = 'hallym_univ';

-- 2. 테넌트 DB는 유지 (데이터 보존)
-- tenant_hallym_univ 데이터베이스 접근만 차단

-- 3. 90일 후 완전 삭제
DROP DATABASE tenant_hallym_univ;
DELETE FROM tenants WHERE id = 'hallym_univ';
```

---

# Part 1: 시스템 이해

## 1. 시스템 개요

### 1.1 Multi-Tenant PaaS란?

Multi-Tenant PaaS는 Service Market과 AI 서비스들을 연결하는 **표준 인터페이스 규격**입니다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Service Market                                │
│                                                                      │
│   • 서비스 등록/관리                                                 │
│   • 테넌트(대학교) 구독 관리                                         │
│   • 모든 데이터 통합 조회                                            │
│   • 과금/결제 처리                                                   │
│                                                                      │
└─────────────────┬──────────────────────┬────────────────────────────┘
                  │                      │
                  │ 표준 API             │ 표준 API
                  ▼                      ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│      keli_tutor         │    │      llm_chatbot        │
│                         │    │                         │
│  대학별 격리 인프라:    │    │  대학별 격리 인프라:    │
│  - 한림대: DB_A, LRS_A  │    │  - 한림대: DB_A, LRS_A  │
│  - 고려대: DB_B, LRS_B  │    │  - 고려대: DB_B, LRS_B  │
│                         │    │                         │
│  분석 서비스 제공       │    │  분석 서비스 제공       │
└───────────┬─────────────┘    └───────────┬─────────────┘
            │                              │
            ▼                              ▼
      [한림대, 고려대, ...]          [한림대, 고려대, ...]
```

### 1.2 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **데이터 격리** | 대학별로 완전히 분리된 DB/LRS 운영 |
| **표준 인터페이스** | 9개의 표준 API만 구현하면 연동 완료 |
| **자율적 인프라** | 서비스 업체가 인프라 자유롭게 선택 |
| **분석 서비스** | 대학별 분석 + Market 전체 분석 |

### 1.3 주요 구성 요소

| 구성 요소 | 역할 | 담당자 |
|----------|------|--------|
| Service Market | 서비스/테넌트/구독 관리 | Market 운영팀 |
| AI 서비스 | 실제 서비스 제공 | 서비스 업체 |
| 테넌트 DB | 대학별 격리된 데이터 | 서비스 업체 |
| LRS | 학습 활동 기록 | 서비스 업체 |
| 분석 엔진 | 데이터 분석/리포트 | 서비스 업체 |

---

## 2. 아키텍처 구조

### 2.1 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Service Market                                  │
│                                                                          │
│   ┌────────────────────────────────────────────────────────┐            │
│   │              통합 대시보드 / 분석                        │            │
│   │   • 전체 서비스 사용량 현황                              │            │
│   │   • 전체 대학 학습 활동 분석                             │            │
│   │   • 서비스별/대학별 비교 분석                            │            │
│   └────────────────────────────────────────────────────────┘            │
│                                                                          │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│   │  서비스   │  │  테넌트   │  │   구독    │  │   과금    │               │
│   │  Registry │  │  Manager │  │  Manager │  │  System  │               │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
        │                │                │
        │                │                │
        ▼                ▼                ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   서비스 A    │ │   서비스 B    │ │   서비스 C    │
│               │ │               │ │               │
│ ┌───────────┐ │ │ ┌───────────┐ │ │ ┌───────────┐ │
│ │ Central   │ │ │ │ Central   │ │ │ │ Central   │ │
│ │ DB        │ │ │ │ DB        │ │ │ │ DB        │ │
│ └───────────┘ │ │ └───────────┘ │ │ └───────────┘ │
│               │ │               │ │               │
│ ┌───────────┐ │ │ ┌───────────┐ │ │ ┌───────────┐ │
│ │ 테넌트 DB │ │ │ │ 테넌트 DB │ │ │ │ 테넌트 DB │ │
│ │ ┌───────┐ │ │ │ │ ┌───────┐ │ │ │ │ ┌───────┐ │ │
│ │ │한림대 │ │ │ │ │ │한림대 │ │ │ │ │ │한림대 │ │ │
│ │ ├───────┤ │ │ │ │ ├───────┤ │ │ │ │ ├───────┤ │ │
│ │ │고려대 │ │ │ │ │ │고려대 │ │ │ │ │ │고려대 │ │ │
│ │ ├───────┤ │ │ │ │ ├───────┤ │ │ │ │ ├───────┤ │ │
│ │ │서울대 │ │ │ │ │ │서울대 │ │ │ │ │ │서울대 │ │ │
│ │ └───────┘ │ │ │ │ └───────┘ │ │ │ │ └───────┘ │ │
│ └───────────┘ │ │ └───────────┘ │ │ └───────────┘ │
└───────────────┘ └───────────────┘ └───────────────┘
```

### 2.2 데이터베이스 구조

```
서비스 업체 인프라:

┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL Server                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐   Central DB (서비스 전체 관리용)       │
│  │ central_db      │   - tenants 테이블                     │
│  │                 │   - 서비스 설정                         │
│  └─────────────────┘                                        │
│                                                              │
│  ┌─────────────────┐   테넌트별 격리 DB                      │
│  │tenant_hallym_univ   - users                              │
│  │                 │   - lrs_statements                     │
│  │                 │   - chat_history                       │
│  │                 │   - files                              │
│  │                 │   - analytics                          │
│  └─────────────────┘                                        │
│                                                              │
│  ┌─────────────────┐                                        │
│  │tenant_korea_univ│   (동일 구조)                          │
│  └─────────────────┘                                        │
│                                                              │
│  ┌─────────────────┐                                        │
│  │tenant_snu       │   (동일 구조)                          │
│  └─────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Central DB 스키마

```sql
-- 테넌트 관리 테이블
CREATE TABLE tenants (
    id VARCHAR(50) PRIMARY KEY,           -- 'hallym_univ'
    name VARCHAR(200) NOT NULL,           -- '한림대학교'
    status VARCHAR(20) DEFAULT 'pending', -- pending/active/suspended/deleted
    plan VARCHAR(20) NOT NULL,            -- basic/standard/premium
    features JSONB DEFAULT '[]',          -- ["ai_chat", "rag", "quiz"]
    config JSONB DEFAULT '{}',            -- 추가 설정
    db_name VARCHAR(100),                 -- 'tenant_hallym_univ'
    contact_email VARCHAR(200),
    contact_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP
);

-- 사용량 집계 테이블 (분석용)
CREATE TABLE usage_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(50) REFERENCES tenants(id),
    period VARCHAR(7),                    -- '2026-01'
    active_users INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    api_calls INTEGER DEFAULT 0,
    ai_tokens BIGINT DEFAULT 0,
    storage_mb INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2.4 테넌트 DB 스키마

```sql
-- 각 테넌트 DB에 생성되는 테이블들

-- 사용자 테이블
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(100),             -- 대학 SSO ID
    name VARCHAR(100),
    email VARCHAR(200),
    role VARCHAR(20) DEFAULT 'student',   -- student/instructor/admin
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

-- LRS 테이블 (xAPI 표준)
CREATE TABLE lrs_statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement_id VARCHAR(100) UNIQUE,     -- xAPI statement ID
    actor JSONB NOT NULL,                 -- {"name": "홍길동", ...}
    verb JSONB NOT NULL,                  -- {"id": "http://...", ...}
    object JSONB NOT NULL,                -- 학습 객체
    result JSONB,                         -- 결과
    context JSONB,                        -- 컨텍스트
    timestamp TIMESTAMP DEFAULT NOW(),
    stored TIMESTAMP DEFAULT NOW()
);

-- 채팅 이력
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(100),
    role VARCHAR(20),                     -- user/assistant
    content TEXT,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 분석 데이터 (사전 계산된)
CREATE TABLE analytics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    active_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    avg_session_duration INTEGER,         -- 초
    total_questions INTEGER DEFAULT 0,
    total_ai_tokens BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_lrs_timestamp ON lrs_statements(timestamp);
CREATE INDEX idx_lrs_actor ON lrs_statements USING gin(actor);
CREATE INDEX idx_chat_user ON chat_history(user_id);
CREATE INDEX idx_chat_session ON chat_history(session_id);
CREATE INDEX idx_analytics_date ON analytics_daily(date);
```

---

## 3. 역할별 접근 권한

### 3.1 접근 권한 매트릭스

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           접근 권한 구조                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Service Market (슈퍼 관리자)                                           │
│   └─ 모든 서비스의 모든 대학 데이터 접근 가능                            │
│      • GET /mt/tenants/lrs ✅                                           │
│      • GET /mt/tenants/analytics ✅                                     │
│      • GET /mt/tenant/{any}/lrs ✅                                      │
│      • GET /mt/tenant/{any}/analytics ✅                                │
│                                                                          │
│   서비스 업체 (서비스 관리자)                                            │
│   └─ 자기 서비스의 모든 대학 데이터 접근 가능                            │
│      • GET /mt/tenant/{any}/lrs ✅                                      │
│      • GET /mt/tenant/{any}/analytics ✅                                │
│      • GET /mt/tenants/lrs ❌ (Market 전용)                             │
│      • GET /mt/tenants/analytics ❌ (Market 전용)                       │
│                                                                          │
│   대학교 (테넌트 관리자)                                                  │
│   └─ 자기 대학 데이터만 접근 가능                                        │
│      • GET /mt/tenant/{자기}/lrs ✅                                     │
│      • GET /mt/tenant/{자기}/analytics ✅                               │
│      • GET /mt/tenant/{다른대학}/lrs ❌                                  │
│      • GET /mt/tenant/{다른대학}/analytics ❌                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 인증 방식

| 호출자 | 인증 방식 | 헤더 |
|--------|----------|------|
| Service Market | API Key | `X-Market-API-Key: {market_key}` |
| 대학 관리자 | JWT | `Authorization: Bearer {jwt_token}` |

### 3.3 권한 검증 코드 예시

```python
from fastapi import Depends, HTTPException, Header
from typing import Optional

async def verify_access(
    tenant_id: str,
    market_api_key: Optional[str] = Header(None, alias="X-Market-API-Key"),
    authorization: Optional[str] = Header(None)
) -> dict:
    """접근 권한 검증"""

    # 1. Market API Key 검증
    if market_api_key:
        if market_api_key == os.getenv("MARKET_API_KEY"):
            return {"role": "market", "access": "all"}
        raise HTTPException(401, "Invalid Market API key")

    # 2. JWT 토큰 검증 (대학 관리자)
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        payload = verify_jwt(token)

        user_tenant_id = payload.get("tenant_id")

        # 자기 대학만 접근 가능
        if user_tenant_id != tenant_id:
            raise HTTPException(403, "Access denied to other tenant's data")

        return {"role": "tenant_admin", "access": user_tenant_id}

    raise HTTPException(401, "Authentication required")
```

---

# Part 2: 서비스 연동

## 4. manifest.yaml 작성

### 4.1 전체 manifest 구조

```yaml
# manifest.yaml - 서비스 등록 명세서
version: "1.0"

# ============================================================
# 서비스 기본 정보
# ============================================================
service:
  id: "my_ai_tutor"                    # 고유 ID (영문, 숫자, 언더스코어)
  name: "My AI Tutor"                  # 표시명
  description: "AI 기반 학습 튜터 서비스"
  version: "1.0.0"                     # 서비스 버전
  vendor: "My Company Inc."            # 개발사
  contact: "support@mycompany.com"     # 연락처

# ============================================================
# API 엔드포인트
# ============================================================
endpoints:
  # 서비스 기본 URL
  base_url: "https://mytutor.k-university.ai"

  # === 기본 API (필수 5개) ===
  health: "/mt/health"
  activate: "/mt/tenant/{tenant_id}/activate"
  deactivate: "/mt/tenant/{tenant_id}/deactivate"
  status: "/mt/tenant/{tenant_id}/status"
  usage: "/mt/tenant/{tenant_id}/usage"

  # === 데이터/분석 API (필수 4개) ===
  tenant_lrs: "/mt/tenant/{tenant_id}/lrs"
  tenant_analytics: "/mt/tenant/{tenant_id}/analytics"
  all_lrs: "/mt/tenants/lrs"
  all_analytics: "/mt/tenants/analytics"

  # === 사용자 접근 URL ===
  user_access: "/{tenant_id}"
  admin_dashboard: "/{tenant_id}/admin/analytics"

# ============================================================
# 인증 설정
# ============================================================
auth:
  # Market → 서비스 인증
  type: "api_key"
  header: "X-Market-API-Key"

tenant_admin_auth:
  # 대학 관리자 인증
  type: "jwt"

# ============================================================
# 요금제 정의
# ============================================================
plans:
  basic:
    features:
      - "ai_chat"
      - "file_upload"
    limits:
      max_users: 100
      storage_gb: 10
      api_calls_per_day: 1000

  standard:
    features:
      - "ai_chat"
      - "file_upload"
      - "rag"
      - "discussion"
    limits:
      max_users: 300
      storage_gb: 50
      api_calls_per_day: 5000

  premium:
    features:
      - "ai_chat"
      - "file_upload"
      - "rag"
      - "discussion"
      - "quiz"
      - "api_integration"
    limits:
      max_users: 1000
      storage_gb: 200
      api_calls_per_day: 50000

# ============================================================
# 사용량 메트릭 정의
# ============================================================
usage_metrics:
  - key: "active_users"
    name: "활성 사용자"
    unit: "명"
  - key: "total_sessions"
    name: "총 세션"
    unit: "회"
  - key: "ai_tokens"
    name: "AI 토큰"
    unit: "tokens"
  - key: "storage_mb"
    name: "스토리지"
    unit: "MB"

# ============================================================
# 데이터 격리 설정
# ============================================================
data_isolation:
  level: "database_per_tenant"
  isolated_data:
    - "user_data"
    - "lrs_statements"
    - "chat_history"
    - "files"
    - "analytics"

# ============================================================
# LRS 설정
# ============================================================
lrs_config:
  xapi_version: "1.0.3"
  verbs:
    - "completed"
    - "answered"
    - "asked"
    - "viewed"
    - "interacted"
  retention_days: 365

# ============================================================
# 분석 설정
# ============================================================
analytics_config:
  reports:
    - type: "engagement"
      name: "학습 참여도 분석"
    - type: "learning_outcomes"
      name: "학습 성과 분석"
    - type: "ai_usage"
      name: "AI 활용 분석"
  update_frequency: "daily"
```

### 4.2 필드별 상세 설명

| 섹션 | 필드 | 필수 | 설명 | 예시 |
|------|------|:----:|------|------|
| service | id | ✅ | 서비스 고유 ID | `my_ai_tutor` |
| service | name | ✅ | 서비스 표시명 | `My AI Tutor` |
| service | version | ✅ | 서비스 버전 | `1.0.0` |
| service | vendor | ✅ | 개발사/회사명 | `My Company` |
| endpoints | base_url | ✅ | 서비스 기본 URL | `https://...` |
| endpoints | health | ✅ | 헬스체크 경로 | `/mt/health` |
| endpoints | activate | ✅ | 테넌트 활성화 | `/mt/tenant/{tenant_id}/activate` |
| endpoints | deactivate | ✅ | 테넌트 비활성화 | `/mt/tenant/{tenant_id}/deactivate` |
| endpoints | status | ✅ | 테넌트 상태 조회 | `/mt/tenant/{tenant_id}/status` |
| endpoints | usage | ✅ | 사용량 조회 | `/mt/tenant/{tenant_id}/usage` |
| endpoints | tenant_lrs | ✅ | 테넌트 LRS 조회 | `/mt/tenant/{tenant_id}/lrs` |
| endpoints | tenant_analytics | ✅ | 테넌트 분석 조회 | `/mt/tenant/{tenant_id}/analytics` |
| endpoints | all_lrs | ✅ | 전체 LRS (Market용) | `/mt/tenants/lrs` |
| endpoints | all_analytics | ✅ | 전체 분석 (Market용) | `/mt/tenants/analytics` |
| endpoints | user_access | ✅ | 사용자 접속 URL | `/{tenant_id}` |
| plans | * | ✅ | 요금제별 기능/제한 | 위 예시 참조 |
| usage_metrics | * | ✅ | 사용량 메트릭 정의 | 위 예시 참조 |
| lrs_config | * | ✅ | LRS 설정 | 위 예시 참조 |

---

## 5. 표준 API 구현

### 5.1 API 구현 체크리스트

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

=== 비용 API (3개) ===
□ GET  /mt/tenant/{id}/billing         테넌트 비용 조회 (대학, Market)
□ GET  /mt/tenant/{id}/billing/details 비용 상세 내역 (대학, Market)
□ GET  /mt/tenants/billing             전체 비용 조회 (Market 전용)
```

### 5.2 기본 API 구현

#### 5.2.1 헬스체크

```python
# GET /mt/health

@router.get("/mt/health")
async def health_check():
    """서비스 상태 확인 - 인증 불필요"""

    # DB 연결 확인
    try:
        await db.execute("SELECT 1")
        db_status = "ok"
    except:
        db_status = "error"

    # 전체 상태 판정
    if db_status == "ok":
        status = "healthy"
    else:
        status = "unhealthy"

    return {
        "status": status,          # healthy, degraded, unhealthy
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "details": {
            "database": db_status
        }
    }
```

**응답 예시:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-03T12:00:00Z",
  "details": {
    "database": "ok"
  }
}
```

#### 5.2.2 테넌트 활성화

```python
# POST /mt/tenant/{tenant_id}/activate

from pydantic import BaseModel
from typing import List, Optional

class ContactInfo(BaseModel):
    email: str
    name: str

class ActivateRequest(BaseModel):
    tenant_id: str
    tenant_name: str
    plan: str
    features: List[str]
    config: Optional[dict] = {}
    contact: ContactInfo

class ActivateResponse(BaseModel):
    success: bool
    tenant_id: str
    access_url: str
    message: str

@router.post("/mt/tenant/{tenant_id}/activate")
async def activate_tenant(
    tenant_id: str,
    request: ActivateRequest,
    api_key: str = Depends(verify_market_api_key)
) -> ActivateResponse:
    """테넌트 활성화"""

    # 1. 이미 존재하는지 확인
    existing = await db.fetch_one(
        "SELECT id FROM tenants WHERE id = :id",
        {"id": tenant_id}
    )
    if existing:
        raise HTTPException(409, {
            "success": False,
            "error": "TENANT_EXISTS",
            "message": f"Tenant {tenant_id} already exists"
        })

    # 2. 테넌트 전용 DB 생성
    db_name = f"tenant_{tenant_id}"
    await create_tenant_database(db_name)

    # 3. Central DB에 테넌트 등록
    await db.execute("""
        INSERT INTO tenants (id, name, plan, features, db_name,
                            contact_email, contact_name, status, created_at)
        VALUES (:id, :name, :plan, :features, :db_name,
                :email, :contact_name, 'active', NOW())
    """, {
        "id": tenant_id,
        "name": request.tenant_name,
        "plan": request.plan,
        "features": json.dumps(request.features),
        "db_name": db_name,
        "email": request.contact.email,
        "contact_name": request.contact.name
    })

    # 4. 접속 URL 생성
    base_url = os.getenv("SERVICE_BASE_URL")
    access_url = f"{base_url}/{tenant_id}"

    return ActivateResponse(
        success=True,
        tenant_id=tenant_id,
        access_url=access_url,
        message="Tenant activated successfully"
    )


async def create_tenant_database(db_name: str):
    """테넌트 전용 데이터베이스 생성"""

    # DB 생성
    await db.execute(f"CREATE DATABASE {db_name}")

    # 테이블 생성 (테넌트 DB에 연결하여)
    tenant_db = await connect_to_db(db_name)

    await tenant_db.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_id VARCHAR(100),
            name VARCHAR(100),
            email VARCHAR(200),
            role VARCHAR(20) DEFAULT 'student',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE lrs_statements (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            statement_id VARCHAR(100) UNIQUE,
            actor JSONB NOT NULL,
            verb JSONB NOT NULL,
            object JSONB NOT NULL,
            result JSONB,
            context JSONB,
            timestamp TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE chat_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id),
            session_id VARCHAR(100),
            role VARCHAR(20),
            content TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE analytics_daily (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            date DATE NOT NULL,
            active_users INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
```

#### 5.2.3 테넌트 비활성화

```python
# POST /mt/tenant/{tenant_id}/deactivate

class DeactivateRequest(BaseModel):
    reason: str  # subscription_expired, admin_request, violation
    preserve_data: bool = True

class DeactivateResponse(BaseModel):
    success: bool
    tenant_id: str
    status: str
    data_preserved: bool
    data_retention_until: Optional[str] = None

@router.post("/mt/tenant/{tenant_id}/deactivate")
async def deactivate_tenant(
    tenant_id: str,
    request: DeactivateRequest,
    api_key: str = Depends(verify_market_api_key)
) -> DeactivateResponse:
    """테넌트 비활성화"""

    # 1. 테넌트 존재 확인
    tenant = await db.fetch_one(
        "SELECT id, db_name FROM tenants WHERE id = :id",
        {"id": tenant_id}
    )
    if not tenant:
        raise HTTPException(404, {
            "success": False,
            "error": "TENANT_NOT_FOUND",
            "message": f"Tenant {tenant_id} not found"
        })

    # 2. 상태 업데이트
    await db.execute("""
        UPDATE tenants
        SET status = 'suspended',
            deactivated_at = NOW(),
            deactivation_reason = :reason
        WHERE id = :id
    """, {"id": tenant_id, "reason": request.reason})

    # 3. 데이터 보존 기간 설정
    retention_until = None
    if request.preserve_data:
        retention_date = datetime.utcnow() + timedelta(days=90)
        retention_until = retention_date.isoformat() + "Z"
    else:
        # 데이터 즉시 삭제
        await db.execute(f"DROP DATABASE IF EXISTS {tenant['db_name']}")

    return DeactivateResponse(
        success=True,
        tenant_id=tenant_id,
        status="deactivated",
        data_preserved=request.preserve_data,
        data_retention_until=retention_until
    )
```

#### 5.2.4 테넌트 상태 조회

```python
# GET /mt/tenant/{tenant_id}/status

class StatusResponse(BaseModel):
    tenant_id: str
    status: str
    plan: str
    features: List[str]
    created_at: str
    updated_at: str

@router.get("/mt/tenant/{tenant_id}/status")
async def get_tenant_status(
    tenant_id: str,
    api_key: str = Depends(verify_market_api_key)
) -> StatusResponse:
    """테넌트 상태 조회"""

    tenant = await db.fetch_one("""
        SELECT id, status, plan, features, created_at,
               COALESCE(activated_at, created_at) as updated_at
        FROM tenants WHERE id = :id
    """, {"id": tenant_id})

    if not tenant:
        raise HTTPException(404, {
            "success": False,
            "error": "TENANT_NOT_FOUND",
            "message": f"Tenant {tenant_id} not found"
        })

    return StatusResponse(
        tenant_id=tenant["id"],
        status=tenant["status"],
        plan=tenant["plan"],
        features=json.loads(tenant["features"]),
        created_at=tenant["created_at"].isoformat() + "Z",
        updated_at=tenant["updated_at"].isoformat() + "Z"
    )
```

#### 5.2.5 사용량 조회

```python
# GET /mt/tenant/{tenant_id}/usage?period=2026-01

class UsageData(BaseModel):
    active_users: int
    total_sessions: int
    api_calls: int
    ai_tokens: int
    storage_mb: int

class UsageResponse(BaseModel):
    tenant_id: str
    period: str
    usage: UsageData

@router.get("/mt/tenant/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    period: str = Query(..., description="조회 기간 (YYYY-MM)"),
    api_key: str = Depends(verify_market_api_key)
) -> UsageResponse:
    """사용량 조회"""

    # 기간 형식 검증
    try:
        datetime.strptime(period, "%Y-%m")
    except ValueError:
        raise HTTPException(400, "period must be in YYYY-MM format")

    # 테넌트 존재 확인
    tenant = await db.fetch_one(
        "SELECT db_name FROM tenants WHERE id = :id",
        {"id": tenant_id}
    )
    if not tenant:
        raise HTTPException(404, f"Tenant {tenant_id} not found")

    # 테넌트 DB에서 사용량 조회
    tenant_db = await connect_to_db(tenant["db_name"])

    year, month = period.split("-")
    start_date = f"{period}-01"
    end_date = f"{period}-31"

    usage = await tenant_db.fetch_one("""
        SELECT
            COUNT(DISTINCT user_id) as active_users,
            COUNT(DISTINCT session_id) as total_sessions,
            COUNT(*) as api_calls,
            COALESCE(SUM(tokens_used), 0) as ai_tokens
        FROM chat_history
        WHERE created_at >= :start AND created_at < :end
    """, {"start": start_date, "end": end_date})

    # 스토리지 사용량 계산
    storage = await calculate_storage_usage(tenant["db_name"])

    return UsageResponse(
        tenant_id=tenant_id,
        period=period,
        usage=UsageData(
            active_users=usage["active_users"] or 0,
            total_sessions=usage["total_sessions"] or 0,
            api_calls=usage["api_calls"] or 0,
            ai_tokens=usage["ai_tokens"] or 0,
            storage_mb=storage
        )
    )
```

### 5.3 데이터/분석 API 구현

#### 5.3.1 테넌트 LRS 조회

```python
# GET /mt/tenant/{tenant_id}/lrs?from=2026-01-01&to=2026-01-31

class LRSStatement(BaseModel):
    id: str
    actor: dict
    verb: dict
    object: dict
    result: Optional[dict]
    timestamp: str

class LRSResponse(BaseModel):
    tenant_id: str
    period: dict
    total_statements: int
    statements: List[LRSStatement]
    pagination: dict

@router.get("/mt/tenant/{tenant_id}/lrs")
async def get_tenant_lrs(
    tenant_id: str,
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=1000),
    access: dict = Depends(verify_access)
) -> LRSResponse:
    """테넌트 LRS 데이터 조회"""

    # 권한 확인 (대학 관리자는 자기 대학만)
    if access["role"] == "tenant_admin" and access["access"] != tenant_id:
        raise HTTPException(403, "Access denied")

    # 테넌트 DB 연결
    tenant = await get_tenant(tenant_id)
    tenant_db = await connect_to_db(tenant["db_name"])

    # 전체 개수 조회
    total = await tenant_db.fetch_one("""
        SELECT COUNT(*) as count FROM lrs_statements
        WHERE timestamp >= :from_date AND timestamp <= :to_date
    """, {"from_date": from_date, "to_date": to_date})

    # 페이지네이션
    offset = (page - 1) * per_page
    statements = await tenant_db.fetch_all("""
        SELECT statement_id, actor, verb, object, result, timestamp
        FROM lrs_statements
        WHERE timestamp >= :from_date AND timestamp <= :to_date
        ORDER BY timestamp DESC
        LIMIT :limit OFFSET :offset
    """, {
        "from_date": from_date,
        "to_date": to_date,
        "limit": per_page,
        "offset": offset
    })

    return LRSResponse(
        tenant_id=tenant_id,
        period={"from": from_date, "to": to_date},
        total_statements=total["count"],
        statements=[
            LRSStatement(
                id=s["statement_id"],
                actor=s["actor"],
                verb=s["verb"],
                object=s["object"],
                result=s["result"],
                timestamp=s["timestamp"].isoformat() + "Z"
            ) for s in statements
        ],
        pagination={
            "page": page,
            "per_page": per_page,
            "total_pages": (total["count"] + per_page - 1) // per_page
        }
    )
```

#### 5.3.2 테넌트 분석 조회

```python
# GET /mt/tenant/{tenant_id}/analytics?period=2026-01

class AnalyticsSummary(BaseModel):
    total_users: int
    active_users: int
    completion_rate: float
    avg_session_duration_minutes: int
    total_learning_hours: int

class EngagementData(BaseModel):
    daily_active_users: List[int]
    peak_hours: List[int]
    retention_rate: float

class LearningOutcomes(BaseModel):
    courses_completed: int
    avg_score: float
    top_performers: int
    at_risk_students: int

class AIUsage(BaseModel):
    total_conversations: int
    avg_turns_per_conversation: float
    satisfaction_score: float

class AnalyticsResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    period: str
    summary: AnalyticsSummary
    engagement: EngagementData
    learning_outcomes: LearningOutcomes
    ai_usage: AIUsage

@router.get("/mt/tenant/{tenant_id}/analytics")
async def get_tenant_analytics(
    tenant_id: str,
    period: str = Query(..., description="YYYY-MM"),
    access: dict = Depends(verify_access)
) -> AnalyticsResponse:
    """테넌트 분석 리포트 조회"""

    # 권한 확인
    if access["role"] == "tenant_admin" and access["access"] != tenant_id:
        raise HTTPException(403, "Access denied")

    tenant = await get_tenant(tenant_id)
    tenant_db = await connect_to_db(tenant["db_name"])

    year, month = period.split("-")

    # 요약 데이터 조회
    summary_data = await tenant_db.fetch_one("""
        SELECT
            COUNT(DISTINCT id) as total_users,
            COUNT(DISTINCT CASE WHEN last_login_at >= :start THEN id END) as active_users
        FROM users
    """, {"start": f"{period}-01"})

    # 일별 활성 사용자
    daily_dau = await tenant_db.fetch_all("""
        SELECT date, active_users
        FROM analytics_daily
        WHERE date >= :start AND date < :end
        ORDER BY date
    """, {"start": f"{period}-01", "end": f"{period}-31"})

    # AI 대화 분석
    ai_stats = await tenant_db.fetch_one("""
        SELECT
            COUNT(DISTINCT session_id) as total_conversations,
            COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT session_id), 0) as avg_turns
        FROM chat_history
        WHERE created_at >= :start
    """, {"start": f"{period}-01"})

    return AnalyticsResponse(
        tenant_id=tenant_id,
        tenant_name=tenant["name"],
        period=period,
        summary=AnalyticsSummary(
            total_users=summary_data["total_users"],
            active_users=summary_data["active_users"],
            completion_rate=0.72,  # 실제 계산 로직 필요
            avg_session_duration_minutes=45,
            total_learning_hours=2500
        ),
        engagement=EngagementData(
            daily_active_users=[d["active_users"] for d in daily_dau],
            peak_hours=[9, 10, 14, 15],
            retention_rate=0.85
        ),
        learning_outcomes=LearningOutcomes(
            courses_completed=450,
            avg_score=82.5,
            top_performers=50,
            at_risk_students=25
        ),
        ai_usage=AIUsage(
            total_conversations=ai_stats["total_conversations"] or 0,
            avg_turns_per_conversation=ai_stats["avg_turns"] or 0,
            satisfaction_score=4.2
        )
    )
```

#### 5.3.3 전체 LRS 조회 (Market 전용)

```python
# GET /mt/tenants/lrs?from=2026-01-01&to=2026-01-31

@router.get("/mt/tenants/lrs")
async def get_all_tenants_lrs(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    summary_only: bool = Query(False),
    api_key: str = Depends(verify_market_master_key)  # Market 전용
):
    """전체 테넌트 LRS 데이터 (Market 전용)"""

    # 모든 활성 테넌트 조회
    tenants = await db.fetch_all(
        "SELECT id, name, db_name FROM tenants WHERE status = 'active'"
    )

    result = {
        "period": {"from": from_date, "to": to_date},
        "tenants": [],
        "total_statements_all": 0
    }

    for tenant in tenants:
        tenant_db = await connect_to_db(tenant["db_name"])

        count = await tenant_db.fetch_one("""
            SELECT COUNT(*) as count FROM lrs_statements
            WHERE timestamp >= :from AND timestamp <= :to
        """, {"from": from_date, "to": to_date})

        tenant_data = {
            "tenant_id": tenant["id"],
            "tenant_name": tenant["name"],
            "total_statements": count["count"]
        }

        if not summary_only:
            statements = await tenant_db.fetch_all("""
                SELECT * FROM lrs_statements
                WHERE timestamp >= :from AND timestamp <= :to
                LIMIT 1000
            """, {"from": from_date, "to": to_date})
            tenant_data["statements"] = statements

        result["tenants"].append(tenant_data)
        result["total_statements_all"] += count["count"]

    return result
```

#### 5.3.4 전체 분석 조회 (Market 전용)

```python
# GET /mt/tenants/analytics?period=2026-01

@router.get("/mt/tenants/analytics")
async def get_all_tenants_analytics(
    period: str = Query(...),
    api_key: str = Depends(verify_market_master_key)  # Market 전용
):
    """전체 테넌트 분석 (Market 전용)"""

    tenants = await db.fetch_all(
        "SELECT id, name, db_name FROM tenants WHERE status = 'active'"
    )

    result = {
        "period": period,
        "overall_summary": {
            "total_tenants": len(tenants),
            "total_users": 0,
            "total_active_users": 0,
            "avg_completion_rate": 0
        },
        "tenants": [],
        "rankings": {
            "by_active_users": [],
            "by_completion_rate": []
        }
    }

    tenant_stats = []

    for tenant in tenants:
        # 각 테넌트 분석 데이터 수집
        analytics = await get_tenant_analytics_data(tenant, period)

        tenant_stats.append({
            "tenant_id": tenant["id"],
            "tenant_name": tenant["name"],
            "summary": analytics["summary"],
            "engagement": analytics["engagement"],
            "learning_outcomes": analytics["learning_outcomes"]
        })

        result["overall_summary"]["total_users"] += analytics["summary"]["total_users"]
        result["overall_summary"]["total_active_users"] += analytics["summary"]["active_users"]

    result["tenants"] = tenant_stats

    # 랭킹 계산
    by_active = sorted(tenant_stats, key=lambda x: x["summary"]["active_users"], reverse=True)
    result["rankings"]["by_active_users"] = [t["tenant_id"] for t in by_active]

    by_completion = sorted(tenant_stats, key=lambda x: x["summary"].get("completion_rate", 0), reverse=True)
    result["rankings"]["by_completion_rate"] = [t["tenant_id"] for t in by_completion]

    return result
```

### 5.4 비용 API 구현

#### 5.4.1 테넌트 비용 요약 조회

```python
# GET /mt/tenant/{tenant_id}/billing?period=2026-01

from pydantic import BaseModel
from typing import Dict, Optional

class BillingResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    period: str
    billing_summary: dict
    cost_breakdown: dict
    usage_summary: dict

@router.get("/mt/tenant/{tenant_id}/billing")
async def get_tenant_billing(
    tenant_id: str,
    period: str = Query(..., description="조회 기간 (YYYY-MM)"),
    api_key: str = Depends(verify_api_key)
) -> BillingResponse:
    """테넌트 비용 요약 조회"""

    # 테넌트 확인
    tenant = await db.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # 기간 파싱
    year, month = map(int, period.split("-"))

    # API 비용 계산
    api_costs = await calculate_api_costs(tenant_id, year, month)

    # 클라우드 비용 계산
    cloud_costs = await calculate_cloud_costs(tenant_id, year, month)

    # 구독료 계산
    subscription_fee = await calculate_subscription_fee(tenant, year, month)

    # 사용량 요약
    usage = await get_usage_summary(tenant_id, year, month)

    total_amount = (
        api_costs["total"] +
        cloud_costs["total"] +
        subscription_fee["total"]
    )

    return BillingResponse(
        tenant_id=tenant_id,
        tenant_name=tenant["name"],
        period=period,
        billing_summary={
            "total_amount": total_amount,
            "currency": "KRW",
            "status": await get_billing_status(tenant_id, period)
        },
        cost_breakdown={
            "api_costs": api_costs,
            "cloud_costs": cloud_costs,
            "subscription_fee": subscription_fee
        },
        usage_summary=usage
    )


async def calculate_api_costs(tenant_id: str, year: int, month: int) -> dict:
    """API 사용 비용 계산"""

    # 일별 API 사용량 조회
    daily_usage = await db.query("""
        SELECT date, service, input_tokens, output_tokens, requests
        FROM api_usage_logs
        WHERE tenant_id = :tenant_id
          AND EXTRACT(YEAR FROM date) = :year
          AND EXTRACT(MONTH FROM date) = :month
        ORDER BY date
    """, {"tenant_id": tenant_id, "year": year, "month": month})

    # 단가 설정 (manifest.yaml의 pricing_config에서 로드)
    pricing = {
        "openai_gpt4": {"input_per_1k": 30, "output_per_1k": 60},
        "openai_gpt35": {"input_per_1k": 1.5, "output_per_1k": 2},
        "openai_embedding": {"per_1k": 0.13},
        "claude_sonnet": {"input_per_1k": 3, "output_per_1k": 15},
    }

    details = {}
    total = 0

    for row in daily_usage:
        service = row["service"]
        if service not in details:
            details[service] = 0

        if service in ["openai_gpt4", "openai_gpt35", "claude_sonnet"]:
            cost = (
                (row["input_tokens"] / 1000) * pricing[service]["input_per_1k"] +
                (row["output_tokens"] / 1000) * pricing[service]["output_per_1k"]
            )
        elif service == "openai_embedding":
            cost = (row["input_tokens"] / 1000) * pricing[service]["per_1k"]
        else:
            cost = 0

        details[service] += cost
        total += cost

    return {"total": int(total), "details": {k: int(v) for k, v in details.items()}}


async def calculate_cloud_costs(tenant_id: str, year: int, month: int) -> dict:
    """클라우드 사용 비용 계산"""

    # 리소스 사용량 조회
    usage = await db.query("""
        SELECT
            SUM(compute_hours * vcpu_count) as vcpu_hours,
            SUM(compute_hours * memory_gb) as memory_hours,
            AVG(storage_gb) as avg_storage_gb,
            AVG(database_gb) as avg_database_gb,
            SUM(network_egress_gb) as egress_gb
        FROM resource_usage
        WHERE tenant_id = :tenant_id
          AND EXTRACT(YEAR FROM date) = :year
          AND EXTRACT(MONTH FROM date) = :month
    """, {"tenant_id": tenant_id, "year": year, "month": month})

    if not usage:
        return {"total": 0, "details": {}}

    row = usage[0]

    # 단가 적용
    compute = (row["vcpu_hours"] or 0) * 50 + (row["memory_hours"] or 0) * 10
    storage = (row["avg_storage_gb"] or 0) * 100
    database = (row["avg_database_gb"] or 0) * 500
    network = (row["egress_gb"] or 0) * 120

    return {
        "total": int(compute + storage + database + network),
        "details": {
            "compute": int(compute),
            "storage": int(storage),
            "database": int(database),
            "network": int(network)
        }
    }


async def calculate_subscription_fee(tenant: dict, year: int, month: int) -> dict:
    """구독료 계산"""

    plan = tenant["plan"]

    # 요금제별 기본료
    base_fees = {
        "basic": 100000,
        "standard": 150000,
        "premium": 250000
    }

    # 요금제별 사용자 한도
    user_limits = {
        "basic": 100,
        "standard": 300,
        "premium": 1000
    }

    base_fee = base_fees.get(plan, 100000)
    user_limit = user_limits.get(plan, 100)

    # 실제 사용자 수 조회
    active_users = await db.query("""
        SELECT COUNT(DISTINCT user_id) as count
        FROM user_sessions
        WHERE tenant_id = :tenant_id
          AND EXTRACT(YEAR FROM created_at) = :year
          AND EXTRACT(MONTH FROM created_at) = :month
    """, {"tenant_id": tenant["id"], "year": year, "month": month})

    user_count = active_users[0]["count"] if active_users else 0

    # 초과 사용자 요금
    additional_users = max(0, user_count - user_limit)
    additional_fee = additional_users * 1000  # 추가 사용자당 1,000원

    return {
        "total": base_fee + additional_fee,
        "plan": plan,
        "base_fee": base_fee,
        "additional_users_fee": additional_fee,
        "additional_users_count": additional_users
    }
```

**응답 예시:**
```json
{
  "tenant_id": "hallym_univ",
  "tenant_name": "한림대학교",
  "period": "2026-01",
  "billing_summary": {
    "total_amount": 1250000,
    "currency": "KRW",
    "status": "pending"
  },
  "cost_breakdown": {
    "api_costs": {
      "total": 450000,
      "details": {
        "openai_gpt4": 320000,
        "openai_embedding": 80000,
        "claude_sonnet": 50000
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

#### 5.4.2 테넌트 비용 상세 내역

```python
# GET /mt/tenant/{tenant_id}/billing/details?period=2026-01&category=api_costs

@router.get("/mt/tenant/{tenant_id}/billing/details")
async def get_tenant_billing_details(
    tenant_id: str,
    period: str = Query(..., description="조회 기간 (YYYY-MM)"),
    category: str = Query(None, description="카테고리 (api_costs, cloud_costs, subscription_fee)"),
    page: int = Query(1, ge=1),
    api_key: str = Depends(verify_api_key)
):
    """테넌트 비용 상세 내역"""

    year, month = map(int, period.split("-"))

    if category == "api_costs":
        # 일별 API 사용 상세
        daily_data = await db.query("""
            SELECT date, service, input_tokens, output_tokens, requests
            FROM api_usage_logs
            WHERE tenant_id = :tenant_id
              AND EXTRACT(YEAR FROM date) = :year
              AND EXTRACT(MONTH FROM date) = :month
            ORDER BY date, service
        """, {"tenant_id": tenant_id, "year": year, "month": month})

        # 일별로 그룹화
        daily_breakdown = []
        current_date = None
        current_items = []

        for row in daily_data:
            if current_date != row["date"]:
                if current_date:
                    daily_breakdown.append({
                        "date": current_date.isoformat(),
                        "items": current_items,
                        "daily_total": sum(item["amount"] for item in current_items)
                    })
                current_date = row["date"]
                current_items = []

            # 비용 계산
            amount = calculate_api_item_cost(row)
            current_items.append({
                "service": row["service"],
                "usage": {
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "requests": row["requests"]
                },
                "amount": amount
            })

        # 마지막 날짜 추가
        if current_items:
            daily_breakdown.append({
                "date": current_date.isoformat(),
                "items": current_items,
                "daily_total": sum(item["amount"] for item in current_items)
            })

        return {
            "tenant_id": tenant_id,
            "period": period,
            "category": "api_costs",
            "daily_breakdown": daily_breakdown,
            "category_total": sum(d["daily_total"] for d in daily_breakdown)
        }

    elif category == "cloud_costs":
        # 클라우드 비용 상세
        daily_data = await db.query("""
            SELECT date, compute_hours, vcpu_count, memory_gb,
                   storage_gb, database_gb, network_egress_gb
            FROM resource_usage
            WHERE tenant_id = :tenant_id
              AND EXTRACT(YEAR FROM date) = :year
              AND EXTRACT(MONTH FROM date) = :month
            ORDER BY date
        """, {"tenant_id": tenant_id, "year": year, "month": month})

        daily_breakdown = []
        for row in daily_data:
            compute = row["compute_hours"] * row["vcpu_count"] * 50
            storage = row["storage_gb"] * 100 / 30  # 일할 계산
            database = row["database_gb"] * 500 / 30
            network = row["network_egress_gb"] * 120

            daily_breakdown.append({
                "date": row["date"].isoformat(),
                "items": {
                    "compute": {"usage": f"{row['compute_hours']}h x {row['vcpu_count']}vCPU", "amount": int(compute)},
                    "storage": {"usage": f"{row['storage_gb']}GB", "amount": int(storage)},
                    "database": {"usage": f"{row['database_gb']}GB", "amount": int(database)},
                    "network": {"usage": f"{row['network_egress_gb']}GB", "amount": int(network)}
                },
                "daily_total": int(compute + storage + database + network)
            })

        return {
            "tenant_id": tenant_id,
            "period": period,
            "category": "cloud_costs",
            "daily_breakdown": daily_breakdown,
            "category_total": sum(d["daily_total"] for d in daily_breakdown)
        }

    else:
        # 전체 요약 반환
        return await get_tenant_billing(tenant_id, period, api_key)
```

#### 5.4.3 전체 비용 조회 (Market 전용)

```python
# GET /mt/tenants/billing?period=2026-01

@router.get("/mt/tenants/billing")
async def get_all_tenants_billing(
    period: str = Query(..., description="조회 기간 (YYYY-MM)"),
    api_key: str = Depends(verify_market_master_key)  # Market 마스터 키만 허용
):
    """전체 테넌트 비용 조회 (Market 전용)"""

    year, month = map(int, period.split("-"))

    # 모든 활성 테넌트 조회
    tenants = await db.query("""
        SELECT id, name, plan FROM tenants WHERE status = 'active'
    """)

    result = {
        "period": period,
        "overall_summary": {
            "total_tenants": len(tenants),
            "total_revenue": 0,
            "total_api_costs": 0,
            "total_cloud_costs": 0,
            "total_subscription_fees": 0,
            "currency": "KRW"
        },
        "tenants": [],
        "rankings": {},
        "cost_trends": {}
    }

    tenant_billings = []

    for tenant in tenants:
        # 각 테넌트 비용 계산
        api_costs = await calculate_api_costs(tenant["id"], year, month)
        cloud_costs = await calculate_cloud_costs(tenant["id"], year, month)
        subscription_fee = await calculate_subscription_fee(tenant, year, month)

        total = api_costs["total"] + cloud_costs["total"] + subscription_fee["total"]

        billing = {
            "tenant_id": tenant["id"],
            "tenant_name": tenant["name"],
            "plan": tenant["plan"],
            "billing_summary": {
                "total_amount": total,
                "api_costs": api_costs["total"],
                "cloud_costs": cloud_costs["total"],
                "subscription_fee": subscription_fee["total"],
                "status": await get_billing_status(tenant["id"], period)
            }
        }

        tenant_billings.append(billing)

        # 합계 업데이트
        result["overall_summary"]["total_revenue"] += total
        result["overall_summary"]["total_api_costs"] += api_costs["total"]
        result["overall_summary"]["total_cloud_costs"] += cloud_costs["total"]
        result["overall_summary"]["total_subscription_fees"] += subscription_fee["total"]

    result["tenants"] = tenant_billings

    # 랭킹 계산
    by_total = sorted(tenant_billings, key=lambda x: x["billing_summary"]["total_amount"], reverse=True)
    result["rankings"]["by_total_cost"] = [t["tenant_id"] for t in by_total]

    by_api = sorted(tenant_billings, key=lambda x: x["billing_summary"]["api_costs"], reverse=True)
    result["rankings"]["by_api_usage"] = [t["tenant_id"] for t in by_api]

    # 최근 3개월 트렌드 계산
    trends = await calculate_cost_trends(year, month)
    result["cost_trends"] = trends

    return result


async def calculate_cost_trends(year: int, month: int) -> dict:
    """최근 3개월 비용 트렌드 계산"""

    api_trend = []
    cloud_trend = []

    for i in range(3):
        # 3개월 전부터 현재까지
        m = month - 2 + i
        y = year
        if m <= 0:
            m += 12
            y -= 1

        total_api = await db.query("""
            SELECT COALESCE(SUM(cost), 0) as total
            FROM api_usage_logs
            WHERE EXTRACT(YEAR FROM date) = :year
              AND EXTRACT(MONTH FROM date) = :month
        """, {"year": y, "month": m})

        total_cloud = await db.query("""
            SELECT COALESCE(SUM(cost), 0) as total
            FROM resource_usage
            WHERE EXTRACT(YEAR FROM date) = :year
              AND EXTRACT(MONTH FROM date) = :month
        """, {"year": y, "month": m})

        api_trend.append(int(total_api[0]["total"]) if total_api else 0)
        cloud_trend.append(int(total_cloud[0]["total"]) if total_cloud else 0)

    # 월간 성장률 계산
    if api_trend[1] > 0:
        growth_rate = (api_trend[2] - api_trend[1]) / api_trend[1]
    else:
        growth_rate = 0

    return {
        "monthly_growth_rate": round(growth_rate, 2),
        "api_cost_trend": api_trend,
        "cloud_cost_trend": cloud_trend
    }
```

**응답 예시:**
```json
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
    }
  ],
  "rankings": {
    "by_total_cost": ["hallym_univ", "korea_univ", "snu"],
    "by_api_usage": ["korea_univ", "hallym_univ", "snu"]
  },
  "cost_trends": {
    "monthly_growth_rate": 0.12,
    "api_cost_trend": [18500000, 20200000, 22500000],
    "cloud_cost_trend": [25000000, 26200000, 27500000]
  }
}
```

---

## 6. Service Market 등록

### 6.1 등록 전 체크리스트

```
□ manifest.yaml 작성 완료
□ 모든 API 엔드포인트 구현 완료
  □ GET  /mt/health
  □ POST /mt/tenant/{id}/activate
  □ POST /mt/tenant/{id}/deactivate
  □ GET  /mt/tenant/{id}/status
  □ GET  /mt/tenant/{id}/usage
  □ GET  /mt/tenant/{id}/lrs
  □ GET  /mt/tenant/{id}/analytics
  □ GET  /mt/tenant/{id}/billing
  □ GET  /mt/tenant/{id}/billing/details
  □ GET  /mt/tenants/lrs
  □ GET  /mt/tenants/analytics
  □ GET  /mt/tenants/billing
□ 서비스 배포 완료 (HTTPS)
□ 헬스체크 응답 확인
```

### 6.2 등록 절차

```
1. Service Market 관리자 콘솔 접속
   https://market.k-university.ai/admin

2. "서비스 등록" 메뉴 클릭

3. manifest.yaml 파일 업로드

4. 자동 검증 (약 1-2분)
   - manifest 스키마 검증
   - 엔드포인트 접근성 테스트
   - 헬스체크 API 호출

5. 검증 통과 시 API 키 발급
   - Market API Key: mk_live_xxx...
   - 이 키로 Market에서 서비스로 API 호출 시 인증

6. 환경변수 설정
   MARKET_API_KEY=mk_live_xxx...

7. 등록 완료
```

### 6.3 등록 후 확인사항

```bash
# 헬스체크 테스트
curl https://myservice.k-university.ai/mt/health

# 예상 응답
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-03T12:00:00Z"
}

# Market에서 호출 테스트 (Market API Key 사용)
curl -X POST https://myservice.k-university.ai/mt/tenant/test_univ/activate \
  -H "X-Market-API-Key: mk_live_xxx..." \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "test_univ",
    "tenant_name": "테스트대학교",
    "plan": "basic",
    "features": ["ai_chat"],
    "contact": {"email": "test@test.ac.kr", "name": "테스터"}
  }'
```

---

# Part 3: 데이터 관리

## 7. 대학별 데이터 격리

### 7.1 격리 전략

```
┌─────────────────────────────────────────────────────────────────────┐
│                    데이터 격리 구조                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    PostgreSQL Server                          │   │
│   │                                                               │   │
│   │   ┌─────────────┐                                            │   │
│   │   │ central_db  │  ← 테넌트 메타정보만                        │   │
│   │   │             │    (테넌트 목록, 설정)                       │   │
│   │   └─────────────┘                                            │   │
│   │                                                               │   │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │
│   │   │tenant_hallym│  │tenant_korea │  │tenant_snu   │  ...    │   │
│   │   │             │  │             │  │             │         │   │
│   │   │ • users     │  │ • users     │  │ • users     │         │   │
│   │   │ • lrs       │  │ • lrs       │  │ • lrs       │         │   │
│   │   │ • chat      │  │ • chat      │  │ • chat      │         │   │
│   │   │ • analytics │  │ • analytics │  │ • analytics │         │   │
│   │   └─────────────┘  └─────────────┘  └─────────────┘         │   │
│   │                                                               │   │
│   │   ← 완전히 격리된 데이터                                       │   │
│   │   ← 다른 테넌트 데이터 접근 불가                               │   │
│   │                                                               │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 테넌트 DB 생성 코드

```python
# tenant_manager.py

class TenantDatabaseManager:
    """테넌트 데이터베이스 관리"""

    def __init__(self, central_db_url: str):
        self.central_db_url = central_db_url
        self.tenant_connections = {}  # 테넌트별 연결 캐시

    async def create_tenant_database(self, tenant_id: str) -> str:
        """테넌트 전용 데이터베이스 생성"""

        db_name = f"tenant_{tenant_id}"

        # 1. 데이터베이스 생성 (PostgreSQL)
        admin_conn = await asyncpg.connect(self.central_db_url)
        await admin_conn.execute(f"""
            CREATE DATABASE {db_name}
            WITH OWNER = postgres
            ENCODING = 'UTF8'
        """)
        await admin_conn.close()

        # 2. 테넌트 DB에 테이블 생성
        tenant_db_url = self._get_tenant_db_url(db_name)
        tenant_conn = await asyncpg.connect(tenant_db_url)

        await tenant_conn.execute("""
            -- 사용자 테이블
            CREATE TABLE users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                external_id VARCHAR(100) UNIQUE,
                name VARCHAR(100),
                email VARCHAR(200),
                role VARCHAR(20) DEFAULT 'student',
                created_at TIMESTAMP DEFAULT NOW(),
                last_login_at TIMESTAMP
            );

            -- LRS 테이블
            CREATE TABLE lrs_statements (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                statement_id VARCHAR(100) UNIQUE NOT NULL,
                actor JSONB NOT NULL,
                verb JSONB NOT NULL,
                object JSONB NOT NULL,
                result JSONB,
                context JSONB,
                timestamp TIMESTAMP NOT NULL,
                stored TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_lrs_timestamp ON lrs_statements(timestamp);
            CREATE INDEX idx_lrs_actor ON lrs_statements USING gin(actor);
            CREATE INDEX idx_lrs_verb ON lrs_statements USING gin(verb);

            -- 채팅 이력
            CREATE TABLE chat_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id),
                session_id VARCHAR(100) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                model VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_chat_user ON chat_history(user_id);
            CREATE INDEX idx_chat_session ON chat_history(session_id);

            -- 일별 분석 데이터
            CREATE TABLE analytics_daily (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                date DATE UNIQUE NOT NULL,
                active_users INTEGER DEFAULT 0,
                new_users INTEGER DEFAULT 0,
                total_sessions INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                total_tokens BIGINT DEFAULT 0,
                avg_session_duration INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_analytics_date ON analytics_daily(date);
        """)

        await tenant_conn.close()

        return db_name

    async def get_tenant_connection(self, tenant_id: str):
        """테넌트 DB 연결 가져오기"""

        if tenant_id not in self.tenant_connections:
            # Central DB에서 테넌트 정보 조회
            tenant = await self._get_tenant_info(tenant_id)
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")

            db_url = self._get_tenant_db_url(tenant["db_name"])
            self.tenant_connections[tenant_id] = await asyncpg.connect(db_url)

        return self.tenant_connections[tenant_id]

    async def delete_tenant_database(self, tenant_id: str):
        """테넌트 데이터베이스 삭제"""

        tenant = await self._get_tenant_info(tenant_id)
        db_name = tenant["db_name"]

        # 연결 종료
        if tenant_id in self.tenant_connections:
            await self.tenant_connections[tenant_id].close()
            del self.tenant_connections[tenant_id]

        # 데이터베이스 삭제
        admin_conn = await asyncpg.connect(self.central_db_url)

        # 활성 연결 종료
        await admin_conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}'
        """)

        await admin_conn.execute(f"DROP DATABASE IF EXISTS {db_name}")
        await admin_conn.close()
```

### 7.3 테넌트별 데이터 접근

```python
# 요청별 테넌트 컨텍스트 관리

from contextvars import ContextVar
from fastapi import Request

# 현재 요청의 테넌트 ID
current_tenant: ContextVar[str] = ContextVar("current_tenant", default=None)

class TenantMiddleware:
    """테넌트 컨텍스트 미들웨어"""

    async def __call__(self, request: Request, call_next):
        # URL 경로에서 테넌트 ID 추출
        # 예: /hallym/chat -> tenant_id = "hallym"
        path_parts = request.url.path.split("/")

        if len(path_parts) > 1 and path_parts[1] not in ["mt", "health", "docs"]:
            tenant_id = path_parts[1] + "_univ"  # hallym -> hallym_univ
            current_tenant.set(tenant_id)

        response = await call_next(request)
        return response


# 비즈니스 로직에서 테넌트 DB 사용
async def save_chat_message(user_id: str, message: str):
    """채팅 메시지 저장 - 자동으로 현재 테넌트 DB에 저장"""

    tenant_id = current_tenant.get()
    if not tenant_id:
        raise ValueError("Tenant context not set")

    tenant_db = await tenant_manager.get_tenant_connection(tenant_id)

    await tenant_db.execute("""
        INSERT INTO chat_history (user_id, session_id, role, content)
        VALUES ($1, $2, 'user', $3)
    """, user_id, session_id, message)
```

---

## 8. LRS 데이터 관리

### 8.1 xAPI Statement 구조

```json
{
  "id": "uuid-string",
  "actor": {
    "objectType": "Agent",
    "name": "홍길동",
    "account": {
      "name": "student001",
      "homePage": "https://hallym.ac.kr"
    }
  },
  "verb": {
    "id": "http://adlnet.gov/expapi/verbs/asked",
    "display": {
      "ko-KR": "질문함",
      "en-US": "asked"
    }
  },
  "object": {
    "objectType": "Activity",
    "id": "https://myservice.k-university.ai/hallym/chat/session_123",
    "definition": {
      "type": "http://adlnet.gov/expapi/activities/interaction",
      "name": {
        "ko-KR": "AI 튜터 대화"
      }
    }
  },
  "result": {
    "response": "미분의 정의가 무엇인가요?",
    "extensions": {
      "https://myservice.k-university.ai/xapi/ai-quality": 4.5
    }
  },
  "context": {
    "extensions": {
      "https://myservice.k-university.ai/xapi/tenant": "hallym_univ",
      "https://myservice.k-university.ai/xapi/session": "session_123"
    }
  },
  "timestamp": "2026-01-03T14:30:00Z"
}
```

### 8.2 LRS 저장 코드

```python
# lrs_service.py

from datetime import datetime
from uuid import uuid4
import json

class LRSService:
    """LRS (Learning Record Store) 서비스"""

    def __init__(self, tenant_manager: TenantDatabaseManager):
        self.tenant_manager = tenant_manager

    async def store_statement(
        self,
        tenant_id: str,
        actor: dict,
        verb: dict,
        activity_object: dict,
        result: dict = None,
        context: dict = None
    ) -> str:
        """xAPI Statement 저장"""

        statement_id = str(uuid4())
        timestamp = datetime.utcnow()

        # 컨텍스트에 테넌트 정보 추가
        if context is None:
            context = {}
        context.setdefault("extensions", {})
        context["extensions"]["https://myservice.k-university.ai/xapi/tenant"] = tenant_id

        # 테넌트 DB에 저장
        tenant_db = await self.tenant_manager.get_tenant_connection(tenant_id)

        await tenant_db.execute("""
            INSERT INTO lrs_statements
            (statement_id, actor, verb, object, result, context, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
            statement_id,
            json.dumps(actor),
            json.dumps(verb),
            json.dumps(activity_object),
            json.dumps(result) if result else None,
            json.dumps(context) if context else None,
            timestamp
        )

        return statement_id

    async def record_chat_interaction(
        self,
        tenant_id: str,
        user_id: str,
        user_name: str,
        session_id: str,
        question: str,
        answer_quality: float = None
    ):
        """AI 채팅 상호작용 기록"""

        actor = {
            "objectType": "Agent",
            "name": user_name,
            "account": {
                "name": user_id,
                "homePage": f"https://{tenant_id.replace('_univ', '')}.ac.kr"
            }
        }

        verb = {
            "id": "http://adlnet.gov/expapi/verbs/asked",
            "display": {"ko-KR": "질문함", "en-US": "asked"}
        }

        activity_object = {
            "objectType": "Activity",
            "id": f"https://myservice.k-university.ai/{tenant_id}/chat/{session_id}",
            "definition": {
                "type": "http://adlnet.gov/expapi/activities/interaction",
                "name": {"ko-KR": "AI 튜터 대화"}
            }
        }

        result = {
            "response": question[:500]  # 질문 내용 (최대 500자)
        }
        if answer_quality:
            result["extensions"] = {
                "https://myservice.k-university.ai/xapi/ai-quality": answer_quality
            }

        context = {
            "extensions": {
                "https://myservice.k-university.ai/xapi/session": session_id
            }
        }

        return await self.store_statement(
            tenant_id, actor, verb, activity_object, result, context
        )

    async def record_completion(
        self,
        tenant_id: str,
        user_id: str,
        user_name: str,
        activity_id: str,
        activity_name: str,
        score: float = None,
        success: bool = True
    ):
        """학습 완료 기록"""

        actor = {
            "objectType": "Agent",
            "name": user_name,
            "account": {"name": user_id, "homePage": f"https://{tenant_id.replace('_univ', '')}.ac.kr"}
        }

        verb = {
            "id": "http://adlnet.gov/expapi/verbs/completed",
            "display": {"ko-KR": "완료함", "en-US": "completed"}
        }

        activity_object = {
            "objectType": "Activity",
            "id": activity_id,
            "definition": {"name": {"ko-KR": activity_name}}
        }

        result = {
            "completion": True,
            "success": success
        }
        if score is not None:
            result["score"] = {"scaled": score}

        return await self.store_statement(
            tenant_id, actor, verb, activity_object, result
        )
```

### 8.3 LRS 조회 예시

```python
# 특정 기간 LRS 데이터 조회
async def get_lrs_statements(
    tenant_id: str,
    from_date: datetime,
    to_date: datetime,
    verb_id: str = None,
    limit: int = 100
) -> list:
    """LRS Statement 조회"""

    tenant_db = await tenant_manager.get_tenant_connection(tenant_id)

    query = """
        SELECT statement_id, actor, verb, object, result, context, timestamp
        FROM lrs_statements
        WHERE timestamp >= $1 AND timestamp <= $2
    """
    params = [from_date, to_date]

    if verb_id:
        query += " AND verb->>'id' = $3"
        params.append(verb_id)

    query += " ORDER BY timestamp DESC LIMIT $" + str(len(params) + 1)
    params.append(limit)

    rows = await tenant_db.fetch(query, *params)

    return [
        {
            "id": row["statement_id"],
            "actor": json.loads(row["actor"]),
            "verb": json.loads(row["verb"]),
            "object": json.loads(row["object"]),
            "result": json.loads(row["result"]) if row["result"] else None,
            "context": json.loads(row["context"]) if row["context"] else None,
            "timestamp": row["timestamp"].isoformat() + "Z"
        }
        for row in rows
    ]
```

---

## 9. 분석 서비스 구현

### 9.1 일별 분석 데이터 집계

```python
# analytics_service.py

class AnalyticsService:
    """분석 서비스"""

    async def aggregate_daily_stats(self, tenant_id: str, date: datetime.date):
        """일별 통계 집계 (매일 자정에 실행)"""

        tenant_db = await tenant_manager.get_tenant_connection(tenant_id)

        # 활성 사용자 수
        active_users = await tenant_db.fetchval("""
            SELECT COUNT(DISTINCT user_id)
            FROM chat_history
            WHERE DATE(created_at) = $1
        """, date)

        # 신규 사용자 수
        new_users = await tenant_db.fetchval("""
            SELECT COUNT(*)
            FROM users
            WHERE DATE(created_at) = $1
        """, date)

        # 총 세션 수
        total_sessions = await tenant_db.fetchval("""
            SELECT COUNT(DISTINCT session_id)
            FROM chat_history
            WHERE DATE(created_at) = $1
        """, date)

        # 총 메시지 수
        total_messages = await tenant_db.fetchval("""
            SELECT COUNT(*)
            FROM chat_history
            WHERE DATE(created_at) = $1
        """, date)

        # 총 토큰 사용량
        total_tokens = await tenant_db.fetchval("""
            SELECT COALESCE(SUM(tokens_used), 0)
            FROM chat_history
            WHERE DATE(created_at) = $1
        """, date)

        # 평균 세션 시간 (초)
        avg_duration = await tenant_db.fetchval("""
            SELECT AVG(EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at))))
            FROM chat_history
            WHERE DATE(created_at) = $1
            GROUP BY session_id
        """, date)

        # 저장/업데이트
        await tenant_db.execute("""
            INSERT INTO analytics_daily
            (date, active_users, new_users, total_sessions, total_messages,
             total_tokens, avg_session_duration)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (date) DO UPDATE SET
                active_users = EXCLUDED.active_users,
                new_users = EXCLUDED.new_users,
                total_sessions = EXCLUDED.total_sessions,
                total_messages = EXCLUDED.total_messages,
                total_tokens = EXCLUDED.total_tokens,
                avg_session_duration = EXCLUDED.avg_session_duration
        """, date, active_users, new_users, total_sessions,
            total_messages, total_tokens, int(avg_duration or 0))

    async def get_monthly_summary(self, tenant_id: str, year: int, month: int) -> dict:
        """월별 요약 리포트"""

        tenant_db = await tenant_manager.get_tenant_connection(tenant_id)

        # 월간 집계
        summary = await tenant_db.fetchrow("""
            SELECT
                SUM(active_users) as total_active_users,
                SUM(new_users) as total_new_users,
                SUM(total_sessions) as total_sessions,
                SUM(total_messages) as total_messages,
                SUM(total_tokens) as total_tokens,
                AVG(avg_session_duration) as avg_session_duration
            FROM analytics_daily
            WHERE EXTRACT(YEAR FROM date) = $1
              AND EXTRACT(MONTH FROM date) = $2
        """, year, month)

        # 일별 DAU 추이
        daily_dau = await tenant_db.fetch("""
            SELECT date, active_users
            FROM analytics_daily
            WHERE EXTRACT(YEAR FROM date) = $1
              AND EXTRACT(MONTH FROM date) = $2
            ORDER BY date
        """, year, month)

        # 총 사용자 수
        total_users = await tenant_db.fetchval("SELECT COUNT(*) FROM users")

        return {
            "summary": {
                "total_users": total_users,
                "active_users": summary["total_active_users"] or 0,
                "new_users": summary["total_new_users"] or 0,
                "total_sessions": summary["total_sessions"] or 0,
                "total_messages": summary["total_messages"] or 0,
                "total_tokens": summary["total_tokens"] or 0,
                "avg_session_duration_minutes": int((summary["avg_session_duration"] or 0) / 60)
            },
            "daily_active_users": [
                {"date": str(row["date"]), "count": row["active_users"]}
                for row in daily_dau
            ]
        }
```

### 9.2 분석 스케줄러

```python
# scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', hour=1, minute=0)  # 매일 01:00
async def daily_analytics_job():
    """일별 분석 데이터 집계 작업"""

    yesterday = datetime.now().date() - timedelta(days=1)

    # 모든 활성 테넌트 조회
    tenants = await db.fetch_all(
        "SELECT id FROM tenants WHERE status = 'active'"
    )

    analytics_service = AnalyticsService()

    for tenant in tenants:
        try:
            await analytics_service.aggregate_daily_stats(
                tenant["id"], yesterday
            )
            print(f"Analytics aggregated for {tenant['id']}")
        except Exception as e:
            print(f"Failed to aggregate analytics for {tenant['id']}: {e}")

# 앱 시작 시
scheduler.start()
```

---

# Part 4: 운영 가이드

## 10. 모니터링

### 10.1 헬스체크 모니터링

```python
# Market에서 주기적으로 호출하는 헬스체크 모니터링

# 서비스 측 구현
@router.get("/mt/health")
async def health_check():
    """상세 헬스체크"""

    checks = {}
    overall_status = "healthy"

    # DB 연결 확인
    try:
        await db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        overall_status = "unhealthy"

    # Redis 연결 확인
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        if overall_status == "healthy":
            overall_status = "degraded"

    # 디스크 공간 확인
    disk_usage = shutil.disk_usage("/")
    disk_free_gb = disk_usage.free / (1024 ** 3)
    if disk_free_gb < 10:
        checks["disk"] = f"warning: {disk_free_gb:.1f}GB free"
        if overall_status == "healthy":
            overall_status = "degraded"
    else:
        checks["disk"] = "ok"

    return {
        "status": overall_status,
        "version": os.getenv("SERVICE_VERSION", "1.0.0"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks
    }
```

### 10.2 사용량 알림

```python
# 사용량 임계치 초과 시 알림

async def check_usage_limits():
    """사용량 한도 체크 (매시간 실행)"""

    tenants = await db.fetch_all("""
        SELECT t.id, t.name, t.contact_email,
               s.max_users, s.plan_type
        FROM tenants t
        JOIN subscriptions s ON t.id = s.tenant_id
        WHERE t.status = 'active' AND s.status = 'active'
    """)

    for tenant in tenants:
        tenant_db = await tenant_manager.get_tenant_connection(tenant["id"])

        # 현재 사용자 수
        user_count = await tenant_db.fetchval("SELECT COUNT(*) FROM users")

        # 한도의 80% 초과 시 경고
        if user_count > tenant["max_users"] * 0.8:
            await send_warning_email(
                to=tenant["contact_email"],
                subject=f"[{tenant['name']}] 사용자 수 한도 임박",
                message=f"현재 사용자 수: {user_count}/{tenant['max_users']}"
            )

        # 한도 초과 시 알림
        if user_count > tenant["max_users"]:
            await send_alert_email(
                to=tenant["contact_email"],
                subject=f"[{tenant['name']}] 사용자 수 한도 초과",
                message=f"현재 사용자 수: {user_count}/{tenant['max_users']}\n요금제 업그레이드를 권장합니다."
            )
```

---

## 11. 트러블슈팅

### 11.1 자주 발생하는 문제

| 문제 | 원인 | 해결 방법 |
|------|------|----------|
| 테넌트 활성화 실패 | DB 생성 권한 부족 | PostgreSQL 사용자에 CREATEDB 권한 부여 |
| LRS 저장 실패 | JSON 형식 오류 | actor, verb, object 필수 필드 확인 |
| 분석 데이터 없음 | 스케줄러 미실행 | cron job 상태 확인 |
| Market API 인증 실패 | API Key 불일치 | 환경변수 MARKET_API_KEY 확인 |
| 테넌트 데이터 혼입 | 컨텍스트 미설정 | TenantMiddleware 적용 확인 |

### 11.2 로그 확인

```bash
# 애플리케이션 로그
tail -f /var/log/myservice/app.log

# PostgreSQL 로그
tail -f /var/log/postgresql/postgresql-15-main.log

# 특정 테넌트 관련 로그만 필터
grep "tenant_id=hallym_univ" /var/log/myservice/app.log
```

### 11.3 데이터 복구

```bash
# 테넌트 DB 백업
pg_dump -h localhost -U postgres tenant_hallym_univ > backup_hallym.sql

# 테넌트 DB 복원
psql -h localhost -U postgres -d tenant_hallym_univ < backup_hallym.sql

# 특정 테이블만 복원
pg_restore -h localhost -U postgres -d tenant_hallym_univ -t lrs_statements backup.dump
```

---

# Part 5: 부록

## 12. API 체크리스트

```
=== 필수 구현 API (9개) ===

□ GET  /mt/health
  응답: { status, version, timestamp }

□ POST /mt/tenant/{id}/activate
  요청: { tenant_id, tenant_name, plan, features, config, contact }
  응답: { success, tenant_id, access_url, message }

□ POST /mt/tenant/{id}/deactivate
  요청: { reason, preserve_data }
  응답: { success, tenant_id, status, data_preserved }

□ GET  /mt/tenant/{id}/status
  응답: { tenant_id, status, plan, features, created_at, updated_at }

□ GET  /mt/tenant/{id}/usage?period=YYYY-MM
  응답: { tenant_id, period, usage: { active_users, ... } }

□ GET  /mt/tenant/{id}/lrs?from=YYYY-MM-DD&to=YYYY-MM-DD
  응답: { tenant_id, period, total_statements, statements, pagination }

□ GET  /mt/tenant/{id}/analytics?period=YYYY-MM
  응답: { tenant_id, period, summary, engagement, learning_outcomes, ai_usage }

□ GET  /mt/tenants/lrs (Market 전용)
  응답: { period, tenants: [...], total_statements_all }

□ GET  /mt/tenants/analytics (Market 전용)
  응답: { period, overall_summary, tenants: [...], rankings }
```

## 13. 코드 예시

### 13.1 FastAPI 프로젝트 구조

```
my_ai_service/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱
│   ├── config.py               # 설정
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── mt_api.py           # 표준 MT API (9개)
│   │   └── service_api.py      # 서비스 비즈니스 API
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tenant_manager.py   # 테넌트 DB 관리
│   │   ├── lrs_service.py      # LRS 서비스
│   │   └── analytics_service.py # 분석 서비스
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── tenant.py           # 테넌트 모델
│   │   └── schemas.py          # Pydantic 스키마
│   │
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py             # 인증 미들웨어
│       └── tenant_context.py   # 테넌트 컨텍스트
│
├── manifest.yaml               # MT PaaS manifest
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

### 13.2 main.py 예시

```python
# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import mt_api, service_api
from app.middleware.tenant_context import TenantMiddleware
from app.config import settings

app = FastAPI(
    title="My AI Service",
    version="1.0.0",
    description="AI 기반 학습 서비스"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 테넌트 컨텍스트 미들웨어
app.add_middleware(TenantMiddleware)

# MT 표준 API
app.include_router(mt_api.router, tags=["MT Standard API"])

# 서비스 비즈니스 API
app.include_router(service_api.router, prefix="/{tenant_id}", tags=["Service API"])

@app.on_event("startup")
async def startup():
    # DB 연결 초기화
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
```

---

## 14. 자주 묻는 질문

### Q1. 기존 서비스에 MT PaaS를 어떻게 적용하나요?

**A:** 단계별로 적용합니다:

1. Central DB에 테넌트 관리 테이블 추가
2. 기존 단일 DB를 테넌트별 DB로 분리 (데이터 마이그레이션)
3. 9개 표준 API 엔드포인트 추가
4. 테넌트 컨텍스트 미들웨어 적용
5. manifest.yaml 작성 후 Market에 등록

### Q2. 테넌트별 DB 분리가 꼭 필요한가요?

**A:** 권장되지만 필수는 아닙니다. Schema-per-tenant 방식도 가능합니다:

```sql
-- Schema-per-tenant 방식
CREATE SCHEMA tenant_hallym;
CREATE SCHEMA tenant_korea;

-- 각 스키마에 동일한 테이블 구조
CREATE TABLE tenant_hallym.users (...);
CREATE TABLE tenant_korea.users (...);
```

### Q3. LRS 데이터는 어느 정도 보관해야 하나요?

**A:** manifest.yaml의 `lrs_config.retention_days`로 설정합니다. 일반적으로:

- 기본: 365일 (1년)
- 연구용: 1825일 (5년)
- 법적 요구사항에 따라 조정

### Q4. Market에서 전체 데이터를 조회하면 성능 문제가 없나요?

**A:** 대용량 데이터의 경우:

1. `summary_only=true` 파라미터로 요약만 조회
2. 페이지네이션 적용
3. 사전 집계된 analytics_daily 테이블 활용
4. 캐싱 적용

### Q5. 대학별 인증은 어떻게 구현하나요?

**A:** 서비스 업체가 선택하여 구현합니다:

1. **자체 로그인**: 서비스에서 직접 사용자 관리
2. **대학 SSO 연동**: OAuth2/SAML로 대학 인증 시스템 연동
3. **하이브리드**: 대학 SSO + 서비스 보조 인증

---

**문서 끝**
