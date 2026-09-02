from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import TransactionRoute, get_db
from app.models import Recipe
from app.schemas import RecipeCreate, RecipeRead, RecipeUpdate
from app.security import get_current_user

router = APIRouter(
    prefix="/api/recipes",
    tags=["recipes"],
    route_class=TransactionRoute,
    dependencies=[Depends(get_current_user)],
)


def _get_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[RecipeRead])
def list_recipes(db: Session = Depends(get_db)) -> list[Recipe]:
    return list(db.scalars(select(Recipe).order_by(Recipe.created_at.desc())))


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db)) -> Recipe:
    recipe = Recipe(**payload.model_dump())
    db.add(recipe)
    db.flush()  # populate id / created_at; get_db owns the commit
    return recipe


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> Recipe:
    return _get_or_404(db, recipe_id)


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: Session = Depends(get_db)) -> Recipe:
    recipe = _get_or_404(db, recipe_id)
    for key, value in payload.model_dump().items():
        setattr(recipe, key, value)
    db.flush()  # get_db owns the commit
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = _get_or_404(db, recipe_id)
    db.delete(recipe)
    db.flush()  # get_db owns the commit
