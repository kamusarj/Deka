import asyncio
import json
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import select
from app.models.ai_account import AIUsage
from app.services.ai.errors import AIError
from app.services.ai.gateway import AIGateway, usage_sink
from app.services.ai.operations import BillableOperation, billable_stream
from tests.test_ai_credits import accounts, assert_balance, record_call  # shared isolated DB fixture
from tests.test_ai_gateway import Transport

@pytest.mark.asyncio
async def test_http_success_tracks_thread_context_and_charges(accounts):
    billing = BillableOperation(1, credits=accounts)
    async def invoke():
        await asyncio.to_thread(AIGateway().generate, prompt='private', provider='openai', service=Transport())
        return {'publication_status': 'verified'}
    await billing.run(invoke)
    assert usage_sink.get() is None
    assert_balance(accounts, 40)

@pytest.mark.asyncio
async def test_http_provider_failure_refunds(accounts):
    billing = BillableOperation(1, credits=accounts)
    class Broken(Transport):
        def generate_text(self, prompt):
            raise TimeoutError('secret')
    async def invoke():
        return await asyncio.to_thread(AIGateway().generate, prompt='private', provider='gemini', service=Broken())
    with pytest.raises(AIError):
        await billing.run(invoke)
    assert_balance(accounts, 50)
    with accounts.sessions() as db:
        rows = db.scalars(select(AIUsage)).all()
        assert len(rows) == 2 and all(row.status == 'failed' for row in rows)

@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['verified', 'draft_unverified'])
async def test_stream_settles_only_verified_results(accounts, status):
    async def source():
        AIGateway().generate(prompt='private', provider='openai', service=Transport())
        yield 'data: ' + json.dumps({'type': 'result', 'payload': {'publication_status': status}}) + '\n\n'
    events = [event async for event in billable_stream(NS(id=1), source, accounts)]
    assert json.loads(events[0][6:])['request_id']
    assert_balance(accounts, 40 if status == 'verified' else 50)

@pytest.mark.asyncio
async def test_sse_error_event_is_failure_even_without_exception(accounts):
    async def source():
        AIGateway().generate(prompt='private', provider='openai', service=Transport())
        yield 'data: {"stage":"error","status":"error","message":"failed"}\n\n'
    events = [event async for event in billable_stream(NS(id=1), source, accounts)]
    assert 'error' in events[0]
    assert_balance(accounts, 50)

@pytest.mark.asyncio
async def test_disconnect_closes_generator_and_refunds(accounts):
    closed = []
    async def source():
        try:
            AIGateway().generate(prompt='private', provider='openai', service=Transport())
            yield 'data: {"stage":"running"}\n\n'
            await asyncio.sleep(30)
        finally:
            closed.append(True)
    stream = billable_stream(NS(id=1), source, accounts)
    await anext(stream)
    await stream.aclose()
    assert closed == [True]
    assert usage_sink.get() is None
    assert_balance(accounts, 50)

@pytest.mark.asyncio
async def test_cancellation_and_late_sdk_result_never_recharge(accounts):
    import threading
    started, release = threading.Event(), threading.Event()
    class Slow(Transport):
        def generate_text(self, prompt):
            from app.services import ai_runtime
            with ai_runtime.track_call('openai', self.model, 'test') as slot:
                started.set()
                release.wait(5)
                slot['response'] = NS(id='late', usage=NS(input_tokens=100, output_tokens=20))
            return 'generated'
    billing = BillableOperation(1, credits=accounts)
    async def invoke():
        return await asyncio.to_thread(AIGateway().generate, prompt='private', provider='openai', service=Slow())
    task = asyncio.create_task(billing.run(invoke))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert_balance(accounts, 50)
    release.set()
    # A worker is still finishing the request after the awaiting task was cancelled.
    for _ in range(100):
        await asyncio.sleep(.01)
        with accounts.sessions() as db:
            row = db.scalar(select(AIUsage).where(AIUsage.record_kind == 'provider'))
            if row:
                assert row.status == 'late_success'
                break
    else:
        pytest.fail('worker did not record usage')
    assert_balance(accounts, 50)
    with accounts.sessions() as db:
        summary = db.get(AIUsage, billing.request_id)
        assert summary.status == 'failed' and summary.input_tokens == 100

@pytest.mark.asyncio
async def test_sse_insufficient_balance_never_starts_rag(accounts):
    accounts.adjust(1, reset_to=0)
    async def source():
        pytest.fail('RAG must not start')
        yield ''
    events = [event async for event in billable_stream(NS(id=1), source, accounts)]
    assert json.loads(events[0][6:])['code'] == 'INSUFFICIENT_CREDITS'

@pytest.mark.asyncio
async def test_swallowed_accounting_failure_cannot_charge_success(accounts):
    billing = BillableOperation(1, credits=accounts)
    async def invoke():
        # A compatibility fallback must not hide a failed usage write.
        billing.recorder.failed = True
        return {'publication_status': 'verified'}
    with pytest.raises(AIError) as caught:
        await billing.run(invoke)
    assert caught.value.code == 'AI_ACCOUNTING_ERROR'
    assert_balance(accounts, 50)
