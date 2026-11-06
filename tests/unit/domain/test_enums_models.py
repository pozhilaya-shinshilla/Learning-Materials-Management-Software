"""Юнит-тесты перечислений и моделей предметной области."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.enums import AccountStatus, EventType, FileType, Role, SortField, SortOrder
from src.domain.models import Discipline, Event, Favorite, Material, MaterialMemento, Topic, User
from tests.fakes import make_material, make_user


class TestEnums:
    @pytest.mark.parametrize("role", list(Role))
    def test_every_role_has_nonempty_label(self, role):
        assert role.label

    @pytest.mark.parametrize("status", list(AccountStatus))
    def test_every_status_has_nonempty_label(self, status):
        assert status.label

    @pytest.mark.parametrize("event_type", list(EventType))
    def test_every_event_type_has_label(self, event_type):
        assert event_type.label

    def test_event_labels_are_unique(self):
        labels = [e.label for e in EventType]
        assert len(labels) == len(set(labels))

    def test_values_are_machine_names(self):
        assert Role.STUDENT.value == "student"
        assert FileType.PDF.value == "pdf"
        assert SortField.TITLE.value == "title"
        assert SortOrder.ASCENDING.value == "asc"

    def test_str_enum_compares_with_string(self):
        assert Role.ADMIN == "admin"

    def test_lookup_by_value(self):
        assert Role("teacher") is Role.TEACHER

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError):
            Role("root")


class TestUser:
    def test_active_user(self):
        assert make_user(status=AccountStatus.ACTIVE).is_active() is True

    def test_blocked_user(self):
        assert make_user(status=AccountStatus.BLOCKED).is_active() is False

    def test_default_status_is_active(self):
        user = User(1, "abc", "a@b.c", "h", Role.STUDENT)
        assert user.status is AccountStatus.ACTIVE


class TestMaterialMemento:
    def test_memento_is_immutable(self):
        memento = MaterialMemento("a", "b", 1, 2)
        with pytest.raises(FrozenInstanceError):
            memento.title = "x"

    def test_snapshot_captures_editable_fields_only(self):
        material = make_material(title="T", description="D", discipline_id=3, topic_id=4)
        assert material.create_memento() == MaterialMemento("T", "D", 3, 4)

    def test_snapshot_is_independent_of_later_changes(self):
        material = make_material(title="T")
        memento = material.create_memento()
        material.title = "changed"
        assert memento.title == "T"

    def test_restore_returns_fields(self):
        material = make_material(title="T", description="D", discipline_id=3, topic_id=4)
        memento = material.create_memento()
        material.title, material.description = "x", "y"
        material.discipline_id, material.topic_id = 9, 9
        material.restore(memento)
        assert (material.title, material.description) == ("T", "D")
        assert (material.discipline_id, material.topic_id) == (3, 4)

    def test_restore_does_not_touch_file_or_author(self):
        material = make_material(author_id=7)
        memento = material.create_memento()
        material.file_name = "other.pdf"
        material.restore(memento)
        assert material.file_name == "other.pdf"
        assert material.author_id == 7


class TestDefaultTimestamps:
    def test_material_uploaded_at_defaults_to_now_utc(self):
        before = datetime.now(UTC)
        material = Material(1, "t", "d", 1, 1, "f.pdf", FileType.PDF, 1, 1)
        assert before <= material.uploaded_at <= datetime.now(UTC) + timedelta(seconds=1)
        assert material.uploaded_at.tzinfo is not None

    def test_favorite_and_event_have_timestamps(self):
        assert Favorite(1, 1).added_at.tzinfo is not None
        assert Event(1, 1, EventType.USER_LOGGED_IN, "x").occurred_at.tzinfo is not None

    def test_two_materials_do_not_share_default_timestamp_object(self):
        first = Material(1, "t", "d", 1, 1, "f.pdf", FileType.PDF, 1, 1)
        second = Material(2, "t", "d", 1, 1, "f.pdf", FileType.PDF, 1, 1)
        assert first.uploaded_at <= second.uploaded_at


def test_simple_models_hold_fields():
    assert Discipline(1, "Математика").name == "Математика"
    assert Topic(2, "Алгебра", 1).discipline_id == 1
