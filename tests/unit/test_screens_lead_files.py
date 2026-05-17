from pathlib import Path

from app.bot.screens.lead_files import (
    LEAD_UPLOAD_FILES_SCREEN_ID,
    LeadFilesCallback,
    render_lead_upload_files,
)
from app.services.content import ContentService

_CONTENT_DIR = Path(__file__).resolve().parents[2] / "app" / "bot" / "content" / "default"


def _content():
    return ContentService(ContentService.load(_CONTENT_DIR))


def test_lead_files_empty():
    screen = render_lead_upload_files(
        content=_content(), files=[], max_files=5, stack=["main_menu", "lead_upload_files"]
    )
    assert screen.screen_id == LEAD_UPLOAD_FILES_SCREEN_ID
    assert "0/5" in screen.text
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    # No delete-last button when empty.
    assert all("Удалить" not in lbl for lbl in labels)


def test_lead_files_with_some():
    files = [{"file_name": "photo.jpg"}, {"file_type": "document"}]
    screen = render_lead_upload_files(
        content=_content(), files=files, max_files=5, stack=["main_menu", "lead_upload_files"]
    )
    assert "2/5" in screen.text
    labels = [b.text for row in screen.keyboard.inline_keyboard for b in row]
    assert any("Удалить" in lbl for lbl in labels)


def test_lead_files_callbacks_pack():
    for a in ("continue", "delete_last", "back_to_questions"):
        assert LeadFilesCallback(action=a).pack().startswith("lead_files:")
