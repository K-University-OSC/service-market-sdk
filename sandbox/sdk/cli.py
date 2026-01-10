#!/usr/bin/env python3
"""
Service Market SDK CLI

사용법:
    python -m sandbox.sdk.cli test http://localhost:8000
    python -m sandbox.sdk.cli health http://localhost:8000
    python -m sandbox.sdk.cli webhook http://localhost:8000 --kind demo
"""

import argparse
import sys
import json

from .client import ServiceMarketClient
from .tester import WebhookTester
from .validator import WebhookValidator


def cmd_test(args):
    """전체 테스트 실행"""
    tester = WebhookTester(
        service_url=args.service_url,
        api_key=args.api_key,
        webhook_path=args.webhook_path
    )

    print(f"\n테스트 대상: {args.service_url}")
    print("테스트 실행 중...")

    report = tester.run_all_tests()

    if args.json:
        print(report.to_json())
    else:
        report.print_report()

    # 실패 시 exit code 1
    return 0 if report.failed == 0 else 1


def cmd_health(args):
    """헬스체크"""
    client = ServiceMarketClient(
        service_url=args.service_url,
        api_key=args.api_key
    )

    result = client.test_health()

    if result.success:
        print(f"[OK] 서비스 정상 ({result.response_time_ms:.2f}ms)")
        if result.data:
            print(json.dumps(result.data, indent=2, ensure_ascii=False))
        return 0
    else:
        print(f"[FAIL] 서비스 연결 실패: {result.error}")
        return 1


def cmd_webhook(args):
    """Webhook 단일 테스트"""
    client = ServiceMarketClient(
        service_url=args.service_url,
        api_key=args.api_key,
        webhook_path=args.webhook_path
    )

    result = client.test_webhook(
        application_id=args.application_id,
        kind=args.kind,
        applicant_email=args.email,
        university_name=args.university
    )

    if result.success:
        print(f"[OK] Webhook 성공 ({result.response_time_ms:.2f}ms)")
        print(json.dumps(result.data, indent=2, ensure_ascii=False))

        # 응답 검증
        validator = WebhookValidator()
        validation = validator.validate_response(result.data)
        if not validation.valid:
            print(f"\n[경고] 응답 형식 문제:")
            for error in validation.errors:
                print(f"  - {error}")
        return 0
    else:
        print(f"[FAIL] Webhook 실패 (HTTP {result.status_code})")
        print(f"오류: {result.error}")
        return 1


def cmd_validate(args):
    """응답 검증"""
    validator = WebhookValidator()

    try:
        data = json.loads(args.response)
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON 파싱 오류: {e}")
        return 1

    result = validator.validate_response(data)

    print(f"\n검증 점수: {result.score}/100")
    print(f"유효성: {'OK' if result.valid else 'FAIL'}")

    if result.errors:
        print("\n오류:")
        for error in result.errors:
            print(f"  - {error}")

    if result.warnings:
        print("\n경고:")
        for warning in result.warnings:
            print(f"  - {warning}")

    return 0 if result.valid else 1


def main():
    parser = argparse.ArgumentParser(
        description="Service Market SDK - Webhook 테스트 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # 전체 테스트
  python -m sandbox.sdk.cli test http://localhost:8000

  # 헬스체크만
  python -m sandbox.sdk.cli health http://localhost:8000

  # Webhook 단일 호출
  python -m sandbox.sdk.cli webhook http://localhost:8000 --kind demo

  # JSON 출력
  python -m sandbox.sdk.cli test http://localhost:8000 --json
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # test 명령어
    test_parser = subparsers.add_parser("test", help="전체 테스트 실행")
    test_parser.add_argument("service_url", help="서비스 URL (예: http://localhost:8000)")
    test_parser.add_argument("--api-key", default="mt_dev_key_12345", help="API Key")
    test_parser.add_argument("--webhook-path", default="/api/tenant/webhook/auto-provision", help="Webhook 경로")
    test_parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")

    # health 명령어
    health_parser = subparsers.add_parser("health", help="헬스체크")
    health_parser.add_argument("service_url", help="서비스 URL")
    health_parser.add_argument("--api-key", default="mt_dev_key_12345", help="API Key")

    # webhook 명령어
    webhook_parser = subparsers.add_parser("webhook", help="Webhook 단일 테스트")
    webhook_parser.add_argument("service_url", help="서비스 URL")
    webhook_parser.add_argument("--api-key", default="mt_dev_key_12345", help="API Key")
    webhook_parser.add_argument("--webhook-path", default="/api/tenant/webhook/auto-provision", help="Webhook 경로")
    webhook_parser.add_argument("--application-id", type=int, default=9999, help="신청 ID")
    webhook_parser.add_argument("--kind", choices=["demo", "service"], default="demo", help="신청 유형")
    webhook_parser.add_argument("--email", default="test@university.ac.kr", help="신청자 이메일")
    webhook_parser.add_argument("--university", default="테스트대학교", help="대학명")

    # validate 명령어
    validate_parser = subparsers.add_parser("validate", help="응답 JSON 검증")
    validate_parser.add_argument("response", help="검증할 JSON 문자열")

    args = parser.parse_args()

    if args.command == "test":
        return cmd_test(args)
    elif args.command == "health":
        return cmd_health(args)
    elif args.command == "webhook":
        return cmd_webhook(args)
    elif args.command == "validate":
        return cmd_validate(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
