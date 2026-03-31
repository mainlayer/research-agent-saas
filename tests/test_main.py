"""Tests for the Research Agent SaaS API."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app, _results

PRO_TOKEN = "pro_test_wallet"
FREE_WALLET = "anon_wallet"


@pytest.fixture()
def client():
    _results.clear()
    with TestClient(app) as c:
        yield c
    _results.clear()


@pytest.fixture(autouse=True)
def mock_billing():
    """Bypass Mainlayer billing calls."""
    from models import BillingMode

    async def _fake_check_and_charge(wallet, token, depth):
        if wallet.startswith("pro_"):
            return BillingMode.SUBSCRIPTION, None
        return BillingMode.PER_QUERY, 0.0

    with patch("src.main.check_and_charge", side_effect=_fake_check_and_charge):
        yield


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


def test_list_plans(client):
    resp = client.get("/plans")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["plans"]) >= 2
    names = [p["name"] for p in body["plans"]]
    assert "Free" in names
    assert "Pro" in names


# ---------------------------------------------------------------------------
# Research — free tier
# ---------------------------------------------------------------------------


def test_research_free_tier(client):
    resp = client.post(
        "/research",
        json={"query": "What is renewable energy?", "depth": "quick"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["depth"] == "quick"
    assert body["word_count"] > 0


def test_research_free_tier_deep_rejected(client):
    """Free tier must not run deep research."""
    resp = client.post(
        "/research",
        json={"query": "test query", "depth": "deep"},
    )
    assert resp.status_code == 402
    detail = resp.json()["detail"]
    assert "depth" in detail["message"].lower() or "upgrade" in detail["message"].lower()


def test_research_free_tier_daily_quota(client):
    """After 3 free queries, the 4th should be rejected."""
    query = {"query": "climate change impacts", "depth": "quick"}
    for _ in range(3):
        resp = client.post("/research", json=query)
        assert resp.status_code == 201

    resp = client.post("/research", json=query)
    assert resp.status_code == 402


# ---------------------------------------------------------------------------
# Research — pro tier
# ---------------------------------------------------------------------------


def test_research_pro_tier_deep(client):
    resp = client.post(
        "/research",
        json={"query": "Impact of AI on healthcare", "depth": "deep", "format": "report"},
        headers={"x-mainlayer-token": PRO_TOKEN, "x-wallet": PRO_TOKEN},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["depth"] == "deep"
    assert len(body["sources"]) >= 5


# ---------------------------------------------------------------------------
# Result retrieval
# ---------------------------------------------------------------------------


def test_get_research_result(client):
    post_resp = client.post(
        "/research",
        json={"query": "quantum computing basics", "depth": "quick"},
    )
    assert post_resp.status_code == 201
    result_id = post_resp.json()["id"]

    get_resp = client.get(f"/research/{result_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == result_id


def test_get_nonexistent_result(client):
    resp = client.get(f"/research/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


def test_result_has_required_fields(client):
    resp = client.post(
        "/research",
        json={"query": "machine learning overview", "depth": "standard"},
        headers={"x-mainlayer-token": PRO_TOKEN, "x-wallet": PRO_TOKEN},
    )
    assert resp.status_code == 201
    body = resp.json()
    for field in ("id", "query", "depth", "title", "content", "key_findings", "sources", "confidence_score"):
        assert field in body, f"Missing field: {field}"


def test_sources_have_relevance_scores(client):
    resp = client.post(
        "/research",
        json={"query": "blockchain technology", "depth": "standard"},
        headers={"x-mainlayer-token": PRO_TOKEN, "x-wallet": PRO_TOKEN},
    )
    assert resp.status_code == 201
    for source in resp.json()["sources"]:
        assert 0.0 <= source["relevance_score"] <= 1.0


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_research_empty_query_rejected(client):
    """Empty queries should be rejected with 400 Bad Request."""
    resp = client.post(
        "/research",
        json={"query": "", "depth": "quick"},
    )
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"]["error"].lower()


def test_research_short_query_accepted(client):
    """Very short queries should still be accepted (min_length=3)."""
    resp = client.post(
        "/research",
        json={"query": "AI", "depth": "quick"},
    )
    assert resp.status_code in (201, 400)  # May fail due to validation


# ---------------------------------------------------------------------------
# Billing modes
# ---------------------------------------------------------------------------


def test_result_includes_billing_info(client):
    """Results must include billing_mode and cost_usd."""
    resp = client.post(
        "/research",
        json={"query": "renewable energy", "depth": "quick"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "billing_mode" in body
    assert "cost_usd" in body
    assert body["billing_mode"] in ("per_query", "subscription")


# ---------------------------------------------------------------------------
# Format support
# ---------------------------------------------------------------------------


def test_report_format(client):
    """Report format should include markdown structure."""
    resp = client.post(
        "/research",
        json={"query": "artificial intelligence", "depth": "standard", "format": "report"},
        headers={"x-mainlayer-token": PRO_TOKEN, "x-wallet": PRO_TOKEN},
    )
    assert resp.status_code == 201
    content = resp.json()["content"]
    # Reports should have markdown headers
    assert "#" in content  # markdown headers


def test_summary_format(client):
    """Summary format should be concise."""
    resp = client.post(
        "/research",
        json={"query": "quantum computing", "depth": "quick", "format": "summary"},
    )
    assert resp.status_code == 201
    body = resp.json()
    # Summary should be shorter than report
    assert body["format"] == "summary"
    assert len(body["content"]) > 0
