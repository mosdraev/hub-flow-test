import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.db import make_session_factory
from app.main import create_app
from app.models import Note
from app.models.note import TITLE_MAX_LENGTH


@pytest.fixture
def client(engine):
    with TestClient(create_app(make_session_factory(engine))) as c:
        yield c


def _create(client, **payload) -> dict:
    resp = client.post("/notes", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# Happy path


def test_create_with_title_and_body(client):
    resp = client.post("/notes", json={"title": "Groceries", "body": "eggs, rice"})

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Groceries"
    assert data["body"] == "eggs, rice"
    assert isinstance(data["id"], int)
    assert data["created_at"].endswith("Z")
    assert data["updated_at"].endswith("Z")


def test_create_title_only_body_null(client):
    assert _create(client, title="Just a title")["body"] is None


def test_list_empty(client):
    resp = client.get("/notes")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_newest_first(client):
    first = _create(client, title="first")
    time.sleep(0.01)
    second = _create(client, title="second")

    ids = [n["id"] for n in client.get("/notes").json()]
    assert ids == [second["id"], first["id"]]


def test_get_by_id(client):
    note = _create(client, title="Find me", body="here")

    resp = client.get(f"/notes/{note['id']}")
    assert resp.status_code == 200
    # Same timestamp format whether the note is fresh or reloaded from the DB.
    assert resp.json() == note


def test_patch_title_only_keeps_body_and_advances_updated_at(client):
    note = _create(client, title="Before", body="keep me")
    time.sleep(0.01)

    resp = client.patch(f"/notes/{note['id']}", json={"title": "After"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "After"
    assert data["body"] == "keep me"
    assert data["created_at"] == note["created_at"]
    assert data["updated_at"] > note["updated_at"]


def test_patch_body_null_clears_body(client):
    note = _create(client, title="t", body="to clear")

    resp = client.patch(f"/notes/{note['id']}", json={"body": None})
    assert resp.status_code == 200
    assert resp.json()["body"] is None
    assert resp.json()["title"] == "t"


def test_delete_removes_note(client):
    note = _create(client, title="Bye")

    resp = client.delete(f"/notes/{note['id']}")
    assert resp.status_code == 204
    assert resp.content == b""

    assert client.get(f"/notes/{note['id']}").status_code == 404
    assert client.get("/notes").json() == []


# Failure path


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"body": "no title"},
        {"title": ""},
        {"title": "   "},
        {"title": "a" * (TITLE_MAX_LENGTH + 1)},
        {"title": 123},
        {"title": None},
        {"title": "ok", "body": 5},
        {"title": "ok", "extra": "nope"},
    ],
)
def test_create_invalid_returns_422(client, payload):
    assert client.post("/notes", json=payload).status_code == 422
    assert client.get("/notes").json() == []


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_unknown_id_returns_404(client, method):
    kwargs = {"json": {"title": "x"}} if method == "patch" else {}
    resp = getattr(client, method)("/notes/9999", **kwargs)
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Note not found"}


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_non_integer_id_returns_422(client, method):
    kwargs = {"json": {"title": "x"}} if method == "patch" else {}
    assert getattr(client, method)("/notes/abc", **kwargs).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": None},
        {"title": "  "},
        {"title": "a" * (TITLE_MAX_LENGTH + 1)},
        {"unknown": "field"},
    ],
)
def test_patch_invalid_returns_422_and_leaves_note_unchanged(client, payload):
    note = _create(client, title="Original", body="b")

    assert client.patch(f"/notes/{note['id']}", json=payload).status_code == 422
    assert client.get(f"/notes/{note['id']}").json() == note


def test_malformed_json_returns_422(client):
    resp = client.post(
        "/notes", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 422


# Edge cases


def test_title_trimmed_on_create_and_update(client):
    note = _create(client, title="  padded  ")
    assert note["title"] == "padded"

    resp = client.patch(f"/notes/{note['id']}", json={"title": "\tagain \n"})
    assert resp.json()["title"] == "again"


def test_title_at_max_length_accepted(client):
    note = _create(client, title="a" * TITLE_MAX_LENGTH)
    assert len(note["title"]) == TITLE_MAX_LENGTH


def test_unicode_round_trips(client):
    note = _create(client, title="Bayad sa InstaPay ✅", body="Salamat po 🙏 ñ é 漢字")

    data = client.get(f"/notes/{note['id']}").json()
    assert data["title"] == "Bayad sa InstaPay ✅"
    assert data["body"] == "Salamat po 🙏 ñ é 漢字"


def test_delete_twice_second_is_404(client):
    note = _create(client, title="Once")
    assert client.delete(f"/notes/{note['id']}").status_code == 204
    assert client.delete(f"/notes/{note['id']}").status_code == 404


def test_list_tiebreak_by_id_when_created_at_equal(client, session):
    ts = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    a = Note(title="a", created_at=ts, updated_at=ts)
    b = Note(title="b", created_at=ts, updated_at=ts)
    session.add_all([a, b])
    session.commit()

    ids = [n["id"] for n in client.get("/notes").json()]
    assert ids == [b.id, a.id]
