from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import SessionDep, CurrentUserDep
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categorías"])


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Lists all available expense and income categories."""
    stmt = select(Category).order_by(Category.name.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    cat_in: CategoryCreate,
    session: SessionDep,
    _current_user: CurrentUserDep,
):
    """Creates a new category."""
    existing_stmt = select(Category).where(Category.name == cat_in.name.strip())
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una categoría con este nombre.",
        )

    category = Category(
        name=cat_in.name.strip(),
        icon=cat_in.icon,
        color_hex=cat_in.color_hex,
        is_default=False,
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category

