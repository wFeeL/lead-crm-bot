from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import UserRole
from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def upsert_telegram_user(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        is_admin: bool = False,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        role = UserRole.ADMIN if is_admin else UserRole.CLIENT
        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=role,
                last_seen_at=datetime.now(UTC),
            )
            self.session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.last_seen_at = datetime.now(UTC)
            if is_admin and user.role == UserRole.CLIENT:
                user.role = UserRole.ADMIN
        await self.session.flush()
        return user

    async def list_admins(self) -> list[User]:
        """List non-blocked admins / managers / owners."""
        from sqlalchemy import select

        from app.core.constants import UserRole

        result = await self.session.execute(
            select(User)
            .where(
                User.role.in_((UserRole.ADMIN, UserRole.MANAGER, UserRole.OWNER)),
                User.is_blocked.is_(False),
            )
            .order_by(User.id)
        )
        return list(result.scalars().all())
