from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Họ và tên không được để trống")
        return normalized


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RegistrationResponse(BaseModel):
    email_delivery_pending: bool = False
    message: str = "Đăng ký thành công. Vui lòng kiểm tra email để xác minh tài khoản."
    requires_email_verification: bool = True


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    school_id: int | None = None
    avatar_url: str | None = None
    created_at: str | None = None
    can_change_password: bool = False
    email_verified: bool = True
    must_change_password: bool = False

    model_config = ConfigDict(from_attributes=True)


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=512)


class ResetPasswordRequest(TokenRequest):
    new_password: str = Field(..., min_length=6, max_length=128)


class MessageResponse(BaseModel):
    message: str
