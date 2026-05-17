import asyncio

from app.core.logging import setup_logging
from app.db.session import session_scope
from app.services.forms import ensure_seed_data


async def main() -> None:
    setup_logging()
    async with session_scope() as session:
        await ensure_seed_data(session)


if __name__ == "__main__":
    asyncio.run(main())

