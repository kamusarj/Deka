"""Accounting, admission, authorization checkpoints and leases for HTTP/SSE."""
import asyncio
import hashlib
import json
import logging
from contextlib import aclosing, asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings
from app.models.ai_account import AIUsage
from app.models.user import User
from app.services.ai.credits import CreditService, RequestReplay
from app.services.ai import admission
from app.services.ai.errors import AIError, normalize_error
from app.services.ai.gateway import usage_sink
from app.services.ai.lifecycle import active_operation, check_authority
from app.services.ai.usage import UsageRecorder

logger = logging.getLogger('app.ai')


def verified(result):
    status = result.get('publication_status', 'verified') if isinstance(result, dict) else getattr(result, 'publication_status', 'verified')
    return status == 'verified'


def input_fingerprint(payload):
    if hasattr(payload, 'model_dump'):
        payload = payload.model_dump(mode='json')
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class BillableOperation:
    def __init__(self, user_id, operation='exam_generation', credits=None, *, actor=None, idempotency_key=None, payload=None):
        self.credits = credits or CreditService()
        self.user_id, self.operation = user_id, operation
        self.document_ids = set((payload.get('document_ids') if isinstance(payload, dict) else getattr(payload, 'document_ids', None)) or [])
        self.actor_snapshot = (actor.role, getattr(actor, 'school_id', None), getattr(actor, 'token_version', 0)) if actor and hasattr(actor, 'role') else None
        # Release the authentication read transaction before waiting on SDKs.
        # The detached snapshot is never authority: checkpoints query current rows.
        from sqlalchemy import inspect
        state = inspect(actor, raiseerr=False) if actor is not None else None
        auth_session = state.session if state is not None else None
        if auth_session is not None:
            if auth_session.new or auth_session.dirty or auth_session.deleted:
                raise AIError('AI_ACCOUNTING_ERROR', 503)
            auth_session.expunge(actor)
            auth_session.rollback()
        self.lease_owner = str(uuid4())
        fingerprint = input_fingerprint(payload) if idempotency_key else None
        if idempotency_key:
            with self.credits.sessions() as db:
                previous = db.scalar(select(AIUsage).where(AIUsage.user_id == user_id,
                    AIUsage.operation == operation, AIUsage.idempotency_key == idempotency_key))
                if previous:
                    if previous.input_fingerprint != fingerprint:
                        raise AIError('AI_IDEMPOTENCY_CONFLICT', 409)
                    raise RequestReplay(previous.id)
        admission.acquire(user_id, operation)
        self.released = False
        try:
            self.request_id = self.credits.reserve(user_id, operation, lease_owner=self.lease_owner,
                                                  idempotency_key=idempotency_key, fingerprint=fingerprint)
        except BaseException:
            self.release()
            raise
        self.started, self.closed, self.result_committed = perf_counter(), False, False
        self.recorder = UsageRecorder(self.credits.sessions, user_id, self.request_id, operation)

    def persisted_status(self):
        with self.credits.sessions() as db:
            row = db.get(AIUsage, self.request_id)
            return row.status if row else None

    def release(self):
        if not self.released:
            self.released = True
            admission.release(self.user_id)

    def checkpoint(self):
        with self.credits.sessions() as db:
            actor = check_authority(db, self)
            if self.actor_snapshot is None:
                self.actor_snapshot = (actor.role, actor.school_id, actor.token_version)

    def persist(self, db, exam):
        """Caller owns commit: result pointer, exam and settlement commit together."""
        check_authority(db, self, lock=True)
        if self.recorder.failed:
            raise AIError('AI_ACCOUNTING_ERROR', 503)
        db.flush()
        request = db.get(AIUsage, self.request_id)
        request.result_exam_id, request.result_version = exam.id, exam.version_id
        if not self.credits.finish_in_transaction(db, self.request_id, success=verified(exam),
                error_code=None if verified(exam) else 'AI_INVALID_RESPONSE', lease_owner=self.lease_owner,
                latency_ms=round((perf_counter() - self.started) * 1000)):
            raise AIError('AI_REQUEST_FENCED', 409)

    def finish(self, success, error_code=None):
        if self.closed:
            return
        if not self.result_committed:
            with self.credits.sessions.begin() as db:
                if success:
                    check_authority(db, self, lock=True)
                changed = self.credits.finish_in_transaction(db, self.request_id, success=success,
                    latency_ms=round((perf_counter() - self.started) * 1000),
                    error_code=error_code, lease_owner=self.lease_owner)
                if success and not changed:
                    raise AIError('AI_REQUEST_FENCED', 409)
        self.closed = True
        logger.info('ai_request request_id=%s user_id=%s operation=%s status=%s',
                    self.request_id, self.user_id, self.operation, 'success' if success else 'failed')

    @asynccontextmanager
    async def context(self):
        sink_token = usage_sink.set(self.recorder)
        context_token = active_operation.set(self)
        async def heartbeat():
            while True:
                await asyncio.sleep(settings.AI_LEASE_SECONDS / 3)
                if not await asyncio.to_thread(self.credits.heartbeat, self.request_id, self.lease_owner):
                    return
        pulse = asyncio.create_task(heartbeat())
        try:
            self.checkpoint()
            async with asyncio.timeout(settings.AI_OPERATION_TIMEOUT_SECONDS):
                yield
        finally:
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
            active_operation.reset(context_token)
            usage_sink.reset(sink_token)
            self.release()

    async def run(self, invoke):
        try:
            async with self.context():
                result = await invoke()
                if self.recorder.failed:
                    raise AIError('AI_ACCOUNTING_ERROR', 503)
                self.finish(verified(result), None if verified(result) else 'AI_INVALID_RESPONSE')
                return result
        except BaseException as error:
            code = 'AI_CANCELLED' if isinstance(error, asyncio.CancelledError) else normalize_error(error).code
            self.finish(False, code)
            raise
        finally:
            self.release()


