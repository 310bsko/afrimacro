import pytest
import requests

import etape5


class FakeResponse:
    """Fausse réponse HTTP : aucun accès à internet n'est nécessaire."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def page(number, pages, rows):
    return [{"page": number, "pages": pages}, rows]


def test_fetch_pages_reads_every_page(monkeypatch):
    answers = iter([FakeResponse(page(1, 2, ["a"])), FakeResponse(page(2, 2, ["b"]))])
    monkeypatch.setattr(etape5.requests, "get", lambda *args, **kwargs: next(answers))

    pages = etape5.fetch_pages("http://fake", {}, "X")

    assert len(pages) == 2
    assert pages[1][1] == ["b"]


def test_get_json_retries_after_a_timeout(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise requests.ReadTimeout("trop lent")
        return FakeResponse({"ok": True})

    monkeypatch.setattr(etape5.requests, "get", fake_get)
    monkeypatch.setattr(etape5.time, "sleep", lambda seconds: None)

    assert etape5.get_json("http://fake", {}) == {"ok": True}
    assert len(calls) == 2


def test_unknown_indicator_raises_ingestion_error(monkeypatch):
    error_payload = [{"message": [{"id": "120"}]}]
    monkeypatch.setattr(etape5.requests, "get", lambda *args, **kwargs: FakeResponse(error_payload))

    with pytest.raises(etape5.IngestionError):
        etape5.fetch_pages("http://fake", {}, "FAKE.CODE")


def test_load_config_rejects_start_after_end(tmp_path):
    path = tmp_path / "bad.yml"
    path.write_text("period: {start: 2030, end: 2020}\ncountries: [CIV]\n", encoding="utf-8")

    with pytest.raises(ValueError):
        etape5.load_config(path)
