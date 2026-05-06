import os
from app.settings import Settings


def test_defaults_load_when_env_missing(monkeypatch):
    for key in [
        "SIGNNOW_API_HOST",
        "SIGNNOW_API_BASIC_TOKEN",
        "SIGNNOW_API_USERNAME",
        "SIGNNOW_API_PASSWORD",
        "SIGNNOW_DOWNLOADS_DIR",
        "SN_SIGNER_EMAIL",
    ]:
        monkeypatch.delenv(key, raising=False)

    s = Settings(_env_file=None)
    assert s.signnow_api_host == "https://api.signnow.com"
    assert s.sn_signer_email == "signer@signnow.com"


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("SN_SIGNER_EMAIL", "override@example.com")
    s = Settings(_env_file=None)
    assert s.sn_signer_email == "override@example.com"
