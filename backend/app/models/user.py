"""User + UserPropertyAccess (SPEC §4.1, §5.1)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.property import Property


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    accesses: Mapped[list[UserPropertyAccess]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserPropertyAccess.user_id",
    )


class UserPropertyAccess(Base):
    """Authorization grant. SPEC §5.1 resolution rules:
      • Anonymous → no properties.
      • Superuser → all properties.
      • Authenticated non-superuser with no grants → no properties.
      • Authenticated user with grants → only those properties.
    """

    __tablename__ = "user_property_accesses"
    __table_args__ = (
        UniqueConstraint("user_id", "property_id", name="uq_user_property_accesses_user_property"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="accesses", foreign_keys=[user_id])
    property: Mapped[Property] = relationship()
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
