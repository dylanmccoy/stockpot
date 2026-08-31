from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecipeBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    ingredients: str = ""
    instructions: str = ""


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(RecipeBase):
    pass


class RecipeRead(RecipeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
