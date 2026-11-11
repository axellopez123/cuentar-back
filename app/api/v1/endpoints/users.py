import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import SessionDep, CurrentUserDep
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["Usuarios y Participantes"])


@router.get("", response_model=List[UserResponse])
async def list_household_members(
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Lists all registered members/participants of the household."""
    stmt = select(User).order_by(User.created_at.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_household_member(
    user_in: UserCreate,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Dynamically registers a new participant in the household."""
    existing_stmt = select(User).where(User.email == user_in.email.lower().strip())
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un participante con este correo electrónico.",
        )

    user = User(
        email=user_in.email.lower().strip(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        role=user_in.role,
        avatar_url=user_in.avatar_url,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_household_member(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Updates information for a specific household participant."""
    stmt = select(User).where(User.id == user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participante no encontrado.",
        )

    if user_in.full_name is not None:
        user.full_name = user_in.full_name.strip()
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.avatar_url is not None:
        user.avatar_url = user_in.avatar_url
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)

    await session.commit()
    await session.refresh(user)
    return user

