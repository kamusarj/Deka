"""Sanitized application errors; never carry provider payloads to callers."""
from fastapi import HTTPException


class AccountingError(RuntimeError):
    """Fail closed on usage storage failure; never trigger provider failover."""


class AIError(HTTPException):
    def __init__(self, code: str, status_code: int = 502, message: str | None = None):
        self.code = code
        messages = {
            'AI_PROVIDER_NOT_ALLOWED': 'Provider này chưa được phép sử dụng.',
            'AI_OPERATION_NOT_CONFIGURED': 'Thao tác AI chưa được cấu hình.',
            'AI_CREDIT_CONFIGURATION_ERROR': 'Cấu hình credit không hợp lệ.',
            'AI_CAPACITY_EXCEEDED': 'AI đang bận. Vui lòng thử lại sau.',
            'AI_ADMISSION_CLOSED': 'AI đang tạm dừng nhận yêu cầu mới.',
            'AI_BUDGET_EXCEEDED': 'Đã đạt giới hạn AI trong ngày.',
            'AI_IDEMPOTENCY_CONFLICT': 'Mã yêu cầu đã được sử dụng với đầu vào khác.',
            'AI_AUTHORIZATION_CHANGED': 'Quyền sử dụng đã thay đổi; tác vụ đã dừng.',
            'AI_REQUEST_FENCED': 'Yêu cầu không còn quyền xử lý.',
            'AI_RATE_LIMITED': 'AI đang giới hạn yêu cầu. Vui lòng thử lại sau.',
            'AI_TIMEOUT': 'AI xử lý quá thời gian cho phép.',
            'AI_AUTH_ERROR': 'Chưa cấu hình thông tin xác thực AI hợp lệ.',
            'AI_INVALID_RESPONSE': 'AI trả về nội dung không hợp lệ.',
            'AI_PROVIDER_ERROR': 'Dịch vụ AI chưa thể xử lý yêu cầu.',
            'AI_ACCOUNTING_ERROR': 'Không thể ghi nhận lượt sử dụng AI. Vui lòng thử lại sau.',
            'INSUFFICIENT_CREDITS': 'Tài khoản không đủ credit để tạo đề.',
            'SUBSCRIPTION_INACTIVE': 'Gói sử dụng đã hết hạn hoặc không hoạt động.',
        }
        super().__init__(status_code, detail=message or {'code': code, 'message': messages.get(code, code)},
                         headers={'X-AI-Error-Code': code})


def normalize_error(error: Exception) -> AIError:
    if isinstance(error, AIError):
        return error
    if isinstance(error, AccountingError):
        return AIError('AI_ACCOUNTING_ERROR', 503)
    cause = error.__cause__ or error
    status = getattr(error, 'status_code', None) or getattr(cause, 'status_code', None)
    name = type(cause).__name__
    if status == 429 or name == 'RateLimitError':
        return AIError('AI_RATE_LIMITED', 429)
    if isinstance(cause, TimeoutError) or 'Timeout' in name or status in {408, 504}:
        return AIError('AI_TIMEOUT', 504)
    if status in {400, 401, 403}:
        return AIError('AI_AUTH_ERROR', 503)
    if isinstance(error, (ValueError, IndexError, TypeError)):
        return AIError('AI_INVALID_RESPONSE')
    return AIError('AI_PROVIDER_ERROR')
