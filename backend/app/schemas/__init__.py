"""Schema definitions and exports."""

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserMini,
    UserRead,
)
from app.schemas.common import ORMModel
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
)
from app.schemas.recipe import (
    RecipeBase,
    RecipeCreate,
    RecipeIngredientIn,
    RecipeIngredientRead,
    RecipeRead,
    RecipeUpdate,
)

__all__ = [
    # Common
    "ORMModel",
    # Auth
    "RegisterRequest",
    "ChangePasswordRequest",
    "LoginRequest",
    "UserMini",
    "UserRead",
    "TokenResponse",
    # Recipe
    "RecipeBase",
    "RecipeCreate",
    "RecipeUpdate",
    "RecipeRead",
    "RecipeIngredientIn",
    "RecipeIngredientRead",
    # Inventory
    "InventoryItemCreate",
    "InventoryItemUpdate",
    "InventoryItemRead",
]
