from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def alembic_cfg(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def _inspect(url):
    engine = create_engine(url)
    try:
        insp = inspect(engine)
        tables = insp.get_table_names()
        columns = {c["name"]: c for c in insp.get_columns("notes")} if "notes" in tables else {}
        indexes = {i["name"] for i in insp.get_indexes("notes")} if "notes" in tables else set()
        return tables, columns, indexes
    finally:
        engine.dispose()


def test_upgrade_creates_notes_table_and_index(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    tables, columns, indexes = _inspect(url)
    assert "notes" in tables
    assert set(columns) == {"id", "title", "body", "created_at", "updated_at"}
    assert columns["title"]["nullable"] is False
    assert columns["body"]["nullable"] is True
    assert columns["created_at"]["nullable"] is False
    assert columns["updated_at"]["nullable"] is False
    assert "ix_notes_created_at" in indexes


def test_downgrade_drops_table_and_reupgrade_works(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tables, _, _ = _inspect(url)
    assert "notes" not in tables

    command.upgrade(cfg, "head")
    tables, _, indexes = _inspect(url)
    assert "notes" in tables
    assert "ix_notes_created_at" in indexes
