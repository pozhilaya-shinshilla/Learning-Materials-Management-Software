"""Юнит-тесты настроек: константы, разбор .env, настройки администратора и SMTP."""

from __future__ import annotations

import pytest

from src.configs import config
from src.configs.settings import (
    SmtpSettings,
    load_admin_settings,
    load_smtp_settings,
    parse_env_file,
)
from src.domain.enums import FileType
from src.domain.exceptions import (
    AdminPasswordNotSetError,
    InvalidEmailError,
    InvalidLoginError,
    PasswordTooShortError,
    PasswordTooWeakError,
    SmtpSettingsError,
)


class TestConfigConstants:
    def test_max_size_is_100_megabytes(self):
        assert config.MAX_FILE_SIZE_BYTES == 100 * 1024 * 1024

    def test_allowed_types_match_the_specification(self):
        assert {t.value for t in config.ALLOWED_FILE_TYPES} == {
            "pdf",
            "docx",
            "pptx",
            "xlsx",
            "jpg",
            "png",
        }

    def test_every_allowed_type_is_a_file_type(self):
        assert all(isinstance(t, FileType) for t in config.ALLOWED_FILE_TYPES)

    def test_reset_token_ttl_is_positive(self):
        assert config.RESET_TOKEN_TTL_MINUTES > 0


