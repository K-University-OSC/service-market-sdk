# Service Market Sandbox

Service Market 연동을 검증하기 위한 샌드박스 환경입니다.
개발 업체는 이 도구들을 사용하여 자체적으로 Service Market 연동을 테스트하고 검증할 수 있습니다.

## 구성

```
sandbox/
├── sample_service/    # 샘플 AI 서비스 (참고용)
├── sdk/               # Python SDK (테스트 도구)
├── simulator/         # Webhook 시뮬레이터
├── tests/             # 테스트 스크립트
└── README.md          # 이 문서
```

## 빠른 시작

### 1. 샘플 서비스 실행

```bash
cd sample_service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 2. SDK로 테스트

```bash
cd sdk
pip install -r requirements.txt

# 전체 테스트 실행
python -m cli test http://localhost:8000

# 헬스체크만
python -m cli health http://localhost:8000

# Webhook 단일 호출
python -m cli webhook http://localhost:8000 --kind demo
```

### 3. Bash 스크립트로 빠른 테스트

```bash
cd tests
./test_webhook.sh http://localhost:8000
```

---

## 샘플 서비스 (sample_service/)

Service Market 연동 방식을 보여주는 완전한 예제입니다.

### 주요 기능

- **Webhook 엔드포인트**: `POST /api/tenant/webhook/auto-provision`
- **API Key 인증**: `X-API-Key` 헤더로 검증
- **테넌트 재사용**: 동일 이메일은 기존 테넌트 재사용
- **관리 API**: 헬스체크, 테넌트 목록, 신청 내역

### API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |
| POST | `/api/tenant/webhook/auto-provision` | 자동 테넌트 프로비저닝 |
| GET | `/api/tenant/list` | 테넌트 목록 |
| GET | `/api/tenant/status/{tenant_id}` | 테넌트 상태 |
| GET | `/api/applications` | 신청 내역 |

### 환경 변수

```bash
# .env.example 참조
API_KEY=mt_dev_key_12345
TENANT_URL_BASE=http://your-service.com
```

---

## Python SDK (sdk/)

Webhook 연동을 테스트하기 위한 Python 도구입니다.

### 설치

```bash
pip install httpx
```

### 사용법

#### Python 코드에서 직접 사용

```python
from sdk.client import ServiceMarketClient

# 클라이언트 생성
client = ServiceMarketClient(
    service_url="http://localhost:8000",
    api_key="mt_dev_key_12345"
)

# 헬스체크
result = client.test_health()
print(f"상태: {'OK' if result.success else 'FAIL'}")

# Webhook 테스트
result = client.test_webhook(
    application_id=1001,
    kind="demo",
    applicant_email="test@university.ac.kr",
    university_name="테스트대학교"
)

if result.success:
    print(f"테넌트 ID: {result.data['tenant_id']}")
    print(f"접속 URL: {result.data['tenant_url']}")

# 전체 테스트 실행
from sdk.tester import WebhookTester

tester = WebhookTester(service_url="http://localhost:8000")
report = tester.run_all_tests()
report.print_report()
```

#### CLI 도구

```bash
# 전체 테스트 (5개 항목)
python -m cli test http://localhost:8000

# JSON 형식 출력
python -m cli test http://localhost:8000 --json

# 헬스체크
python -m cli health http://localhost:8000

# 단일 Webhook 호출
python -m cli webhook http://localhost:8000 \
    --kind demo \
    --email "test@univ.ac.kr" \
    --university "테스트대학"

# 응답 JSON 검증
python -m cli validate '{"status":"approved","tenant_id":"t1","tenant_url":"http://x.com","message":"ok"}'
```

### 테스트 항목

| # | 테스트 | 설명 |
|---|--------|------|
| 1 | 헬스체크 | `/health` 엔드포인트 응답 확인 |
| 2 | Webhook 기본 호출 | 정상 페이로드로 Webhook 호출 |
| 3 | API Key 검증 | 잘못된 API Key로 401 응답 확인 |
| 4 | 응답 형식 검증 | 필수 필드 및 형식 검증 |
| 5 | 테넌트 재사용 | 동일 이메일로 동일 테넌트 ID 반환 확인 |

---

## Webhook 시뮬레이터 (simulator/)

Service Market이 보내는 Webhook 요청을 시뮬레이션합니다.

### 실행

```bash
cd simulator
pip install -r requirements.txt
uvicorn webhook_simulator:app --host 0.0.0.0 --port 9000
```

### 사용법

```bash
# 자동 생성된 테스트 데이터로 Webhook 호출
curl -X POST "http://localhost:9000/simulate/provision" \
    -H "Content-Type: application/json" \
    -d '{"target_url": "http://localhost:8000/api/tenant/webhook/auto-provision"}'

# 커스텀 데이터로 호출
curl -X POST "http://localhost:9000/simulate/custom" \
    -H "Content-Type: application/json" \
    -d '{
        "target_url": "http://localhost:8000/api/tenant/webhook/auto-provision",
        "payload": {
            "application_id": 999,
            "kind": "demo",
            "applicant": {
                "id": 1,
                "name": "김테스트",
                "email": "test@university.ac.kr",
                "university_name": "테스트대학교"
            },
            "service": {
                "id": 1,
                "slug": "my-service",
                "title": "My AI Service"
            }
        }
    }'

