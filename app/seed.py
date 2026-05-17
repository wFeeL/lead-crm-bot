import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import session_scope
from app.services.content import ContentService
from app.services.forms import ensure_seed_data


async def main() -> None:
    setup_logging()
    settings = get_settings()
    profile_dir = Path(__file__).parent / "bot" / "content" / settings.content_profile
    bundle = ContentService.load(profile_dir)
    async with session_scope() as session:
        await ensure_seed_data(session, bundle)


if __name__ == "__main__":
    asyncio.run(main())
