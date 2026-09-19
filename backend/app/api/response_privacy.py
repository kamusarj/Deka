"""Remove infrastructure diagnostics from scientific content responses for teaching roles."""
import json
from fastapi.routing import APIRoute

DIAGNOSTICS = frozenset({
    'provider', 'model', 'provider_request_id', 'upstream_request_id', 'input_tokens',
    'output_tokens', 'cached_tokens', 'estimated_cost_usd', 'known_cost_usd',
    'prompt_tokens', 'completion_tokens', 'total_tokens', 'ocr_provider',
    'generation_model', 'review_model', 'embedding_model',
})


def content_projection(value):
    if isinstance(value, dict):
        # Reviewer labels identify infrastructure as well. Preserve scientific
        # findings/consensus while omitting the diagnostic label.
        hidden = DIAGNOSTICS | ({'label'} if 'provider' in value or 'model' in value else set())
        return {key: content_projection(item) for key, item in value.items() if key not in hidden}
    if isinstance(value, list):
        return [content_projection(item) for item in value]
    return value


class ContentPrivacyRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def projected(request):
            response = await handler(request)
            if getattr(request.state, 'actor_role', None) != 'super_admin' and response.media_type == 'application/json':
                body = content_projection(json.loads(response.body))
                response.body = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
                response.headers['content-length'] = str(len(response.body))
            return response
        return projected
