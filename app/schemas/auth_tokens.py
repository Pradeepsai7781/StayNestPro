from pydantic import BaseModel, EmailStr, Field


class EmailRequest(BaseModel):
    email: EmailStr


class TokenVerificationRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)
    new_password: str = Field(min_length=8, max_length=128)
