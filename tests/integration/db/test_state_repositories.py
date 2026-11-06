"""Репозитории состояния приложения: коды сброса, неудачные входы, снимки правок."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from src.configs.config import MAX_REVISIONS_PER_MATERIAL
from src.database.models import AuthTokenEntity, MaterialRevisionEntity, PasswordResetTokenEntity
from src.domain.models import AuthToken, MaterialMemento, PasswordResetToken
from tests.conftest import new_material

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


class TestAuthTokens:
    def _token(self, user_id: int, digest: str = "a" * 64, delta=timedelta(hours=12)):
        return AuthToken(0, user_id, digest, NOW + delta)

    def test_add_get_delete(self, auth_token_repo, teacher_user):
        saved = auth_token_repo.add(self._token(teacher_user.id))
        assert saved.id > 0
        assert auth_token_repo.get_by_hash("a" * 64).user_id == teacher_user.id
        auth_token_repo.delete_by_hash("a" * 64)
        assert auth_token_repo.get_by_hash("a" * 64) is None

    def test_unknown_hash_is_none(self, auth_token_repo):
        assert auth_token_repo.get_by_hash("f" * 64) is None

    def test_hash_is_unique(self, auth_token_repo, teacher_user, student_user):
        from sqlalchemy.exc import IntegrityError

        auth_token_repo.add(self._token(teacher_user.id))
        with pytest.raises(IntegrityError, match="uq_auth_tokens_token_hash"):
            auth_token_repo.add(self._token(student_user.id))

    def test_delete_by_user_keeps_other_users_tokens(
        self, auth_token_repo, teacher_user, student_user
    ):
        auth_token_repo.add(self._token(teacher_user.id, "a" * 64))
        auth_token_repo.add(self._token(teacher_user.id, "b" * 64))
        auth_token_repo.add(self._token(student_user.id, "c" * 64))
        auth_token_repo.delete_by_user(teacher_user.id)
        assert auth_token_repo.get_by_hash("a" * 64) is None
        assert auth_token_repo.get_by_hash("b" * 64) is None
        assert auth_token_repo.get_by_hash("c" * 64) is not None

    def test_delete_expired_keeps_valid(self, auth_token_repo, teacher_user):
        auth_token_repo.add(self._token(teacher_user.id, "a" * 64, timedelta(minutes=-1)))
        auth_token_repo.add(self._token(teacher_user.id, "b" * 64, timedelta(minutes=5)))
        auth_token_repo.delete_expired(NOW)
        assert auth_token_repo.get_by_hash("a" * 64) is None
        assert auth_token_repo.get_by_hash("b" * 64) is not None

    def test_deleting_user_removes_tokens(
        self, auth_token_repo, user_repo, teacher_user, db_session
    ):
        auth_token_repo.add(self._token(teacher_user.id))
        user_repo.delete(teacher_user.id)
        count = db_session.scalar(select(func.count()).select_from(AuthTokenEntity))
        assert count == 0


class TestPasswordResetTokens:
    def _token(self, user_id: int, digest: str = "a" * 64, delta=timedelta(minutes=30)):
        return PasswordResetToken(0, user_id, digest, NOW + delta)

    def test_add_get_delete(self, reset_token_repo, teacher_user):
        saved = reset_token_repo.add(self._token(teacher_user.id))
        assert saved.id > 0
        assert reset_token_repo.get_by_hash("a" * 64).user_id == teacher_user.id
        reset_token_repo.delete_by_hash("a" * 64)
        assert reset_token_repo.get_by_hash("a" * 64) is None

    def test_unknown_hash_is_none(self, reset_token_repo):
        assert reset_token_repo.get_by_hash("f" * 64) is None

    def test_hash_is_unique(self, reset_token_repo, teacher_user, student_user):
        from sqlalchemy.exc import IntegrityError

        reset_token_repo.add(self._token(teacher_user.id))
        with pytest.raises(IntegrityError, match="uq_password_reset_tokens_token_hash"):
            reset_token_repo.add(self._token(student_user.id))

    def test_consume_returns_owner_and_removes_code(self, reset_token_repo, teacher_user):
        reset_token_repo.add(self._token(teacher_user.id))
        assert reset_token_repo.consume("a" * 64, NOW) == teacher_user.id
        assert reset_token_repo.get_by_hash("a" * 64) is None
        assert reset_token_repo.consume("a" * 64, NOW) is None  # код одноразовый

    def test_consume_rejects_expired_code(self, reset_token_repo, teacher_user):
        reset_token_repo.add(self._token(teacher_user.id, delta=timedelta(minutes=-5)))
        assert reset_token_repo.consume("a" * 64, NOW) is None

    def test_consume_of_unknown_code_is_none(self, reset_token_repo):
        assert reset_token_repo.consume("f" * 64, NOW) is None

    def test_delete_by_user_keeps_other_users_codes(
        self, reset_token_repo, teacher_user, student_user
    ):
        reset_token_repo.add(self._token(teacher_user.id, "a" * 64))
        reset_token_repo.add(self._token(teacher_user.id, "b" * 64))
        reset_token_repo.add(self._token(student_user.id, "c" * 64))
        reset_token_repo.delete_by_user(teacher_user.id)
        assert reset_token_repo.get_by_hash("a" * 64) is None
        assert reset_token_repo.get_by_hash("b" * 64) is None
        assert reset_token_repo.get_by_hash("c" * 64) is not None

    def test_delete_expired_keeps_valid(self, reset_token_repo, teacher_user):
        reset_token_repo.add(self._token(teacher_user.id, "a" * 64, timedelta(minutes=-1)))
        reset_token_repo.add(self._token(teacher_user.id, "b" * 64, timedelta(minutes=5)))
        reset_token_repo.delete_expired(NOW)
        assert reset_token_repo.get_by_hash("a" * 64) is None
        assert reset_token_repo.get_by_hash("b" * 64) is not None

    def test_expiry_keeps_timezone(self, reset_token_repo, teacher_user):
        reset_token_repo.add(self._token(teacher_user.id))
        assert reset_token_repo.get_by_hash("a" * 64).expires_at == NOW + timedelta(minutes=30)

    def test_deleting_user_removes_codes(
        self, reset_token_repo, user_repo, teacher_user, db_session
    ):
        reset_token_repo.add(self._token(teacher_user.id))
        user_repo.delete(teacher_user.id)
        count = db_session.scalar(select(func.count()).select_from(PasswordResetTokenEntity))
        assert count == 0


class TestFailedLogins:
    def test_register_counts_per_login(self, failed_login_repo):
        assert [failed_login_repo.register("bob") for _ in range(3)] == [1, 2, 3]
        assert failed_login_repo.register("amy") == 1

    def test_reset_forgets_only_that_login(self, failed_login_repo):
        failed_login_repo.register("bob")
        failed_login_repo.register("amy")
        failed_login_repo.reset("bob")
        assert failed_login_repo.register("bob") == 1
        assert failed_login_repo.register("amy") == 2

    def test_reset_of_unknown_login_is_silent(self, failed_login_repo):
        failed_login_repo.reset("nobody")

    def test_login_of_nonexistent_user_is_counted(self, failed_login_repo):
        assert failed_login_repo.register("ghost") == 1


class TestMaterialRevisions:
    def _memento(self, title: str = "t") -> MaterialMemento:
        return MaterialMemento(title, "описание", 1, 1)

    @pytest.fixture
    def material(self, seeded, material_repo):
        return material_repo.add(new_material(seeded.topic, seeded.teacher.id))

    def test_pop_on_empty_returns_none(self, revision_repo, material):
        assert revision_repo.pop(material.id) is None

    def test_has_history_false_initially(self, revision_repo, material):
        assert revision_repo.has_history(material.id) is False

    def test_snapshot_roundtrip(self, revision_repo, material):
        revision_repo.push(material.id, MaterialMemento("Название", "Описание", 1, 1))
        assert revision_repo.pop(material.id) == MaterialMemento("Название", "Описание", 1, 1)

    def test_lifo_order(self, revision_repo, material):
        revision_repo.push(material.id, self._memento("first"))
        revision_repo.push(material.id, self._memento("second"))
        assert revision_repo.pop(material.id).title == "second"
        assert revision_repo.pop(material.id).title == "first"
        assert revision_repo.pop(material.id) is None

    def test_histories_are_per_material(self, revision_repo, material, material_repo, seeded):
        other = material_repo.add(new_material(seeded.topic, seeded.teacher.id, "Другой"))
        revision_repo.push(material.id, self._memento("one"))
        revision_repo.push(other.id, self._memento("two"))
        assert revision_repo.pop(material.id).title == "one"
        assert revision_repo.has_history(other.id)

    def test_has_history_after_pop_of_last(self, revision_repo, material):
        revision_repo.push(material.id, self._memento())
        revision_repo.pop(material.id)
        assert revision_repo.has_history(material.id) is False

    def test_only_latest_snapshots_are_kept(self, revision_repo, material, db_session):
        for index in range(MAX_REVISIONS_PER_MATERIAL + 5):
            revision_repo.push(material.id, self._memento(str(index)))
        stored = db_session.scalar(select(func.count()).select_from(MaterialRevisionEntity))
        assert stored == MAX_REVISIONS_PER_MATERIAL
        assert revision_repo.pop(material.id).title == str(MAX_REVISIONS_PER_MATERIAL + 4)

    def test_default_depth_is_twenty(self):
        assert MAX_REVISIONS_PER_MATERIAL == 20

    def test_deleting_material_removes_snapshots(
        self, revision_repo, material, material_repo, db_session
    ):
        revision_repo.push(material.id, self._memento())
        material_repo.delete(material.id)
        stored = db_session.scalar(select(func.count()).select_from(MaterialRevisionEntity))
        assert stored == 0