class TestParseEnvFile:
    def test_missing_file_gives_empty_dict(self, tmp_path):
        assert parse_env_file(tmp_path / "none.env") == {}

    def test_empty_file(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("")
        assert parse_env_file(path) == {}

    def test_reads_pairs(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nB=two\n")
        assert parse_env_file(path) == {"A": "1", "B": "two"}

    def test_skips_comments_blank_lines_and_lines_without_equals(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("# comment\n\n   \nNOEQUALS\nA=1\n")
        assert parse_env_file(path) == {"A": "1"}

    def test_strips_quotes_and_spaces(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A = \"hello\"\nB='x y'\n")
        assert parse_env_file(path) == {"A": "hello", "B": "x y"}

    def test_value_may_contain_equals(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=b=c\n")
        assert parse_env_file(path) == {"A": "b=c"}

    def test_empty_value(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=\n")
        assert parse_env_file(path) == {"A": ""}

    def test_last_duplicate_wins(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nA=2\n")
        assert parse_env_file(path) == {"A": "2"}

    def test_indented_comment_is_skipped(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("   # note\nA=1\n")
        assert parse_env_file(path) == {"A": "1"}


class TestLoadAdminSettings:
    def _load(self, tmp_path, environ, file_text=None):
        env_file = tmp_path / ".env"
        if file_text is not None:
            env_file.write_text(file_text)
        return load_admin_settings(env_file, environ)

    def test_password_is_required(self, tmp_path):
        with pytest.raises(AdminPasswordNotSetError):
            self._load(tmp_path, {})

    def test_empty_password_is_rejected(self, tmp_path):
        with pytest.raises(AdminPasswordNotSetError):
            self._load(tmp_path, {"ADMIN_PASSWORD": ""})

    def test_defaults_for_login_and_email(self, tmp_path):
        settings = self._load(tmp_path, {"ADMIN_PASSWORD": "Password1!"})
        assert (settings.login, settings.email) == ("admin", "admin@example.org")

    def test_blank_login_and_email_fall_back_to_defaults(self, tmp_path):
        env = {"ADMIN_PASSWORD": "Password1!", "ADMIN_LOGIN": "  ", "ADMIN_EMAIL": ""}
        settings = self._load(tmp_path, env)
        assert settings.login == "admin"

    def test_environment_overrides_file(self, tmp_path):
        settings = self._load(
            tmp_path,
            {"ADMIN_PASSWORD": "FromEnv123!"},
            "ADMIN_PASSWORD=FromFile123!\nADMIN_LOGIN=boss\n",
        )
        assert settings.password == "FromEnv123!"
        assert settings.login == "boss"

    def test_file_is_used_when_environment_is_empty(self, tmp_path):
        settings = self._load(tmp_path, {}, "ADMIN_PASSWORD=FromFile123!\n")
        assert settings.password == "FromFile123!"

    def test_password_boundary_eight_characters(self, tmp_path):
        assert self._load(tmp_path, {"ADMIN_PASSWORD": "Abcdef1!"}).password == "Abcdef1!"
        with pytest.raises(PasswordTooShortError):
            self._load(tmp_path, {"ADMIN_PASSWORD": "Abcde1!"})

    @pytest.mark.parametrize("password", ["admin123", "admin123!", "Admin!!!!", "Admin1234"])
    def test_weak_admin_password_is_rejected(self, tmp_path, password):
        with pytest.raises(PasswordTooWeakError):
            self._load(tmp_path, {"ADMIN_PASSWORD": password})

    def test_invalid_login(self, tmp_path):
        with pytest.raises(InvalidLoginError):
            self._load(tmp_path, {"ADMIN_PASSWORD": "Password1!", "ADMIN_LOGIN": "a!"})

    def test_invalid_email(self, tmp_path):
        with pytest.raises(InvalidEmailError):
            self._load(tmp_path, {"ADMIN_PASSWORD": "Password1!", "ADMIN_EMAIL": "nope"})

    def test_settings_are_frozen(self, tmp_path):
        settings = self._load(tmp_path, {"ADMIN_PASSWORD": "Password1!"})
        with pytest.raises(AttributeError):
            settings.login = "x"


class TestLoadSmtpSettings:
    def _load(self, tmp_path, environ):
        return load_smtp_settings(tmp_path / "none.env", environ)

    def test_returns_none_without_host(self, tmp_path):
        assert self._load(tmp_path, {}) is None
        assert self._load(tmp_path, {"SMTP_HOST": "   "}) is None

    def test_defaults(self, tmp_path):
        settings = self._load(tmp_path, {"SMTP_HOST": "h", "SMTP_FROM": "a@b.org"})
        assert settings == SmtpSettings("h", 587, "a@b.org", "", "", True)

    @pytest.mark.parametrize("port", ["1", "25", "587", "65535"])
    def test_valid_ports(self, tmp_path, port):
        env = {"SMTP_HOST": "h", "SMTP_FROM": "a@b.org", "SMTP_PORT": port}
        assert self._load(tmp_path, env).port == int(port)

    @pytest.mark.parametrize("port", ["0", "65536", "-1", "abc", "5.5", "1e3"])
    def test_invalid_ports(self, tmp_path, port):
        env = {"SMTP_HOST": "h", "SMTP_FROM": "a@b.org", "SMTP_PORT": port}
        with pytest.raises(SmtpSettingsError):
            self._load(tmp_path, env)

    def test_blank_port_uses_default(self, tmp_path):
        env = {"SMTP_HOST": "h", "SMTP_FROM": "a@b.org", "SMTP_PORT": "  "}
        assert self._load(tmp_path, env).port == 587

    def test_sender_falls_back_to_username(self, tmp_path):
        env = {"SMTP_HOST": "h", "SMTP_USER": "me@x.org", "SMTP_PASSWORD": "pw"}
        settings = self._load(tmp_path, env)
        assert settings.sender == "me@x.org"
        assert settings.password == "pw"

    def test_sender_is_required(self, tmp_path):
        with pytest.raises(SmtpSettingsError):
            self._load(tmp_path, {"SMTP_HOST": "h"})

    def test_sender_must_be_email(self, tmp_path):
        with pytest.raises(InvalidEmailError):
            self._load(tmp_path, {"SMTP_HOST": "h", "SMTP_FROM": "nope"})

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "нет", " 0 "])
    def test_starttls_can_be_disabled(self, tmp_path, value):
        env = {"SMTP_HOST": "h", "SMTP_FROM": "a@b.org", "SMTP_STARTTLS": value}
        assert self._load(tmp_path, env).use_starttls is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "anything"])
    def test_starttls_enabled_otherwise(self, tmp_path, value):
        env = {"SMTP_HOST": "h", "SMTP_FROM": "a@b.org", "SMTP_STARTTLS": value}
        assert self._load(tmp_path, env).use_starttls is True
