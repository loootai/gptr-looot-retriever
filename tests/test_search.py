import json
import logging

import pytest
import requests
import responses

import gptr_looot_retriever as mod
from gptr_looot_retriever import LoootSearch

RUNS = "https://api.looot.ai/v1/runs"
ORGANIC = [
    {"title": "A", "link": "https://a.example/1", "snippet": "first", "position": 1},
    {"title": "B", "link": "https://b.example/2", "snippet": "second", "position": 2},
    {"title": "no link", "snippet": "dropped"},
]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("LOOOT_TOKEN", "test-token")
    monkeypatch.delenv("LOOOT_API_BASE", raising=False)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)


def done(organic=ORGANIC):
    return {"runId": "run_1", "status": "completed", "result": {"organic": organic}}


@responses.activate
def test_request_shape_and_mapping():
    responses.post(RUNS, json=done())
    out = LoootSearch("rust async").search(max_results=5)
    assert out == [
        {"href": "https://a.example/1", "body": "first"},
        {"href": "https://b.example/2", "body": "second"},
    ]
    req = responses.calls[0].request
    assert req.url == f"{RUNS}?wait=30"
    assert req.headers["Authorization"] == "Bearer test-token"
    body = json.loads(req.body)
    assert body["endpointId"] == "serper-search"
    assert body["input"] == {"q": "rust async", "num": 5}
    assert len(body["idempotencyKey"]) == 36


@responses.activate
def test_idempotency_key_is_fresh_per_call():
    responses.post(RUNS, json=done())
    r = LoootSearch("q")
    r.search()
    r.search()
    keys = {json.loads(c.request.body)["idempotencyKey"] for c in responses.calls}
    assert len(keys) == 2


@responses.activate
def test_domain_filter_matches_serper_retriever():
    responses.post(RUNS, json=done())
    LoootSearch("llm agents", query_domains=["arxiv.org", "github.com"]).search()
    q = json.loads(responses.calls[0].request.body)["input"]["q"]
    assert q == "llm agents site:arxiv.org OR site:github.com"


@responses.activate
def test_polls_until_completed():
    responses.post(RUNS, json={"runId": "run_1", "status": "running"})
    responses.get(f"{RUNS}/run_1", json={"runId": "run_1", "status": "running"})
    responses.get(f"{RUNS}/run_1", json=done())
    out = LoootSearch("q").search()
    assert [r["href"] for r in out] == ["https://a.example/1", "https://b.example/2"]
    assert len(responses.calls) == 3


@responses.activate
def test_poll_deadline_returns_empty(monkeypatch, caplog):
    monkeypatch.setattr(mod, "POLL_DEADLINE", 0)
    responses.post(RUNS, json={"runId": "run_1", "status": "running"})
    with caplog.at_level(logging.WARNING):
        assert LoootSearch("q").search() == []
    assert "deadline" in caplog.text


@responses.activate
@pytest.mark.parametrize("status", ["failed", "blocked", "stopped"])
def test_unsuccessful_run_returns_empty_and_warns(status, caplog):
    responses.post(
        RUNS,
        json={"runId": "r", "status": status, "error": {"code": "provider_error", "message": "boom"}},
    )
    with caplog.at_level(logging.WARNING):
        assert LoootSearch("q").search() == []
    assert "boom" in caplog.text


@responses.activate
def test_http_error_returns_empty():
    responses.post(RUNS, status=401, json={"error": "unauthorized"})
    assert LoootSearch("q").search() == []


@responses.activate
def test_network_error_returns_empty():
    responses.post(RUNS, body=requests.ConnectionError("down"))
    assert LoootSearch("q").search() == []


@responses.activate
def test_invalid_json_returns_empty():
    responses.post(RUNS, body="not json", status=200)
    assert LoootSearch("q").search() == []


@responses.activate
@pytest.mark.parametrize("result", [None, "x", {}, {"organic": None}])
def test_unexpected_result_shape_returns_empty(result):
    responses.post(RUNS, json={"runId": "r", "status": "completed", "result": result})
    assert LoootSearch("q").search() == []


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("LOOOT_TOKEN")
    with pytest.raises(Exception, match="LOOOT_TOKEN"):
        LoootSearch("q")


def test_requires_scraping():
    assert LoootSearch.requires_scraping is True
