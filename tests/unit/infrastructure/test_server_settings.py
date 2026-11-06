"""Настройки запуска сервера и часового пояса приложения."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.configs.settings import (
    DEFAULT_TIMEZONE,
    ServerSettings,
    load_app_timezone,
    load_server_settings,
)
from src.domain.exceptions import ServerSettingsError, TimezoneSettingsError

NO_FILE = Path("/nonexistent/.env")


def server(environ: dict[str, str]) -> ServerSettings:
    return load_server_settings(NO_FILE, environ)


class TestServerSettings:
    def test_defaults_listen_on_localhost_only(self):
        settings = server({})
        assert settings == ServerSettings("127.0.0.1", 8000, 30, True)

    def test_values_come_from_environment(self):
        settings = server(
            {"APP_HOST": "0.0.0.0", "APP_PORT": "9000", "DB_WAIT_SECONDS": "5", "AUTO_MIGRATE": "0"}
        )
        assert settings == ServerSettings("0.0.0.0", 9000, 5, False)

    def test_values_come_from_env_file(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("APP_PORT=8123\nAUTO_MIGRATE=false\n", encoding="utf-8")
        settings = load_server_settings(env, {})
        assert (settings.port, settings.auto_migrate) == (8123, False)

    def test_environment_beats_env_file(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("APP_PORT=8123\n", encoding="utf-8")
        assert load_server_settings(env, {"APP_PORT": "8200"}).port == 8200

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "нет", "off"])
    def test_auto_migrate_off_words(self, value):
        assert server({"AUTO_MIGRATE": value}).auto_migrate is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "anything"])
    def test_auto_migrate_stays_on_otherwise(self, value):
        assert server({"AUTO_MIGRATE": value}).auto_migrate is True

    @pytest.mark.parametrize("port", ["abc", "0", "65536", "-1", "80.5"])
    def test_bad_port_is_rejected_with_its_name(self, port):
        with pytest.raises(ServerSettingsError, match="APP_PORT"):
            server({"APP_PORT": port})

    @pytest.mark.parametrize("wait", ["abc", "-5", "3601", "1.5"])
    def test_bad_wait_is_rejected_with_its_name(self, wait):
        with pytest.raises(ServerSettingsError, match="DB_WAIT_SECONDS"):
            server({"DB_WAIT_SECONDS": wait})

    def test_zero_wait_is_allowed(self):
        assert server({"DB_WAIT_SECONDS": "0"}).db_wait_seconds == 0

    def test_blank_values_fall_back_to_defaults(self):
        assert server({"APP_HOST": "  ", "APP_PORT": " "}) == ServerSettings()


class TestTimezone:
    def test_default_is_the_university_time_zone(self):
        assert load_app_timezone(NO_FILE, {}) == ZoneInfo(DEFAULT_TIMEZONE)

    def test_zone_comes_from_environment(self):
        zone = load_app_timezone(NO_FILE, {"APP_TIMEZONE": "Europe/Warsaw"})
        assert zone == ZoneInfo("Europe/Warsaw")

    def test_zone_offsets_are_applied(self):
        zone = load_app_timezone(NO_FILE, {"APP_TIMEZONE": "UTC"})
        assert datetime(2026, 3, 2, tzinfo=zone).utcoffset().total_seconds() == 0

    @pytest.mark.parametrize("name", ["Mars/Olympus", "не пояс", "../etc/passwd"])
    def test_unknown_zone_is_rejected_with_its_name(self, name):
        with pytest.raises(TimezoneSettingsError, match="APP_TIMEZONE"):
            load_app_timezone(NO_FILE, {"APP_TIMEZONE": name})
