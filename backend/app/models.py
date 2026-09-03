from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UtcDateTime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)

    # Case-insensitive unique constraint on username.
    __table_args__ = (
        Index("uq_users_username_lower", func.lower(username), unique=True),
    )

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)
    last_used_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions", passive_deletes=True)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prep_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[float | None] = mapped_column(Float, nullable=True)
    cuisine: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Reserved for v2 image support: nothing writes it in v1, but `RecipeRead`
    # exposes it so the field does not appear later as a breaking addition.
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utcnow, onupdate=_utcnow
    )
    # Attribution only, and never reassigned. No cascade: deleting a user (which
    # v1 never does) must not take their recipes with them.
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    created_by: Mapped[User | None] = relationship()
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        order_by="RecipeIngredient.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    # 0-based, contiguous, server-assigned from the request array order.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL means "to taste"; when set the schema guarantees > 0 and finite.
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    # The author's unit as written (lower-cased, one trailing "." stripped),
    # never singularized: display text only. Arithmetic goes through
    # `normalize_unit_token`.
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    item: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # The verbatim pasted line (already truncated to 200 chars) for string
    # elements; NULL for structured ones.
    raw_text: Mapped[str | None] = mapped_column(String(300), nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")

    __table_args__ = (Index("ix_recipe_ingredients_recipe_position", "recipe_id", "position"),)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Display text. Set on first insert into a `(match_name, unit_bucket)` row and
    # only changed by `PATCH` — the additive `POST` upsert leaves it untouched
    # on conflict (spec.md §1, §5.5).
    item: Mapped[str] = mapped_column(String(200), nullable=False)
    # `normalize_name(item)`; tracks `item`.
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # The recipe<->inventory match key. User-editable but canonical: every value
    # (default or supplied) is `normalize_name`d before store; `""` after
    # normalize -> 422 (N5).
    match_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # "mass" | "volume" | "count" | "opaque:<canonical-token>". Widened to 30 to
    # fit `opaque:` + a long unknown token.
    unit_bucket: Mapped[str] = mapped_column(String(30), nullable=False)
    # Source of truth, in the bucket's canonical unit (g / ml / count / raw
    # opaque amount). Must stay `>= 0` and finite (spec.md §1): a finite request
    # can still overflow to `+inf` through unit conversion or the additive
    # upsert, and `x < 9e999` (SQLite parses the literal as `+Inf`) rejects that
    # and NaN at the database boundary.
    quantity_base: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Preferred display unit only — never drives math. NULL / opaque => display
    # in the canonical unit.
    display_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=_utcnow, onupdate=_utcnow
    )
    # Attribution only, never reassigned. No cascade: deleting a user (which v1
    # never does) must not take their inventory with them.
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("match_name", "unit_bucket", name="uq_inventory_match_bucket"),
        CheckConstraint(
            "quantity_base >= 0 AND quantity_base < 9e999",
            name="ck_inventory_quantity_base_nonneg_finite",
        ),
    )
