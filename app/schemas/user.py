from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserRead(BaseModel):
    # Lets Pydantic read attributes off a SQLAlchemy object, not just a dict.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class LoginForm(BaseModel):
    # Field names are fixed by OAuth2 so Swagger's Authorize button works; username holds the email.
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
