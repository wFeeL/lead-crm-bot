import pytest

from app.bot.ui.callbacks import NavCallback


def test_navcallback_pack_back():
    assert NavCallback(action="back").pack() == "nav:back"


def test_navcallback_pack_home():
    assert NavCallback(action="home").pack() == "nav:home"


def test_navcallback_pack_cancel():
    assert NavCallback(action="cancel").pack() == "nav:cancel"


def test_navcallback_unpack_roundtrip():
    s = NavCallback(action="back").pack()
    cb = NavCallback.unpack(s)
    assert cb.action == "back"


def test_navcallback_rejects_unknown_action():
    with pytest.raises(Exception):  # ValidationError or ValueError
        NavCallback(action="teleport")
