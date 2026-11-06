"""Юнит-тесты хеширования паролей PBKDF2."""

from __future__ import annotations

import pytest

from src.security.password_hasher import Pbkdf2PasswordHasher


@pytest.fixture
def hasher() -> Pbkdf2PasswordHasher:
    return Pbkdf2PasswordHasher()


def test_hash_does_not_contain_plain_password(hasher):
    assert "secret-password" not in hasher.hash("secret-password")


def test_hash_has_four_parts(hasher):
    algorithm, iterations, salt, digest = hasher.hash("Password1!").split("$")
    assert algorithm == "sha256"
    assert int(iterations) >= 100_000
    assert len(bytes.fromhex(salt)) == 16
    assert len(bytes.fromhex(digest)) == 32


def test_same_password_gives_different_hashes_because_of_salt(hasher):
    assert hasher.hash("Password1!") != hasher.hash("Password1!")


def test_verify_accepts_correct_password(hasher):
    assert hasher.verify("Password1!", hasher.hash("Password1!")) is True


def test_verify_rejects_wrong_password(hasher):
    assert hasher.verify("Password2!", hasher.hash("Password1!")) is False


@pytest.mark.parametrize("password", ["", " ", "a", "Пароль-кириллица", "😀" * 5, "a" * 10_000])
def test_roundtrip_for_unusual_passwords(hasher, password):
    assert hasher.verify(password, hasher.hash(password)) is True


def test_verification_is_case_sensitive(hasher):
    assert hasher.verify("PASSWORD1", hasher.hash("Password1!")) is False


def test_trailing_space_matters(hasher):
    assert hasher.verify("Password1! ", hasher.hash("Password1!")) is False


@pytest.mark.parametrize(
    "broken",
    [
        "",
        "plain",
        "a$b$c",
        "a$b$c$d$e",
        "sha256$notanumber$00$00",
        "sha256$1000$zz$00",
        "sha256$$00$00",
    ],
)
def test_malformed_hash_is_rejected_without_exception(hasher, broken):
    assert hasher.verify("Password1!", broken) is False


def test_tampered_digest_is_rejected(hasher):
    algorithm, iterations, salt, digest = hasher.hash("Password1!").split("$")
    flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
    assert hasher.verify("Password1!", "$".join([algorithm, iterations, salt, flipped])) is False


def test_hash_with_different_iteration_count_still_verifies(hasher):
    import hashlib

    salt = bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", b"Password1!", salt, 1000)
    stored = f"sha256$1000${salt.hex()}${digest.hex()}"
    assert hasher.verify("Password1!", stored) is True
