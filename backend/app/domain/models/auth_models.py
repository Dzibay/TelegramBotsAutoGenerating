from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(..., min_length=1)


class AdminUser(BaseModel):
    id: str = "admin"
    role: str = "admin"
