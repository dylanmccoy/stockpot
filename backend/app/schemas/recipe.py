"""Recipe schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RecipeBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    ingredients: str = ""
    instructions: str = ""


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(RecipeBase):
    pass


class RecipeRead(ORMModel):
    id: int
    title: str
    ingredients: str
    instructions: str
    created_at: datetime
