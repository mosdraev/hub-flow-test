from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import make_session_factory
from app.main import create_app
from app.models import Note
from app.services.notes import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, SEARCH_MAX_LENGTH

BASE_TS = datetime(2026, 11, 5, 8, 0, tzinfo=UTC)


@pytest.fixture
def client(engine):
    with TestClient(create_app(make_session_factory(engine))) as c:
        yield c


@pytest.fixture
def seed(session):
    """Insert notes with strictly increasing created_at; returns them oldest first."""

    def _seed(*specs: tuple[str, str | None]) -> list[Note]:
        notes = []
        for i, (title, body) in enumerate(specs):
            ts = BASE_TS + timedelta(minutes=i)
            notes.append(Note(title=title, body=body, created_at=ts, updated_at=ts))
        session.add_all(notes)
        session.commit()
        return notes

    return _seed


def _seed_n(seed, n: int) -> list[Note]:
    return seed(*[(f"note {i}", None) for i in range(n)])


def _list(client, **params) -> dict:
    resp = client.get("/notes", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ids(page: dict) -> list[int]:
    return [n["id"] for n in page["items"]]


def _newest_first(notes: list[Note]) -> list[int]:
    return [n.id for n in reversed(notes)]


# Happy path


def test_defaults_and_envelope_shape(client, seed):
    notes = _seed_n(seed, 3)

    page = _list(client)
    assert set(page) == {"items", "total", "limit", "offset"}
    assert page["limit"] == DEFAULT_PAGE_LIMIT
    assert page["offset"] == 0
    assert page["total"] == 3
    assert _ids(page) == _newest_first(notes)
    assert set(page["items"][0]) == {"id", "title", "body", "created_at", "updated_at"}


def test_default_limit_caps_items(client, seed):
    _seed_n(seed, 25)

    page = _list(client)
    assert len(page["items"]) == DEFAULT_PAGE_LIMIT
    assert page["total"] == 25


def test_limit_and_offset_select_middle_page(client, seed):
    expected = _newest_first(_seed_n(seed, 25))

    page = _list(client, limit=10, offset=10)
    assert _ids(page) == expected[10:20]
    assert (page["limit"], page["offset"], page["total"]) == (10, 10, 25)


def test_walking_pages_returns_each_note_once_in_order(client, seed):
    expected = _newest_first(_seed_n(seed, 23))

    seen = []
    for offset in range(0, 30, 7):
        seen += _ids(_list(client, limit=7, offset=offset))
    assert seen == expected


@pytest.mark.parametrize(
    ("q", "expected_titles"),
    [
        ("groceries", ["Groceries list"]),  # title only
        ("calamansi", ["Market run"]),  # body only
        ("bills", ["Bills", "Pay bills"]),  # title in one, body in another
    ],
)
def test_search_matches_title_or_body(client, seed, q, expected_titles):
    seed(
        ("Groceries list", "eggs, rice"),
        ("Market run", "calamansi and garlic"),
        ("Pay bills", None),
        ("Bills", "pay the bills"),
        ("Unrelated", "nothing here"),
    )

    page = _list(client, q=q)
    assert [n["title"] for n in page["items"]] == expected_titles
    assert page["total"] == len(expected_titles)


def test_search_match_in_both_fields_returns_note_once(client, seed):
    seed(("rice", "rice and more rice"))

    page = _list(client, q="rice")
    assert page["total"] == 1
    assert len(page["items"]) == 1


def test_search_is_case_insensitive(client, seed):
    seed(("groceries", None), ("Other", "Buy GROCERIES"))

    assert _list(client, q="GROCERIES")["total"] == 2
    assert _list(client, q="gRoCeRiEs")["total"] == 2


def test_search_with_paging_counts_all_matches(client, seed):
    notes = seed(*[(f"match {i}", None) for i in range(5)], ("other", None))
    matches = _newest_first([n for n in notes if n.title.startswith("match")])

    page = _list(client, q="match", limit=2, offset=2)
    assert page["total"] == 5
    assert _ids(page) == matches[2:4]


# Failure path


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": MAX_PAGE_LIMIT + 1},
        {"limit": -1},
        {"limit": "abc"},
        {"offset": -1},
        {"offset": "abc"},
        {"q": "a" * (SEARCH_MAX_LENGTH + 1)},
    ],
)
def test_invalid_params_return_422(client, params):
    assert client.get("/notes", params=params).status_code == 422


# Edge cases


def test_empty_table(client):
    assert _list(client) == {"items": [], "total": 0, "limit": DEFAULT_PAGE_LIMIT, "offset": 0}


def test_offset_beyond_total_returns_empty_items_with_real_total(client, seed):
    _seed_n(seed, 3)

    page = _list(client, offset=50)
    assert page["items"] == []
    assert page["total"] == 3


@pytest.mark.parametrize("limit", [1, MAX_PAGE_LIMIT])
def test_limit_bounds_accepted(client, seed, limit):
    _seed_n(seed, MAX_PAGE_LIMIT + 1)

    page = _list(client, limit=limit)
    assert len(page["items"]) == limit
    assert page["total"] == MAX_PAGE_LIMIT + 1


def test_search_no_matches(client, seed):
    _seed_n(seed, 3)

    page = _list(client, q="zzz")
    assert page["items"] == []
    assert page["total"] == 0


@pytest.mark.parametrize("q", ["", "   "])
def test_blank_search_means_no_filter(client, seed, q):
    _seed_n(seed, 3)

    assert _list(client, q=q)["total"] == 3


def test_search_term_is_trimmed(client, seed):
    seed(("eggs", None), ("milk", None))

    page = _list(client, q="  eggs ")
    assert [n["title"] for n in page["items"]] == ["eggs"]


@pytest.mark.parametrize(
    ("q", "expected_titles"),
    [
        ("%", ["50% off"]),
        ("_", ["snake_case"]),
        ("\\", ["back\\slash"]),
        ("50%", ["50% off"]),
    ],
)
def test_like_wildcards_are_literal(client, seed, q, expected_titles):
    seed(("50% off", None), ("snake_case", None), ("back\\slash", None), ("plain", None))

    page = _list(client, q=q)
    assert [n["title"] for n in page["items"]] == expected_titles


def test_null_body_notes_found_by_title(client, seed):
    seed(("Title only", None), ("Has body", "with title text"))

    page = _list(client, q="title")
    assert page["total"] == 2


def test_unicode_search_exact_case(client, seed):
    # SQLite only case-folds ASCII, so only exact-case non-ASCII matches are asserted here.
    seed(("Bayad sa InstaPay ✅", None), ("Piña colada", "jalapeño"), ("plain", None))

    assert [n["title"] for n in _list(client, q="✅")["items"]] == ["Bayad sa InstaPay ✅"]
    assert [n["title"] for n in _list(client, q="ñ")["items"]] == ["Piña colada"]


def test_search_at_max_length_accepted(client, seed):
    term = "a" * SEARCH_MAX_LENGTH
    seed((term, None), ("short", None))

    page = _list(client, q=term)
    assert [n["title"] for n in page["items"]] == [term]
