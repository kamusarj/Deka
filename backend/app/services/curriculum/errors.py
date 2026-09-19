class CurriculumNotFoundError(FileNotFoundError):
    """Không tìm thấy dữ liệu curriculum được yêu cầu."""


class CurriculumValidationError(ValueError):
    """Dữ liệu curriculum không hợp lệ."""
