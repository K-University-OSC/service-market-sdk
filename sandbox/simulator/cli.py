#!/usr/bin/env python3
"""
Service Market Simulator CLI

서비스 마켓 시뮬레이터를 커맨드라인에서 사용할 수 있습니다.

Usage:
    # 서버 실행
    python -m sandbox.simulator.cli serve --port 9000

    # 데모 신청 테스트 (한 줄로)
    python -m sandbox.simulator.cli demo \
        --target http://localhost:8000/api/tenant/webhook/auto-provision \
        --email test@seoul.ac.kr

    # 서비스 신청 테스트
    python -m sandbox.simulator.cli service \
        --target http://localhost:8000/api/tenant/webhook/auto-provision \
        --email admin@yonsei.ac.kr \
        --start-date 2026-02-01 \
        --end-date 2026-12-31

    # 신청 목록 조회
    python -m sandbox.simulator.cli applications --kind demo

    # 결과 조회
    python -m sandbox.simulator.cli results --limit 10

    # 통계 조회
    python -m sandbox.simulator.cli stats
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .database import get_database
from .application_manager import ApplicationManager
from .result_store import ResultStore


# 기본 설정
DEFAULT_DB_PATH = "simulator.db"
DEFAULT_API_KEY = "mt_dev_key_12345"


def print_json(data: dict, indent: int = 2):
    """JSON 출력"""
    print(json.dumps(data, ensure_ascii=False, indent=indent, default=str))


def print_table(headers: list, rows: list, widths: Optional[list] = None):
    """간단한 테이블 출력"""
    if not widths:
        widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(len(headers))]

    # 헤더
    header_line = "".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("-" * len(header_line))

    # 행
    for row in rows:
        print("".join(str(c).ljust(w) for c, w in zip(row, widths)))


async def send_webhook(
    target_url: str,
    payload: dict,
    api_key: str = DEFAULT_API_KEY
) -> tuple[int, Optional[dict], float, Optional[str]]:
    """웹훅 전송"""
    start = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                target_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": api_key
                }
            )
            elapsed = (datetime.now() - start).total_seconds() * 1000

            response_data = None
            try:
                response_data = response.json()
            except:
                pass

            return response.status_code, response_data, elapsed, None

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds() * 1000
        return 0, None, elapsed, str(e)


def cmd_serve(args):
    """서버 실행"""
    import uvicorn
    from .webhook_simulator import app, init_simulator

    init_simulator(args.db)
    print(f"Starting Service Market Simulator on http://{args.host}:{args.port}")
    print(f"Database: {args.db}")
    print(f"API Docs: http://{args.host}:{args.port}/docs")
    print()

    uvicorn.run(app, host=args.host, port=args.port)


def cmd_demo(args):
    """데모 신청 및 웹훅 전송"""
    db = get_database(args.db)
    manager = ApplicationManager(db)
    store = ResultStore(db)

    # 신청 생성
    app = manager.create_demo_application(
        applicant_email=args.email,
        applicant_name=args.name,
        university_name=args.university,
        service_slug=args.service_slug,
        service_title=args.service_title
    )

    print(f"Demo application created:")
    print(f"  ID: {app.id}")
    print(f"  Application ID: {app.application_id}")
    print(f"  Email: {app.applicant_email}")
    print(f"  University: {app.university_name}")
    print(f"  Period: {app.start_date} ~ {app.end_date}")
    print()

    # 웹훅 전송
    if args.target:
        print(f"Sending webhook to: {args.target}")
        payload = app.to_webhook_payload()

        status_code, response_body, response_time, error = asyncio.run(
            send_webhook(args.target, payload, args.api_key)
        )

        # 결과 저장
        result = store.save_result(
            application_id=app.id,
            target_url=args.target,
            request_payload=payload,
            response_code=status_code,
            response_body=response_body,
            response_time_ms=response_time,
            api_key=args.api_key,
            error=error
        )

        # 상태 업데이트
        if result.success:
            if response_body and response_body.get("status") == "approved":
                manager.update_status(app.id, "completed")
            else:
                manager.update_status(app.id, "sent")
        else:
            manager.update_status(app.id, "failed")

        print()
        print(f"Webhook Result:")
        print(f"  Success: {result.success}")
        print(f"  Status Code: {status_code}")
        print(f"  Response Time: {response_time:.2f}ms")

        if error:
            print(f"  Error: {error}")
        elif response_body:
            print(f"  Response:")
            print_json(response_body)
    else:
        print("No target URL specified. Use --target to send webhook.")

    db.close()


def cmd_service(args):
    """서비스 신청 및 웹훅 전송"""
    db = get_database(args.db)
    manager = ApplicationManager(db)
    store = ResultStore(db)

    # 신청 생성
    app = manager.create_service_application(
        applicant_email=args.email,
        applicant_name=args.name,
        university_name=args.university,
        start_date=args.start_date,
        end_date=args.end_date,
        service_slug=args.service_slug,
        service_title=args.service_title
    )

    print(f"Service application created:")
    print(f"  ID: {app.id}")
    print(f"  Application ID: {app.application_id}")
    print(f"  Email: {app.applicant_email}")
    print(f"  University: {app.university_name}")
    print(f"  Period: {app.start_date} ~ {app.end_date}")
    print()

    # 웹훅 전송
    if args.target:
        print(f"Sending webhook to: {args.target}")
        payload = app.to_webhook_payload()

        status_code, response_body, response_time, error = asyncio.run(
            send_webhook(args.target, payload, args.api_key)
        )

        # 결과 저장
        result = store.save_result(
            application_id=app.id,
            target_url=args.target,
            request_payload=payload,
            response_code=status_code,
            response_body=response_body,
            response_time_ms=response_time,
            api_key=args.api_key,
            error=error
        )

        # 상태 업데이트
        if result.success:
            if response_body and response_body.get("status") == "approved":
                manager.update_status(app.id, "completed")
            else:
                manager.update_status(app.id, "sent")
        else:
            manager.update_status(app.id, "failed")

        print()
        print(f"Webhook Result:")
        print(f"  Success: {result.success}")
        print(f"  Status Code: {status_code}")
        print(f"  Response Time: {response_time:.2f}ms")

        if error:
            print(f"  Error: {error}")
        elif response_body:
            print(f"  Response:")
            print_json(response_body)
    else:
        print("No target URL specified. Use --target to send webhook.")

    db.close()


def cmd_applications(args):
    """신청 목록 조회"""
    db = get_database(args.db)
    manager = ApplicationManager(db)

    apps = manager.list_applications(
        kind=args.kind,
        status=args.status,
        limit=args.limit
    )

    if not apps:
        print("No applications found.")
        db.close()
        return

    if args.json:
        print_json([app.to_dict() for app in apps])
    else:
        headers = ["ID", "App ID", "Kind", "Status", "Email", "University", "Created"]
        rows = [
            [
                app.id,
                app.application_id,
                app.kind,
                app.status,
                app.applicant_email[:25] + "..." if len(app.applicant_email) > 28 else app.applicant_email,
                app.university_name[:15] + "..." if len(app.university_name) > 18 else app.university_name,
                app.created_at[:19]
            ]
            for app in apps
        ]
        print_table(headers, rows)

    print(f"\nTotal: {len(apps)} applications")
    db.close()


def cmd_results(args):
    """결과 조회"""
    db = get_database(args.db)
    store = ResultStore(db)

    if args.application_id:
        results = store.get_results_for_application(args.application_id)
    else:
        results = store.get_latest_results(args.limit)

    if not results:
        print("No results found.")
        db.close()
        return

    if args.json:
        print_json([r.to_response().dict() for r in results])
    else:
        headers = ["ID", "App ID", "Success", "Status", "Tenant ID", "Time(ms)", "Created"]
        rows = [
            [
                r.id,
                r.application_id,
                "Yes" if r.success else "No",
                r.webhook_status or "-",
                r.tenant_id or "-",
                f"{r.response_time_ms:.1f}",
                r.created_at[:19]
            ]
            for r in results
        ]
        print_table(headers, rows)

    print(f"\nTotal: {len(results)} results")
    db.close()


def cmd_stats(args):
    """통계 조회"""
    db = get_database(args.db)
    store = ResultStore(db)

    stats = store.get_statistics()

    if args.json:
        print_json(stats.dict())
    else:
        print("=" * 50)
        print("Service Market Simulator Statistics")
        print("=" * 50)
        print()
        print("Applications:")
        print(f"  Total: {stats.total_applications}")
        print(f"  Demo: {stats.demo_applications}")
        print(f"  Service: {stats.service_applications}")
        print()
        print("Application Status:")
        print(f"  Pending: {stats.pending_applications}")
        print(f"  Sent: {stats.sent_applications}")
        print(f"  Completed: {stats.completed_applications}")
        print(f"  Failed: {stats.failed_applications}")
        print()
        print("Webhook Calls:")
        print(f"  Total: {stats.total_webhook_calls}")
        print(f"  Successful: {stats.successful_calls}")
        print(f"  Failed: {stats.failed_calls}")
        print(f"  Success Rate: {stats.success_rate}%")
        print(f"  Avg Response Time: {stats.average_response_time_ms}ms")
        print()

    db.close()


def cmd_clear(args):
    """데이터 삭제"""
    db = get_database(args.db)

    if args.all:
        db.clear_all()
        print("All data cleared.")
    elif args.results:
        store = ResultStore(db)
        count = store.clear_all()
        print(f"Cleared {count} results.")
    else:
        print("Specify --all or --results to clear data.")

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Service Market Simulator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server
  python -m sandbox.simulator.cli serve --port 9000

  # Send demo application webhook
  python -m sandbox.simulator.cli demo \\
      --target http://localhost:8000/api/tenant/webhook/auto-provision \\
      --email test@seoul.ac.kr \\
      --university "서울대학교"

  # View statistics
  python -m sandbox.simulator.cli stats
        """
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Database path")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start simulator server")
    serve_parser.add_argument("--port", type=int, default=9000, help="Server port (default: 9000)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")

    # demo command
    demo_parser = subparsers.add_parser("demo", help="Create and send demo application")
    demo_parser.add_argument("--target", help="Target webhook URL")
    demo_parser.add_argument("--email", default="test@university.ac.kr", help="Applicant email")
    demo_parser.add_argument("--name", default="Test User", help="Applicant name")
    demo_parser.add_argument("--university", default="Test University", help="University name")
    demo_parser.add_argument("--service-slug", default="test-service", help="Service slug")
    demo_parser.add_argument("--service-title", default="Test Service", help="Service title")
    demo_parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")

    # service command
    service_parser = subparsers.add_parser("service", help="Create and send service application")
    service_parser.add_argument("--target", help="Target webhook URL")
    service_parser.add_argument("--email", required=True, help="Applicant email")
    service_parser.add_argument("--name", default="Service User", help="Applicant name")
    service_parser.add_argument("--university", default="Service University", help="University name")
    service_parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    service_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    service_parser.add_argument("--service-slug", default="test-service", help="Service slug")
    service_parser.add_argument("--service-title", default="Test Service", help="Service title")
    service_parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key")

    # applications command
    apps_parser = subparsers.add_parser("applications", help="List applications")
    apps_parser.add_argument("--kind", choices=["demo", "service"], help="Filter by kind")
    apps_parser.add_argument("--status", choices=["pending", "sent", "completed", "failed"], help="Filter by status")
    apps_parser.add_argument("--limit", type=int, default=50, help="Limit results")
    apps_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # results command
    results_parser = subparsers.add_parser("results", help="List webhook results")
    results_parser.add_argument("--application-id", type=int, help="Filter by application ID")
    results_parser.add_argument("--limit", type=int, default=50, help="Limit results")
    results_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="View statistics")
    stats_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear data")
    clear_parser.add_argument("--all", action="store_true", help="Clear all data")
    clear_parser.add_argument("--results", action="store_true", help="Clear results only")

    args = parser.parse_args()

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "demo":
        cmd_demo(args)
    elif args.command == "service":
        cmd_service(args)
    elif args.command == "applications":
        cmd_applications(args)
    elif args.command == "results":
        cmd_results(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "clear":
        cmd_clear(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
