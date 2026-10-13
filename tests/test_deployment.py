import os
import runpy
from pathlib import Path
from unittest.mock import patch

import pytest

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.py"


def load_settings(**overrides):
    environment = {
        "PYTHON_DOTENV_DISABLED": "1",
        "DATABASE_URL": "postgresql://test:test@localhost/test",
        **overrides,
    }
    with patch.dict(os.environ, environment, clear=True):
        return runpy.run_path(str(SETTINGS_PATH))


def test_render_settings_enable_security_and_allow_render_host():
    settings = load_settings(
        RENDER="true",
        RENDER_EXTERNAL_HOSTNAME="uk-weather.onrender.com",
        DJANGO_SECRET_KEY="a" * 64,
        MAP_STYLE_URL="https://tiles.example.com/style.json",
    )
    assert settings["DEBUG"] is False
    assert "uk-weather.onrender.com" in settings["ALLOWED_HOSTS"]
    assert settings["SECURE_SSL_REDIRECT"] is True
    assert settings["SESSION_COOKIE_SECURE"] is True
    assert settings["CSRF_COOKIE_SECURE"] is True
    assert settings["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")
    assert settings["DATABASES"]["default"]["ENGINE"].endswith("postgis")


def test_production_requires_secret_key():
    with pytest.raises(ValueError, match="DJANGO_SECRET_KEY"):
        load_settings(DJANGO_DEBUG="false")


def test_production_requires_map_provider():
    with pytest.raises(ValueError, match="MAP_STYLE_URL"):
        load_settings(DJANGO_DEBUG="false", DJANGO_SECRET_KEY="a" * 64)


def test_local_development_keeps_demo_map_and_debug():
    settings = load_settings()
    assert settings["DEBUG"] is True
    assert settings["MAP_STYLE_URL"] == "https://demotiles.maplibre.org/style.json"


def test_custom_hosts_and_csrf_origins_are_parsed():
    settings = load_settings(
        DJANGO_ALLOWED_HOSTS=" weather.example.com, ,www.weather.example.com ",
        DJANGO_CSRF_TRUSTED_ORIGINS=" https://weather.example.com, ",
    )
    assert settings["ALLOWED_HOSTS"] == [
        "weather.example.com",
        "www.weather.example.com",
    ]
    assert settings["CSRF_TRUSTED_ORIGINS"] == ["https://weather.example.com"]
