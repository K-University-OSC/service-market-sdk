# Sample AI Service

Service Market 연동을 위한 샘플 AI 서비스입니다.
개발 업체는 이 코드를 참고하여 자신의 서비스를 구현할 수 있습니다.

## 빠른 시작

```bash
# 1. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일 편집 (필요시)

# 4. 서버 실행
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

## 구현된 기능

### Webhook 엔드포인트
- `POST /api/tenant/webhook/auto-provision` - 테넌트 자동 프로비저닝

### 관리 API
- `GET /health` - 헬스체크
- `GET /api/tenant/list` - 테넌트 목록
- `GET /api/tenant/status/{tenant_id}` - 테넌트 상태
- `GET /api/applications` - 신청 목록

## Webhook 페이로드 형식

```json
{
  "application_id": 17,
  "kind": "demo",
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

## 응답 형식

```json
{
  "status": "approved",
  "tenant_id": "demo_tenant_17",
  "tenant_url": "http://your-service.com/?tenant=demo_tenant_17",
  "message": "테넌트 '서울대학교' 생성 완료",
  "expires_at": "2026-12-31T23:59:59"
}
```

## 주요 구현 사항

1. **API Key 검증**: `X-API-Key` 헤더로 인증
2. **테넌트 재사용**: 동일 이메일은 기존 테넌트 재사용
3. **신청 내역 저장**: 모든 신청은 별도 저장
4. **만료일 계산**: demo는 30일, service는 end_date 기준

## 참고 문서

- [AI Service Quick Start](../../docs/AI_SERVICE_QUICKSTART.md)
- [Service Market 데이터 흐름](../../docs/AI_SERVICE_QUICKSTART.md#11-service-market--ai-service-데이터-흐름)
