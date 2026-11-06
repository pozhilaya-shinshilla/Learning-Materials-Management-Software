"""Аутентификация: вход, токены, выход, восстановление пароля."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.api.conftest import ADMIN, PASSWORD, headers_of, sign_in


class TestLogin:
    def test_login_returns_token_and_user_without_password(self, client):
        data = sign_in(client, ADMIN.login, ADMIN.password)
        assert data["token_type"] == "bearer"
        assert data["access_token"]
        assert data["user"]["role"] == "admin"
        assert "password" not in str(data) and "hash" not in str(data)

    @pytest.mark.parametrize("password", ["wrong-password", "x"])
    def test_wrong_password_is_401_with_error_body(self, client, password):
        response = client.post("/api/auth/login", json={"login": "admin", "password": password})
        assert response.status_code == 401
        assert response.json()["code"] == "AuthenticationError"
        assert response.headers["www-authenticate"] == "Bearer"

    def test_unknown_login_gives_same_answer_as_wrong_password(self, client):
        ghost = client.post("/api/auth/login", json={"login": "ghost", "password": "Password123!"})
        wrong = client.post("/api/auth/login", json={"login": "admin", "password": "Password123!"})
        assert (ghost.status_code, ghost.json()) == (wrong.status_code, wrong.json())

    def test_missing_field_is_422(self, client):
        assert client.post("/api/auth/login", json={"login": "admin"}).status_code == 422

    def test_unknown_field_is_422(self, client):
        body = {"login": "admin", "password": ADMIN.password, "remember": True}
        assert client.post("/api/auth/login", json=body).status_code == 422

    def test_blocked_user_cannot_login(self, client, admin, student):
        client.patch(f"/api/users/{student.id}", headers=admin.headers, json={"status": "blocked"})
        response = client.post("/api/auth/login", json={"login": "student1", "password": PASSWORD})
        assert response.status_code == 403
        assert response.json()["code"] == "AccountBlockedError"


class TestTokens:
    def test_protected_route_without_token_is_401(self, client):
        response = client.get("/api/materials")
        assert response.status_code == 401
        assert response.json()["code"] == "NotAuthenticatedError"

    def test_garbage_token_is_401(self, client):
        response = client.get("/api/materials", headers=headers_of("garbage"))
        assert response.status_code == 401
        assert response.json()["code"] == "InvalidTokenError"

    def test_valid_token_opens_protected_route(self, client, student):
        assert client.get("/api/materials", headers=student.headers).status_code == 200

    def test_logout_revokes_token(self, client, student):
        assert client.post("/api/auth/logout", headers=student.headers).status_code == 200
        assert client.get("/api/materials", headers=student.headers).status_code == 401

    def test_logout_keeps_other_sessions_of_the_same_user(self, client, student):
        second = headers_of(sign_in(client, "student1", PASSWORD)["access_token"])
        client.post("/api/auth/logout", headers=student.headers)
        assert client.get("/api/materials", headers=second).status_code == 200

    def test_expired_token_is_rejected(self, client, student, session_factory):
        with session_factory() as session:
            session.execute(text("UPDATE auth_tokens SET expires_at = now() - interval '1 hour'"))
            session.commit()
        response = client.get("/api/materials", headers=student.headers)
        assert response.status_code == 401
        assert response.json()["code"] == "InvalidTokenError"

    def test_token_is_stored_only_as_hash(self, client, student, session_factory):
        token = student.headers["Authorization"].removeprefix("Bearer ")
        with session_factory() as session:
            stored = session.scalars(text("SELECT token_hash FROM auth_tokens")).all()
        assert token not in stored and all(len(value) == 64 for value in stored)

    def test_role_change_revokes_existing_tokens(self, client, admin, teacher):
        client.patch(f"/api/users/{teacher.id}", headers=admin.headers, json={"role": "student"})
        response = client.post("/api/disciplines", headers=teacher.headers, json={"name": "Физика"})
        assert response.status_code == 401

    def test_new_login_after_role_change_has_new_role(self, client, admin, teacher):
        client.patch(f"/api/users/{teacher.id}", headers=admin.headers, json={"role": "student"})
        opened = sign_in(client, teacher.login, PASSWORD)
        assert opened["user"]["role"] == "student"
        headers = {"Authorization": f"Bearer {opened['access_token']}"}
        assert (
            client.post("/api/disciplines", headers=headers, json={"name": "Физика"}).status_code
            == 403
        )

    def test_me_returns_current_user(self, client, student):
        response = client.get("/api/auth/me", headers=student.headers)
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == student.id and body["login"] == student.login
        assert body["role"] == "student" and "password" not in body and "password_hash" not in body

    def test_me_requires_token(self, client):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_for_blocked_user_is_403(self, client, admin, student):
        client.patch(f"/api/users/{student.id}", headers=admin.headers, json={"status": "blocked"})
        assert client.get("/api/auth/me", headers=student.headers).status_code == 403

    def test_blocking_applies_to_existing_token_immediately(self, client, admin, student):
        client.patch(f"/api/users/{student.id}", headers=admin.headers, json={"status": "blocked"})
        response = client.get("/api/materials", headers=student.headers)
        assert response.status_code == 403
        assert response.json()["code"] == "AccountBlockedError"

    def test_deleting_user_revokes_token(self, client, admin, student):
        assert client.delete(f"/api/users/{student.id}", headers=admin.headers).status_code == 204
        assert client.get("/api/materials", headers=student.headers).status_code == 401


class TestPasswordRecovery:
    def test_recovery_sends_code_and_reset_changes_password(self, client, student, email_sender):
        response = client.post(
            "/api/auth/password/recovery", json={"email": "student1@example.org"}
        )
        assert response.status_code == 202
        ((to_address, _subject, body),) = email_sender.sent
        assert to_address == "student1@example.org"
        code = body.split("Код для восстановления пароля: ")[1].split()[0]

        reset = client.post(
            "/api/auth/password/reset", json={"token": code, "new_password": "NewPassword456!"}
        )
        assert reset.status_code == 200
        old = client.post("/api/auth/login", json={"login": "student1", "password": PASSWORD})
        new = client.post(
            "/api/auth/login", json={"login": "student1", "password": "NewPassword456!"}
        )
        assert (old.status_code, new.status_code) == (401, 200)

    def test_unknown_email_gets_same_answer_and_no_mail(self, client, email_sender):
        response = client.post("/api/auth/password/recovery", json={"email": "nobody@example.org"})
        assert response.status_code == 202
        assert email_sender.sent == []

    def test_wrong_code_is_401(self, client):
        response = client.post(
            "/api/auth/password/reset", json={"token": "000000", "new_password": "NewPassword456!"}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "InvalidResetTokenError"

    def test_code_is_single_use(self, client, student, email_sender):
        client.post("/api/auth/password/recovery", json={"email": "student1@example.org"})
        code = email_sender.sent[0][2].split("Код для восстановления пароля: ")[1].split()[0]
        payload = {"token": code, "new_password": "NewPassword456!"}
        assert client.post("/api/auth/password/reset", json=payload).status_code == 200
        assert client.post("/api/auth/password/reset", json=payload).status_code == 401


class TestTokensAfterPasswordReset:
    def _reset_password(self, client, email_sender, new_password="NewPassword456!"):
        client.post("/api/auth/password/recovery", json={"email": "student1@example.org"})
        code = email_sender.sent[-1][2].split("Код для восстановления пароля: ")[1].split()[0]
        response = client.post(
            "/api/auth/password/reset", json={"token": code, "new_password": new_password}
        )
        assert response.status_code == 200

    def test_all_tokens_of_the_user_are_revoked(self, client, student, email_sender):
        second = headers_of(sign_in(client, "student1", PASSWORD)["access_token"])
        self._reset_password(client, email_sender)
        for headers in (student.headers, second):
            response = client.get("/api/materials", headers=headers)
            assert response.status_code == 401
            assert response.json()["code"] == "InvalidTokenError"

    def test_tokens_of_other_users_survive(self, client, teacher, student, email_sender):
        self._reset_password(client, email_sender)
        assert client.get("/api/materials", headers=teacher.headers).status_code == 200

    def test_new_password_gives_a_working_new_token(self, client, student, email_sender):
        self._reset_password(client, email_sender)
        fresh = headers_of(sign_in(client, "student1", "NewPassword456!")["access_token"])
        assert client.get("/api/materials", headers=fresh).status_code == 200

    def test_rejected_reset_keeps_tokens(self, client, student):
        response = client.post(
            "/api/auth/password/reset", json={"token": "000000", "new_password": "NewPassword456!"}
        )
        assert response.status_code == 401
        assert client.get("/api/materials", headers=student.headers).status_code == 200

    def test_weak_new_password_keeps_tokens(self, client, student, email_sender):
        client.post("/api/auth/password/recovery", json={"email": "student1@example.org"})
        code = email_sender.sent[-1][2].split("Код для восстановления пароля: ")[1].split()[0]
        weak = client.post("/api/auth/password/reset", json={"token": code, "new_password": "weak"})
        assert weak.status_code == 422
        assert client.get("/api/materials", headers=student.headers).status_code == 200
