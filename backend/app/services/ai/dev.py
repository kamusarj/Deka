"""Local operator CLI. No public admin mutation route or payment integration."""
import argparse
import json
from sqlalchemy import select
from app.core.config import settings
from app.models.ai_account import AIUsage
from app.services.ai.credits import CreditService
from app.services.ai.pricing import PLAN_ALLOWANCES


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['show', 'grant', 'reset', 'plan', 'usage', 'recover'])
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--amount', type=int)
    parser.add_argument('--plan', choices=list(PLAN_ALLOWANCES))
    parser.add_argument('--request-id', help='Exact interrupted request; stop its worker before recovery')
    args = parser.parse_args(argv)
    if settings.ENV.strip().lower() not in {'development', 'dev', 'test', 'testing'}:
        parser.error('AI account mutation CLI is available only in development/test')
    service = CreditService()
    if args.command == 'grant':
        if args.amount is None:
            parser.error('grant requires --amount (negative values subtract)')
        result = service.adjust(args.user_id, amount=args.amount)
    elif args.command == 'reset':
        if args.amount is None:
            parser.error('reset requires --amount')
        result = service.adjust(args.user_id, reset_to=args.amount)
    elif args.command == 'plan':
        if args.plan is None:
            parser.error('plan requires --plan')
        result = service.change_plan(args.user_id, args.plan)
    elif args.command == 'recover':
        if not args.request_id:
            parser.error('recover requires --request-id; stop that worker first')
        with service.sessions() as db:
            row = db.get(AIUsage, args.request_id)
            if row is None or row.user_id != args.user_id or row.record_kind != 'request':
                parser.error('Request does not belong to this user')
        result = {'refunded': service.finish(args.request_id, success=False, error_code='AI_INTERRUPTED')}
    elif args.command == 'usage':
        with service.sessions() as db:
            rows = db.scalars(select(AIUsage).where(AIUsage.user_id == args.user_id)
                              .order_by(AIUsage.created_at.desc()).limit(100)).all()
            result = [{c.name: getattr(row, c.name) for c in row.__table__.columns} for row in rows]
    else:
        result = service.account(args.user_id)
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
