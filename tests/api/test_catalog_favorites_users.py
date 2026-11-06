"""Дисциплины, темы, избранное, пользователи и журнал событий."""

from __future__ import annotations

from tests.api.conftest import PASSWORD


class TestDisciplinesAndTopics:
    def test_crud_flow(self, client, teacher, student):
        created = client.post("/api/disciplines", headers=teacher.headers, json={"name": "Физика"})
        assert created.status_code == 201
        discipline_id = created.json()["id"]

        listed = client.get("/api/disciplines", headers=student.headers).json()
        assert [d["name"] for d in listed] == ["Физика"]
        assert (
            client.get(f"/api/disciplines/{discipline_id}", headers=student.headers).json()["name"]
            == "Физика"
        )

        renamed = client.patch(
            f"/api/disciplines/{discipline_id}", headers=teacher.headers, json={"name": "Механика"}
        )
        assert renamed.json()["name"] == "Механика"

        topic = client.post(
            "/api/topics",
            headers=teacher.headers,
            json={"name": "Кинематика", "discipline_id": discipline_id},
        )
        assert topic.status_code == 201
        topic_id = topic.json()["id"]
        assert client.get("/api/topics", headers=student.headers).json()[0]["name"] == "Кинематика"
        assert client.get(
            f"/api/topics?discipline_id={discipline_id}", headers=student.headers
        ).json()
        assert client.get("/api/topics?discipline_id=9999", headers=student.headers).json() == []
        assert (
            client.patch(
                f"/api/topics/{topic_id}", headers=teacher.headers, json={"name": "Динамика"}
            ).json()["name"]
            == "Динамика"
        )
        assert client.get(f"/api/topics/{topic_id}", headers=student.headers).status_code == 200

    def test_empty_patch_returns_current_object(self, client, teacher, catalog):
        response = client.patch(
            f"/api/disciplines/{catalog['discipline_id']}", headers=teacher.headers, json={}
        )
        assert response.status_code == 200 and response.json()["name"] == "Математика"

    def test_student_cannot_change_catalog(self, client, student, catalog):
        assert (
            client.post("/api/disciplines", headers=student.headers, json={"name": "Х"}).status_code
            == 403
        )
        assert (
            client.patch(
                f"/api/topics/{catalog['topic_id']}", headers=student.headers, json={"name": "Х"}
            ).status_code
            == 403
        )

    def test_duplicate_discipline_is_409_case_insensitive(self, client, teacher, catalog):
        response = client.post(
            "/api/disciplines", headers=teacher.headers, json={"name": "математика"}
        )
        assert response.status_code == 409
        assert response.json()["code"] == "DuplicateDisciplineError"

    def test_unknown_ids_are_404(self, client, teacher):
        assert client.get("/api/disciplines/9999", headers=teacher.headers).status_code == 404
        assert client.get("/api/topics/9999", headers=teacher.headers).status_code == 404
        assert (
            client.patch(
                "/api/topics/9999", headers=teacher.headers, json={"name": "Х"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/topics", headers=teacher.headers, json={"name": "Х", "discipline_id": 9999}
            ).status_code
            == 404
        )

    def test_anonymous_gets_401(self, client):
        assert client.get("/api/disciplines").status_code == 401
        assert client.get("/api/topics").status_code == 401


class TestFavorites:
    def test_add_list_remove(self, client, upload, teacher, student):
        material = upload(teacher).json()
        added = client.post(f"/api/favorites/{material['id']}", headers=student.headers)
        assert added.status_code == 201
        assert (
            added.json()["material_id"] == material["id"] and added.json()["user_id"] == student.id
        )

        listed = client.get("/api/favorites", headers=student.headers).json()
        assert [m["id"] for m in listed] == [material["id"]]
        assert client.get("/api/favorites", headers=teacher.headers).json() == []

        assert (
            client.delete(f"/api/favorites/{material['id']}", headers=student.headers).status_code
            == 204
        )
        assert client.get("/api/favorites", headers=student.headers).json() == []

    def test_duplicate_is_409_and_missing_is_404(self, client, upload, teacher, student):
        material = upload(teacher).json()
        client.post(f"/api/favorites/{material['id']}", headers=student.headers)
        assert (
            client.post(f"/api/favorites/{material['id']}", headers=student.headers).status_code
            == 409
        )
        assert client.post("/api/favorites/9999", headers=student.headers).status_code == 404
        client.delete(f"/api/favorites/{material['id']}", headers=student.headers)
        assert (
            client.delete(f"/api/favorites/{material['id']}", headers=student.headers).status_code
            == 404
        )


class TestUsers:
    def test_admin_lists_users_without_password_data(self, client, admin, teacher):
        response = client.get("/api/users", headers=admin.headers)
        assert response.status_code == 200
        assert {u["login"] for u in response.json()} == {"admin", "teacher1"}
        assert "password" not in response.text

    def test_non_admin_is_403_everywhere(self, client, teacher, student):
        for account in (teacher, student):
            assert client.get("/api/users", headers=account.headers).status_code == 403
            assert client.post("/api/users", headers=account.headers, json={}).status_code == 403
            assert client.patch("/api/users/1", headers=account.headers, json={}).status_code == 403
            assert client.delete("/api/users/1", headers=account.headers).status_code == 403

    def test_create_user_validations(self, client, admin, student):
        base = {"login": "newbie", "email": "newbie@example.org", "password": PASSWORD}
        weak = client.post("/api/users", headers=admin.headers, json={**base, "password": "weak"})
        assert weak.status_code == 422
        dup_login = client.post(
            "/api/users", headers=admin.headers, json={**base, "login": "student1"}
        )
        assert (dup_login.status_code, dup_login.json()["code"]) == (409, "DuplicateLoginError")
        dup_email = client.post(
            "/api/users", headers=admin.headers, json={**base, "email": "student1@example.org"}
        )
        assert (dup_email.status_code, dup_email.json()["code"]) == (409, "DuplicateEmailError")
        bad_role = client.post("/api/users", headers=admin.headers, json={**base, "role": "boss"})
        assert bad_role.status_code == 422

    def test_default_role_is_student(self, client, admin):
        body = {"login": "newbie", "email": "newbie@example.org", "password": PASSWORD}
        assert (
            client.post("/api/users", headers=admin.headers, json=body).json()["role"] == "student"
        )

    def test_patch_changes_role_and_status_together(self, client, admin, student):
        response = client.patch(
            f"/api/users/{student.id}",
            headers=admin.headers,
            json={"role": "teacher", "status": "blocked"},
        )
        assert response.status_code == 200
        assert (response.json()["role"], response.json()["status"]) == ("teacher", "blocked")
        restored = client.patch(
            f"/api/users/{student.id}", headers=admin.headers, json={"status": "active"}
        )
        assert restored.json()["status"] == "active"

    def test_patch_with_same_values_is_not_an_error(self, client, admin, student):
        response = client.patch(
            f"/api/users/{student.id}",
            headers=admin.headers,
            json={"role": "student", "status": "active"},
        )
        assert response.status_code == 200

    def test_admin_cannot_change_or_block_or_delete_self(self, client, admin):
        role = client.patch(
            f"/api/users/{admin.id}", headers=admin.headers, json={"role": "student"}
        )
        assert (role.status_code, role.json()["code"]) == (403, "SelfRoleChangeError")
        block = client.patch(
            f"/api/users/{admin.id}", headers=admin.headers, json={"status": "blocked"}
        )
        assert (block.status_code, block.json()["code"]) == (403, "SelfBlockError")
        delete = client.delete(f"/api/users/{admin.id}", headers=admin.headers)
        assert (delete.status_code, delete.json()["code"]) == (403, "SelfDeleteError")

    def test_refused_patch_changes_nothing(self, client, admin):
        client.patch(
            f"/api/users/{admin.id}",
            headers=admin.headers,
            json={"role": "student", "status": "blocked"},
        )
        me = next(
            u for u in client.get("/api/users", headers=admin.headers).json() if u["id"] == admin.id
        )
        assert (me["role"], me["status"]) == ("admin", "active")

    def test_unknown_user_is_404(self, client, admin):
        assert (
            client.patch(
                "/api/users/9999", headers=admin.headers, json={"role": "teacher"}
            ).status_code
            == 404
        )
        assert client.delete("/api/users/9999", headers=admin.headers).status_code == 404

    def test_delete_user_keeps_their_materials(self, client, admin, upload, teacher, student):
        material = upload(teacher).json()
        assert client.delete(f"/api/users/{teacher.id}", headers=admin.headers).status_code == 204
        kept = client.get(f"/api/materials/{material['id']}", headers=student.headers).json()
        assert kept["author_id"] is None


class TestEvents:
    def test_admin_sees_journal_of_actions(self, client, admin, upload, teacher):
        upload(teacher)
        events = client.get("/api/events", headers=admin.headers).json()
        types = {e["event_type"] for e in events}
        assert {
            "user_logged_in",
            "material_created",
            "file_uploaded",
            "discipline_created",
        } <= types
        sample = events[0]
        assert set(sample) == {
            "id",
            "user_id",
            "event_type",
            "description",
            "target",
            "occurred_at",
        }

    def test_logout_is_journaled(self, client, admin, student):
        client.post("/api/auth/logout", headers=student.headers)
        events = client.get("/api/events", headers=admin.headers).json()
        assert "user_logged_out" in {e["event_type"] for e in events}

    def test_role_and_block_changes_are_journaled(self, client, admin, student):
        client.patch(
            f"/api/users/{student.id}",
            headers=admin.headers,
            json={"role": "teacher", "status": "blocked"},
        )
        types = {e["event_type"] for e in client.get("/api/events", headers=admin.headers).json()}
        assert {"user_role_changed", "user_blocked", "user_account_changed"} & types

    def test_non_admin_cannot_read_journal(self, client, teacher, student):
        assert client.get("/api/events", headers=teacher.headers).status_code == 403
        assert client.get("/api/events", headers=student.headers).status_code == 403


class TestCatalogDeletion:
    def test_teacher_deletes_empty_topic_then_discipline(self, client, teacher, catalog):
        topic = f"/api/topics/{catalog['topic_id']}"
        discipline = f"/api/disciplines/{catalog['discipline_id']}"
        assert client.delete(topic, headers=teacher.headers).status_code == 204
        assert client.get(topic, headers=teacher.headers).status_code == 404
        assert client.delete(discipline, headers=teacher.headers).status_code == 204
        assert client.get(discipline, headers=teacher.headers).status_code == 404

    def test_discipline_with_topics_is_409(self, client, teacher, catalog):
        response = client.delete(
            f"/api/disciplines/{catalog['discipline_id']}", headers=teacher.headers
        )
        assert response.status_code == 409
        assert response.json()["code"] == "DisciplineNotEmptyError"
        assert "Математика" in response.json()["detail"]
        still_there = client.get(
            f"/api/disciplines/{catalog['discipline_id']}", headers=teacher.headers
        )
        assert still_there.status_code == 200

    def test_topic_with_materials_is_409_and_session_stays_usable(
        self, client, upload, teacher, catalog
    ):
        assert upload(teacher).status_code == 201
        response = client.delete(f"/api/topics/{catalog['topic_id']}", headers=teacher.headers)
        assert response.status_code == 409
        assert response.json()["code"] == "TopicInUseError"
        assert client.get("/api/materials", headers=teacher.headers).json()

    def test_student_cannot_delete(self, client, student, catalog):
        assert (
            client.delete(f"/api/topics/{catalog['topic_id']}", headers=student.headers).status_code
            == 403
        )
        assert (
            client.delete(
                f"/api/disciplines/{catalog['discipline_id']}", headers=student.headers
            ).status_code
            == 403
        )

    def test_unknown_ids_are_404_and_anonymous_is_401(self, client, teacher):
        assert client.delete("/api/topics/9999", headers=teacher.headers).status_code == 404
        assert client.delete("/api/disciplines/9999", headers=teacher.headers).status_code == 404
        assert client.delete("/api/topics/1").status_code == 401

    def test_deletions_are_journaled(self, client, admin, teacher, catalog):
        client.delete(f"/api/topics/{catalog['topic_id']}", headers=teacher.headers)
        client.delete(f"/api/disciplines/{catalog['discipline_id']}", headers=teacher.headers)
        events = client.get("/api/events", headers=admin.headers).json()
        kinds = {event["event_type"] for event in events}
        assert {"topic_deleted", "discipline_deleted"} <= kinds
