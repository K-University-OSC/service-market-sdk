#!/bin/bash
#
# Service Market Webhook 테스트 스크립트
#
# 사용법:
#   ./test_webhook.sh http://localhost:8000
#   ./test_webhook.sh http://localhost:8000 my_api_key
#

SERVICE_URL="${1:-http://localhost:8000}"
API_KEY="${2:-mt_dev_key_12345}"
WEBHOOK_PATH="/api/tenant/webhook/auto-provision"

echo "=============================================="
echo "Service Market Webhook 테스트"
echo "=============================================="
echo "서비스 URL: $SERVICE_URL"
echo "API Key: $API_KEY"
echo "----------------------------------------------"

# 1. 헬스체크
echo ""
echo "[1/5] 헬스체크 테스트..."
HEALTH=$(curl -s -w "\n%{http_code}" "$SERVICE_URL/health")
HEALTH_CODE=$(echo "$HEALTH" | tail -1)
HEALTH_BODY=$(echo "$HEALTH" | head -n -1)

if [ "$HEALTH_CODE" = "200" ]; then
    echo "  [PASS] 헬스체크 성공"
    echo "  응답: $HEALTH_BODY"
else
    echo "  [FAIL] 헬스체크 실패 (HTTP $HEALTH_CODE)"
fi

# 2. Webhook 기본 테스트
echo ""
echo "[2/5] Webhook 기본 테스트..."
WEBHOOK_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$SERVICE_URL$WEBHOOK_PATH" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{
        "application_id": 8001,
        "kind": "demo",
        "contact": "02-1234-5678",
        "reason": "테스트 신청",
        "applicant": {
            "id": 1,
            "name": "테스터",
            "email": "test1@university.ac.kr",
            "university_name": "테스트대학교"
        },
        "service": {
            "id": 1,
            "slug": "test-service",
            "title": "Test Service"
        }
    }')

WEBHOOK_CODE=$(echo "$WEBHOOK_RESULT" | tail -1)
WEBHOOK_BODY=$(echo "$WEBHOOK_RESULT" | head -n -1)

if [ "$WEBHOOK_CODE" = "200" ]; then
    echo "  [PASS] Webhook 성공"
    echo "  응답: $WEBHOOK_BODY"
else
    echo "  [FAIL] Webhook 실패 (HTTP $WEBHOOK_CODE)"
    echo "  응답: $WEBHOOK_BODY"
fi

# 3. API Key 검증 테스트
echo ""
echo "[3/5] API Key 검증 테스트 (잘못된 키)..."
INVALID_KEY_RESULT=$(curl -s -w "\n%{http_code}" -X POST "$SERVICE_URL$WEBHOOK_PATH" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: invalid_key" \
    -d '{"application_id": 8002, "kind": "demo", "applicant": {"email": "x@x.com"}, "service": {"id": 1}}')

INVALID_CODE=$(echo "$INVALID_KEY_RESULT" | tail -1)

if [ "$INVALID_CODE" = "401" ]; then
    echo "  [PASS] 잘못된 API Key 거부됨 (HTTP 401)"
else
    echo "  [FAIL] API Key 검증 실패 (예상: 401, 실제: $INVALID_CODE)"
fi

# 4. 테넌트 재사용 테스트
echo ""
echo "[4/5] 테넌트 재사용 테스트..."
REUSE_EMAIL="reuse_test_$(date +%s)@university.ac.kr"

# 첫 번째 신청
FIRST=$(curl -s -X POST "$SERVICE_URL$WEBHOOK_PATH" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
        \"application_id\": 8003,
        \"kind\": \"demo\",
        \"applicant\": {
            \"id\": 1,
            \"name\": \"재사용테스트\",
            \"email\": \"$REUSE_EMAIL\",
            \"university_name\": \"재사용대학교\"
        },
        \"service\": {\"id\": 1, \"slug\": \"test\", \"title\": \"Test\"}
    }")

FIRST_TENANT=$(echo "$FIRST" | grep -o '"tenant_id":"[^"]*"' | cut -d'"' -f4)

# 두 번째 신청 (같은 이메일)
SECOND=$(curl -s -X POST "$SERVICE_URL$WEBHOOK_PATH" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
        \"application_id\": 8004,
        \"kind\": \"service\",
        \"applicant\": {
            \"id\": 1,
            \"name\": \"재사용테스트\",
            \"email\": \"$REUSE_EMAIL\",
            \"university_name\": \"재사용대학교\"
        },
        \"service\": {\"id\": 1, \"slug\": \"test\", \"title\": \"Test\"}
    }")

SECOND_TENANT=$(echo "$SECOND" | grep -o '"tenant_id":"[^"]*"' | cut -d'"' -f4)

if [ "$FIRST_TENANT" = "$SECOND_TENANT" ] && [ -n "$FIRST_TENANT" ]; then
    echo "  [PASS] 테넌트 재사용 성공"
    echo "  첫 번째 tenant_id: $FIRST_TENANT"
    echo "  두 번째 tenant_id: $SECOND_TENANT"
else
    echo "  [FAIL] 테넌트 재사용 실패"
    echo "  첫 번째 tenant_id: $FIRST_TENANT"
    echo "  두 번째 tenant_id: $SECOND_TENANT"
fi

# 5. 응답 형식 검증
echo ""
echo "[5/5] 응답 형식 검증..."

# 필수 필드 확인
if echo "$WEBHOOK_BODY" | grep -q '"status"'; then
    echo "  [OK] status 필드 있음"
else
    echo "  [FAIL] status 필드 없음"
fi

if echo "$WEBHOOK_BODY" | grep -q '"tenant_id"'; then
    echo "  [OK] tenant_id 필드 있음"
else
    echo "  [FAIL] tenant_id 필드 없음"
fi

if echo "$WEBHOOK_BODY" | grep -q '"tenant_url"'; then
    echo "  [OK] tenant_url 필드 있음"
else
    echo "  [FAIL] tenant_url 필드 없음"
fi

if echo "$WEBHOOK_BODY" | grep -q '"message"'; then
    echo "  [OK] message 필드 있음"
else
    echo "  [FAIL] message 필드 없음"
fi

echo ""
echo "=============================================="
echo "테스트 완료"
echo "=============================================="
