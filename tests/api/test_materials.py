"""Материалы: загрузка, список с поиском и фильтрами, правка, удаление, скачивание."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.api.conftest import PDF


class TestUpload:
    def test_teacher_uploads_material(self, upload, teacher, catalog):
        response = upload(teacher)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["title"] == "Лекция по пределам"
        assert body["file_type"] == "pdf" and body["file_size_bytes"] == len(PDF)
        assert body["author_id"] == teacher.id
        assert body["topic_id"] == catalog["topic_id"]
        assert "storage_path" not in body

    def test_student_cannot_upload(self, upload, student):
        response = upload(student)
        assert response.status_code == 403
        assert response.json()["code"] == "MaterialAccessError"

    def test_unsupported_format_is_415(self, upload, teacher):
        response = upload(teacher, name="virus.exe")
        assert response.status_code == 415
        assert response.json()["code"] == "UnsupportedFileTypeError"

    def test_too_large_file_is_413_and_nothing_is_saved(
        self, client, upload, teacher, student, monkeypatch
    ):
        monkeypatch.setattr("src.api.uploads.MAX_FILE_SIZE_BYTES", 10)
        response = upload(teacher)
        assert response.status_code == 413
        assert client.get("/api/materials", headers=student.headers).json() == []

    def test_missing_file_is_422(self, client, teacher, catalog):
        response = client.post(
            "/api/materials",
            headers=teacher.headers,
            data={"title": "Без файла", **{k: str(v) for k, v in catalog.items()}},
        )
        assert response.status_code == 422

    def test_unknown_topic_is_rejected(self, client, teacher, catalog):
        response = client.post(
            "/api/materials",
            headers=teacher.headers,
            data={"title": "Т", "discipline_id": str(catalog["discipline_id"]), "topic_id": "9999"},
            files={"file": ("a.pdf", PDF, "application/pdf")},
        )
        assert response.status_code in (404, 422)

    def test_path_in_filename_is_stripped(self, upload, teacher):
        response = upload(teacher, name="../../etc/evil.pdf")
        assert response.status_code == 201
        assert response.json()["file_name"] == "evil.pdf"

    def test_anonymous_cannot_upload(self, client, catalog):
        response = client.post(
            "/api/materials", data={"title": "x"}, files={"file": ("a.pdf", PDF)}
        )
        assert response.status_code == 401


class TestListAndSearch:
    @pytest.fixture
    def materials(self, upload, teacher):
        upload(teacher, title="Лекция по пределам", name="a.pdf")
        upload(teacher, title="Практика: производные", name="b.docx")
        upload(teacher, title="Алгебра в таблицах", name="c.xlsx")

    def titles(self, client, student, **params):
        response = client.get("/api/materials", headers=student.headers, params=params)
        assert response.status_code == 200, response.text
        return [m["title"] for m in response.json()]

    def test_lists_everything_for_student(self, client, student, materials):
        assert len(self.titles(client, student)) == 3

    @pytest.mark.db  # морфологию русского языка выполняет PostgreSQL
    def test_search_uses_russian_morphology(self, client, student, materials):
        assert self.titles(client, student, q="лекции") == ["Лекция по пределам"]
        assert self.titles(client, student, q="производная") == ["Практика: производные"]

    def test_filter_by_file_type(self, client, student, materials):
        assert self.titles(client, student, file_type="xlsx") == ["Алгебра в таблицах"]

    def test_filter_by_discipline_and_topic(self, client, student, materials, catalog):
        assert len(self.titles(client, student, discipline_id=catalog["discipline_id"])) == 3
        assert self.titles(client, student, topic_id=catalog["topic_id"] + 100) == []

    def test_filter_by_upload_date(self, client, student, materials):
        today = date.today()
        assert len(self.titles(client, student, uploaded_from=today - timedelta(days=1))) == 3
        assert self.titles(client, student, uploaded_from=today + timedelta(days=2)) == []
        assert self.titles(client, student, uploaded_to=today - timedelta(days=2)) == []

    def test_sort_by_title(self, client, student, materials):
        ascending = self.titles(client, student, sort_by="title", order="asc")
        assert ascending == sorted(ascending, key=str.casefold)
        descending = self.titles(client, student, sort_by="title", order="desc")
        assert descending == ascending[::-1]

    @pytest.mark.parametrize(
        "params",
        [{"file_type": "exe"}, {"sort_by": "size"}, {"unknown": "1"}, {"discipline_id": 0}],
    )
    def test_invalid_query_is_422(self, client, student, params):
        response = client.get("/api/materials", headers=student.headers, params=params)
        assert response.status_code == 422

    def test_reversed_date_range_is_422(self, client, student):
        params = {"uploaded_from": "2026-10-10", "uploaded_to": "2026-10-01"}
        assert (
            client.get("/api/materials", headers=student.headers, params=params).status_code == 422
        )


class TestItem:
    def test_get_material(self, client, upload, teacher, student):
        created = upload(teacher).json()
        response = client.get(f"/api/materials/{created['id']}", headers=student.headers)
        assert response.status_code == 200 and response.json() == created

    def test_unknown_material_is_404(self, client, student):
        response = client.get("/api/materials/9999", headers=student.headers)
        assert response.status_code == 404
        assert response.json()["code"] == "MaterialNotFoundError"

    def test_patch_changes_only_sent_fields(self, client, upload, teacher):
        created = upload(teacher).json()
        response = client.patch(
            f"/api/materials/{created['id']}", headers=teacher.headers, json={"title": "Новое"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Новое"
        assert response.json()["description"] == created["description"]

    def test_patch_by_foreign_teacher_is_403(self, client, upload, teacher, make_account):
        created = upload(teacher).json()
        other = make_account("teacher2", "teacher")
        response = client.patch(
            f"/api/materials/{created['id']}", headers=other.headers, json={"title": "Чужое"}
        )
        assert response.status_code == 403

    def test_patch_unknown_field_is_422(self, client, upload, teacher):
        created = upload(teacher).json()
        response = client.patch(
            f"/api/materials/{created['id']}", headers=teacher.headers, json={"file_type": "png"}
        )
        assert response.status_code == 422

    def test_delete_removes_material(self, client, upload, teacher, student):
        created = upload(teacher).json()
        assert (
            client.delete(f"/api/materials/{created['id']}", headers=teacher.headers).status_code
            == 204
        )
        assert (
            client.get(f"/api/materials/{created['id']}", headers=student.headers).status_code
            == 404
        )

    def test_student_cannot_delete(self, client, upload, teacher, student):
        created = upload(teacher).json()
        response = client.delete(f"/api/materials/{created['id']}", headers=student.headers)
        assert response.status_code == 403

    def test_admin_can_delete_any_material(self, client, upload, teacher, admin):
        created = upload(teacher).json()
        assert (
            client.delete(f"/api/materials/{created['id']}", headers=admin.headers).status_code
            == 204
        )


class TestDownload:
    def test_download_returns_file_and_is_logged(self, client, upload, teacher, student, admin):
        created = upload(teacher).json()
        response = client.get(f"/api/materials/{created['id']}/download", headers=student.headers)
        assert response.status_code == 200
        assert response.content == PDF
        assert "lecture.pdf" in response.headers["content-disposition"]
        events = client.get("/api/events", headers=admin.headers).json()
        assert "material_downloaded" in {e["event_type"] for e in events}

    def test_download_requires_login(self, client, upload, teacher):
        created = upload(teacher).json()
        assert client.get(f"/api/materials/{created['id']}/download").status_code == 401

    def test_download_of_unknown_material_is_404(self, client, student):
        assert (
            client.get("/api/materials/9999/download", headers=student.headers).status_code == 404
        )

    def test_deleted_file_on_disk_is_404_not_500(self, client, upload, teacher, student, tmp_path):
        created = upload(teacher).json()
        for stored in (tmp_path / "uploads").iterdir():
            stored.unlink()
        response = client.get(f"/api/materials/{created['id']}/download", headers=student.headers)
        assert response.status_code == 404


class TestPaginationAndAuthors:
    @pytest.fixture
    def many(self, upload, teacher):
        for number in range(5):
            assert upload(teacher, title=f"Материал {number}").status_code == 201

    def test_without_limit_everything_is_returned_with_total_header(self, client, student, many):
        response = client.get("/api/materials", headers=student.headers)
        assert len(response.json()) == 5
        assert response.headers["X-Total-Count"] == "5"

    def test_pages_do_not_overlap_and_total_is_stable(self, client, student, many):
        params = {"limit": 2, "sort_by": "title", "order": "asc"}
        first = client.get("/api/materials", headers=student.headers, params=params)
        second = client.get(
            "/api/materials", headers=student.headers, params={**params, "offset": 2}
        )
        last = client.get("/api/materials", headers=student.headers, params={**params, "offset": 4})
        titles = [m["title"] for r in (first, second, last) for m in r.json()]
        assert titles == [f"Материал {n}" for n in range(5)]
        assert [len(r.json()) for r in (first, second, last)] == [2, 2, 1]
        assert {r.headers["X-Total-Count"] for r in (first, second, last)} == {"5"}

    def test_total_respects_filters(self, client, student, many):
        response = client.get(
            "/api/materials", headers=student.headers, params={"q": "Материал 3", "limit": 10}
        )
        everything = client.get(
            "/api/materials", headers=student.headers, params={"q": "Материал 3"}
        )
        assert (
            int(response.headers["X-Total-Count"]) == len(everything.json()) == len(response.json())
        )
        assert 0 < len(response.json()) < 5

    def test_offset_beyond_the_end_is_empty_but_total_is_kept(self, client, student, many):
        response = client.get(
            "/api/materials", headers=student.headers, params={"limit": 5, "offset": 50}
        )
        assert response.json() == [] and response.headers["X-Total-Count"] == "5"

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
    def test_invalid_paging_is_422(self, client, student, params):
        assert (
            client.get("/api/materials", headers=student.headers, params=params).status_code == 422
        )

    def test_author_login_is_visible_to_every_role(self, client, upload, teacher, student):
        created = upload(teacher).json()
        assert created["author_login"] == teacher.login
        listed = client.get("/api/materials", headers=student.headers).json()
        assert listed[0]["author_login"] == teacher.login
        card = client.get(f"/api/materials/{created['id']}", headers=student.headers).json()
        assert card["author_login"] == teacher.login

    def test_deleted_author_is_marked(self, client, admin, upload, teacher, student):
        created = upload(teacher).json()
        client.delete(f"/api/users/{teacher.id}", headers=admin.headers)
        card = client.get(f"/api/materials/{created['id']}", headers=student.headers).json()
        assert card["author_id"] is None and card["author_login"] == "автор удалён"

    def test_favorites_include_author_login(self, client, upload, teacher, student):
        created = upload(teacher).json()
        client.post(f"/api/favorites/{created['id']}", headers=student.headers)
        favorites = client.get("/api/favorites", headers=student.headers).json()
        assert favorites[0]["author_login"] == teacher.login


class TestJpegExtension:
    @pytest.mark.parametrize("name", ["scan.jpeg", "scan.JPEG", "scan.jpg"])
    def test_jpeg_is_accepted_as_jpg(self, upload, teacher, name):
        response = upload(teacher, name=name, body=b"\xff\xd8\xff\xe0jpeg")
        assert response.status_code == 201, response.text
        assert response.json()["file_type"] == "jpg"
        assert response.json()["file_name"] == name
