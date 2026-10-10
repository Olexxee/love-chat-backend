from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=50,
    )
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=100,
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=100,
    )


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    avatar_url: str | None = None


class AuthResponse(BaseModel):
    message: str
    access_token: str
    token_type: str
    user: UserResponse
