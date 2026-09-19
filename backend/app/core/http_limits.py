"""Bound aggregate buffered bodies before parsing or reserving credit."""
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes, max_concurrent=8):
        self.app, self.max_bytes = app, max_bytes
        self.max_concurrent, self.running = max_concurrent, 0

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # ASGI runs on one event loop. No await separates admission and increment.
        if self.running >= self.max_concurrent:
            return await JSONResponse({'detail': 'Máy chủ đang bận'}, 429)(scope, receive, send)
        self.running += 1
        try:
            await self._bounded(scope, receive, send)
        finally:
            self.running -= 1

    async def _bounded(self, scope, receive, send):
        headers = dict(scope.get('headers', []))
        try:
            if int(headers.get(b'content-length', b'0')) > self.max_bytes:
                return await JSONResponse({'detail': 'Request quá lớn'}, 413)(scope, receive, send)
        except ValueError:
            return await JSONResponse({'detail': 'Content-Length không hợp lệ'}, 400)(scope, receive, send)
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > self.max_bytes:
                return await JSONResponse({'detail': 'Request quá lớn'}, 413)(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False):
                break
        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, send)
