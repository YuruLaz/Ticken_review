from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserRead(BaseModel):
    # Read attributes from SQLAlchemy objects.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class LoginForm(BaseModel):
    # OAuth2 field names; username holds email.
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