# 호출 이력 조회
curl http://localhost:9000/history
```

### 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/simulate/provision` | 랜덤 데이터로 Webhook 호출 |
| POST | `/simulate/custom` | 커스텀 페이로드로 Webhook 호출 |
| GET | `/history` | 시뮬레이션 이력 조회 |

---

## 테스트 스크립트 (tests/)

### test_webhook.sh

Bash로 작성된 빠른 테스트 스크립트입니다.

```bash
# 기본 사용
./test_webhook.sh http://localhost:8000

# API Key 지정
./test_webhook.sh http://localhost:8000 my_api_key
```

**테스트 항목:**
1. 헬스체크
2. Webhook 기본 테스트
3. API Key 검증 (잘못된 키)
4. 테넌트 재사용
5. 응답 형식 검증

---

## Webhook 규격

### 요청 (Service Market → AI Service)

```http
POST /api/tenant/webhook/auto-provision
X-API-Key: mt_dev_key_12345
Content-Type: application/json
```

```json
{
    "application_id": 17,
    "kind": "demo",
    "contact": "02-1234-5678",
    "reason": "테스트 신청",
    "applicant": {
        "id": 27,
        "name": "김서울",
        "email": "seoul@university.ac.kr",
        "university_name": "서울대학교"
    },
    "service": {
        "id": 18,
        "slug": "my-service",
        "title": "My AI Service"
    },
    "start_date": "2026-01-10",
    "end_date": "2026-12-31"
}
```

### 응답 (AI Service → Service Market)

```json
{
    "status": "approved",
    "tenant_id": "demo_tenant_17",
    "tenant_url": "http://your-service.com/?tenant=demo_tenant_17",
    "message": "테넌트 '서울대학교' 생성 완료",
    "expires_at": "2026-12-31T23:59:59"
}
```

### 필드 설명

**요청 필드:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| application_id | int | ✓ | 신청 고유 ID |
| kind | string | ✓ | "demo" 또는 "service" |
| contact | string | | 담당자 연락처 |
| reason | string | | 신청 사유 |
| applicant | object | ✓ | 신청자 정보 |
| applicant.id | int | ✓ | 신청자 ID |
| applicant.name | string | ✓ | 신청자 이름 |
| applicant.email | string | ✓ | 신청자 이메일 |
| applicant.university_name | string | ✓ | 소속 대학 |
| service | object | ✓ | 서비스 정보 |
| service.id | int | ✓ | 서비스 ID |
| service.slug | string | ✓ | 서비스 슬러그 |
| service.title | string | ✓ | 서비스 제목 |
| start_date | string | | 시작일 (YYYY-MM-DD) |
| end_date | string | | 종료일 (YYYY-MM-DD) |

**응답 필드:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| status | string | ✓ | "approved", "processing", "rejected", "error" |
| tenant_id | string | ✓ | 생성/할당된 테넌트 ID |
| tenant_url | string | ✓ | 테넌트 접속 URL |
| message | string | ✓ | 처리 결과 메시지 |
| expires_at | string | | 만료일시 (ISO 8601) |

---

## 테넌트 재사용 로직

동일 이메일로 여러 번 신청할 경우 기존 테넌트를 재사용합니다:

```
1차 신청 (demo): email=kim@univ.ac.kr → tenant_id=demo_tenant_1 (신규 생성)
2차 신청 (service): email=kim@univ.ac.kr → tenant_id=demo_tenant_1 (재사용)
```

**권장 구현:**
- 신청자 이메일을 기준으로 기존 테넌트 조회
- 기존 테넌트가 있으면 재사용
- 없으면 새로 생성

---

## API Key 관리

개발 환경: `mt_dev_key_12345`

실제 서비스 연동 시에는 Service Market 관리자가 발급한 API Key를 사용합니다.

---

## 자주 묻는 질문

### Q: Webhook 호출 시 401 오류가 발생합니다
A: `X-API-Key` 헤더를 확인하세요. 개발 환경에서는 `mt_dev_key_12345`를 사용합니다.

### Q: tenant_url은 어떤 형식이어야 하나요?
A: 사용자가 직접 접속할 수 있는 URL이어야 합니다. 쿼리 파라미터나 서브도메인 방식 모두 가능합니다.
- 쿼리: `http://service.com/?tenant=xxx`
- 서브도메인: `https://xxx.service.com/`

### Q: 테넌트 재사용이 작동하지 않습니다
A: 신청자 이메일(`applicant.email`)을 기준으로 기존 테넌트를 조회하는지 확인하세요.

### Q: expires_at 필드는 필수인가요?
A: 아니오, 선택 필드입니다. 다만 포함하면 Service Market UI에서 만료일을 표시할 수 있습니다.

---

## 관련 문서

- [AI Service Quick Start](../docs/AI_SERVICE_QUICKSTART.md) - 전체 연동 가이드
- [Service Market 데이터 흐름](../docs/AI_SERVICE_QUICKSTART.md#11-service-market--ai-service-데이터-흐름) - 상세 데이터 흐름
