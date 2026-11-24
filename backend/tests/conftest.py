import csv
import os
import shutil

import pytest
from fastapi.testclient import TestClient

import fakes
from helpers import CLINIC_NOW, DATA


@pytest.fixture(autouse=True)
def fake_llm():
    """Every test gets a scripted fake model by default (no key, no network). Tests may replace it."""
    from app import llm
    calls: list = []
    llm.set_model_factory(fakes.make_factory(calls=calls))
    yield calls
    llm.set_model_factory(None)


def _build_template(tmp_path_factory, name, seed, pack2):
    path = tmp_path_factory.mktemp(name) / "template.db"
    old = os.environ.get("NETRACARE_DB")
    os.environ["NETRACARE_DB"] = str(path)
    os.environ["CLINIC_NOW"] = CLINIC_NOW
    from app import db
    db.init_db(with_seed_appointments=seed, with_past_visits=pack2)
    if old is not None:
        os.environ["NETRACARE_DB"] = old
    return path


@pytest.fixture(scope="session")
def template_db(tmp_path_factory):
    """Iteration 1 database: data pack 1 + stretch seed appointments (data pack 2 left out so those tests are unchanged)."""
    return _build_template(tmp_path_factory, "tpl1", seed=True, pack2=False)


@pytest.fixture(scope="session")
def template_db2(tmp_path_factory):
    """Iteration 2 database: data pack 1 + data pack 2 (27 past visits, profiles), no seed appointments."""
    return _build_template(tmp_path_factory, "tpl2", seed=False, pack2=True)


def _client(template, tmp_path, monkeypatch):
    fresh = tmp_path / "test.db"
    shutil.copy(template, fresh)
    monkeypatch.setenv("NETRACARE_DB", str(fresh))
    monkeypatch.setenv("CLINIC_NOW", CLINIC_NOW)
    from app.main import app
    return TestClient(app)  # no `with`: lifespan is skipped, the DB is already loaded


@pytest.fixture()
def client(template_db, tmp_path, monkeypatch):
    return _client(template_db, tmp_path, monkeypatch)


@pytest.fixture()
def client2(template_db2, tmp_path, monkeypatch):
    return _client(template_db2, tmp_path, monkeypatch)


@pytest.fixture(scope="session")
def patients():
    with open(DATA / "patients.csv", newline="", encoding="utf-8") as f:
        return {r["patient_id"]: r for r in csv.DictReader(f)}
