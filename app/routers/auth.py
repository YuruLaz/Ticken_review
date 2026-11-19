from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import CurrentUser, SessionDep
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.user import LoginForm, Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, session: SessionDep):
    existing = await session.scalar(select(User).where(User.email == data.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # role is never taken from the request, so nobody can register as admin.
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
    )
    session.add(user)
    await session.commit()
    return user


@router.post("/login", response_model=Token)
async def login(form: Annotated[LoginForm, Form()], session: SessionDep):
    user = await session.scalar(select(User).where(User.email == form.username))
    if user is None or not user.is_active or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser):
    return user
