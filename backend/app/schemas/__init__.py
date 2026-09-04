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
from app.schemas.cook_logs import (
    CookDeductionRead,
    CookLogList,
    CookLogRead,
    CookRequest,
)
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
)
from app.schemas.recipe import (
    AvailabilityLine,
    AvailabilityReport,
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
    "AvailabilityLine",
    "AvailabilityReport",
    # Cook logs
    "CookRequest",
    "CookDeductionRead",
    "CookLogRead",
    "CookLogList",
    # Inventory
    "InventoryItemCreate",
    "InventoryItemUpdate",
    "InventoryItemRead",
]
