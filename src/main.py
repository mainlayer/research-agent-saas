"""Research Agent SaaS — FastAPI application.

Endpoints
---------
POST /research            — start a research job ($0.10/query or subscription)
GET  /research/{id}       — fetch results for a completed job
GET  /plans               — list subscription plans (free)
GET  /health              — health probe (free)
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .billing import check_and_charge
from .researcher import run_research
from .tiers import PLANS, can_run_research, get_tier
from models import (
    BillingMode,
    ErrorDetail,
    ErrorResponse,
    HistoryResponse,
    Plan,
    PlansResponse,
    ResearchDepth,
    ResearchFormat,
    ResearchRequest,
    ResearchResult,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("research-agent")

# ---------------------------------------------------------------------------
# In-memory result store (swap for Redis/DB in production)
# ---------------------------------------------------------------------------

_results: dict[str, ResearchResult] = {}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Research Agent SaaS",
    description=(
        "AI research agent with subscription tiers. "
        "Free tier: 3 searches/day. Pro: unlimited. Powered by Mainlayer."
    ),
    version="1.0.0",
    contact={"name": "Mainlayer", "url": "https://mainlayer.fr"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post(
    "/research",
    response_model=ResearchResult,
    status_code=status.HTTP_201_CREATED,
    tags=["Research"],
    summary="Start a research job ($0.10/query or subscription)",
    responses={402: {"model": ErrorResponse, "description": "Payment required or quota exceeded"}},
)
async def start_research(
    body: ResearchRequest,
    request: Request,
    x_mainlayer_token: str = Header(default="", alias="x-mainlayer-token"),
    x_wallet: str = Header(default="", alias="x-wallet"),
) -> ResearchResult:
    """Submit a research query and receive a structured report.

    - **Free tier** (no token): 3 queries/day, `quick` depth only.
    - **Pro tier** (Mainlayer token): unlimited queries, all depths.

    Supply `x-mainlayer-token` for per-query billing, or `x-wallet` for
    subscription-based access.

    **Pricing:**
    - Free tier: no charge (3/day limit)
    - Per-query: $0.05 (quick), $0.10 (standard), $0.25 (deep)
    - Subscription: included in plan
    """
    # Resolve wallet identity
    wallet = x_wallet or x_mainlayer_token or "anonymous"
    client_ip = request.client.host if request.client else "unknown"

    # Validate request
    if not body.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Query cannot be empty."},
        )

    # Check tier entitlements
    tier = await get_tier(wallet)
    allowed, reason = can_run_research(tier, body.depth, wallet)
    if not allowed:
        logger.warning(
            "research: denied wallet=%s ip=%s reason=%s",
            wallet,
            client_ip,
            reason[:50],
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": "quota_exceeded", "message": reason, "info": "mainlayer.fr"},
        )

    # Charge if per-query billing
    billing_mode, cost_usd = await check_and_charge(
        wallet=wallet,
        token=x_mainlayer_token,
        depth=body.depth,
    )

    # Execute research
    result = await run_research(
        query=body.query,
        depth=body.depth,
        fmt=body.format,
        billing_mode=billing_mode,
        cost_usd=cost_usd,
    )

    _results[str(result.id)] = result

    logger.info(
        "research: id=%s wallet=%s ip=%s query=%r depth=%s sources=%d words=%d cost=$%.4f mode=%s",
        result.id,
        wallet,
        client_ip,
        body.query[:50],
        body.depth.value,
        len(result.sources),
        result.word_count,
        cost_usd or 0,
        billing_mode.value,
    )
    return result


@app.get(
    "/research/{research_id}",
    response_model=ResearchResult,
    tags=["Research"],
    summary="Retrieve a research result by ID",
    responses={404: {"model": ErrorDetail, "description": "Result not found"}},
)
async def get_research(research_id: UUID) -> ResearchResult:
    """Fetch a previously completed research result.

    Results are held in memory; in production store them in a database with
    a TTL appropriate for your retention policy.
    """
    key = str(research_id)
    result = _results.get(key)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Research result '{research_id}' not found."},
        )
    return result


@app.get(
    "/plans",
    response_model=PlansResponse,
    tags=["Plans"],
    summary="List available subscription plans",
)
async def list_plans() -> PlansResponse:
    """Return all available plans and the per-query price."""
    return PlansResponse(plans=PLANS, per_query_price_usd=0.10)


@app.get("/health", tags=["Info"], include_in_schema=False)
async def health() -> dict:
    return {"status": "ok", "service": "research-agent-saas"}


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": str(exc)},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