def replay_result(user, request_id, credits=None):
    credits = credits or CreditService()
    with credits.sessions() as db:
        request = db.scalar(select(AIUsage).where(AIUsage.id == request_id, AIUsage.user_id == user.id))
        if request is None:
            raise HTTPException(404, 'Không tìm thấy yêu cầu')
        if request.result_exam_id is not None:
            from app.models.exam import Exam
            from app.services.authorization import require_resource_access
            from app.services.exam.serializers import to_full_response
            actor = db.get(User, user.id, populate_existing=True)
            if actor is None or not actor.is_active or actor.deleted_at:
                raise HTTPException(403, 'Tài khoản không hoạt động')
            exam = db.get(Exam, request.result_exam_id)
            if exam is None:
                raise HTTPException(404, 'Kết quả đã được xóa')
            require_resource_access(exam, actor)
            if exam.version_id == request.result_version:
                return to_full_response(exam)
        raise HTTPException(409, {'message': 'Yêu cầu này đã được ghi nhận. Xem trạng thái trong lịch sử sử dụng trước khi tạo yêu cầu mới.', 'code': 'AI_REQUEST_EXISTS', 'request_id': request.id,
                                 'status': request.status, 'result_exam_id': request.result_exam_id})


async def run_billable(user, invoke, operation='exam_generation', *, idempotency_key=None, payload=None):
    if active_operation.get() is not None:
        return await invoke()
    try:
        billing = BillableOperation(user.id, operation, actor=user, idempotency_key=idempotency_key, payload=payload)
    except RequestReplay as replay:
        return replay_result(user, replay.request_id)
    return await billing.run(invoke)


async def billable_stream(user, invoke, credits=None, *, idempotency_key=None, payload=None):
    billing = None
    try:
        try:
            billing = BillableOperation(user.id, credits=credits, actor=user, idempotency_key=idempotency_key, payload=payload)
        except RequestReplay as replay:
            result = replay_result(user, replay.request_id, credits)
            from app.api.response_privacy import content_projection
            payload = result.model_dump(mode='json')
            if getattr(user, 'role', None) != 'super_admin':
                payload = content_projection(payload)
            yield 'data: ' + json.dumps({'type': 'result', 'request_id': replay.request_id, 'payload': payload}) + '\n\n'
            return
        async with billing.context():
            async with aclosing(invoke()) as source:
                async for event in source:
                    if event.startswith('data: '):
                        data = json.loads(event[6:])
                        if data.get('type') == 'result':
                            if billing.recorder.failed:
                                raise AIError('AI_ACCOUNTING_ERROR', 503)
                            success = verified(data.get('payload', {}))
                            billing.finish(success, None if success else 'AI_INVALID_RESPONSE')
                        elif data.get('stage') == 'error' or data.get('status') == 'error':
                            billing.finish(False, data.get('code') or 'AI_PROVIDER_ERROR')
                            data['request_status'] = billing.persisted_status()
                        if getattr(user, 'role', None) != 'super_admin':
                            from app.api.response_privacy import content_projection
                            data = content_projection(data)
                        data['request_id'] = billing.request_id
                        event = f'data: {json.dumps(data, ensure_ascii=False)}\n\n'
                    yield event
    except (HTTPException, TimeoutError) as error:
        code = normalize_error(error).code
        if billing:
            billing.finish(False, code)
        detail = error.detail if isinstance(error, HTTPException) else normalize_error(error).detail
        if not isinstance(detail, dict):
            detail = {'message': detail, 'code': code}
        if billing:
            detail = {**detail, 'request_id': billing.request_id, 'request_status': billing.persisted_status()}
        elif detail.get('code') == 'AI_REQUEST_EXISTS':
            detail = {**detail, 'request_status': detail.get('status')}
        yield f'data: {json.dumps({**detail, "stage": "error", "status": "error"}, ensure_ascii=False)}\n\n'
    finally:
        if billing:
            try:
                billing.finish(False, 'AI_CANCELLED')
            finally:
                billing.release()
