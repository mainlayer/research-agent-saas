"""Subscription tier definitions and quota enforcement.

Free tier : 3 searches/day, `quick` depth only.
Pro tier  : unlimited queries, all depths.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date
from typing import Optional

from models import (
    BillingMode,
    Plan,
    PlanFeatures,
    ResearchDepth,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plan definitions
# ---------------------------------------------------------------------------

PLANS: list[Plan] = [
    Plan(
        id="free",
        name="Free",
        tier=SubscriptionTier.FREE,
        price_per_month_usd=0.0,
        price_per_query_usd=None,
        features=PlanFeatures(
            max_queries_per_month=90,  # 3/day * 30
            max_depth=ResearchDepth.QUICK,
            streaming_enabled=False,
            history_retention_days=7,
            priority_processing=False,
            export_formats=["text"],
        ),
        description="3 quick searches per day, no credit card required.",
    ),
    Plan(
        id="starter",
        name="Starter",
        tier=SubscriptionTier.STARTER,
        price_per_month_usd=9.0,
        price_per_query_usd=0.10,
        features=PlanFeatures(
            max_queries_per_month=200,
            max_depth=ResearchDepth.STANDARD,
            streaming_enabled=True,
            history_retention_days=30,
            priority_processing=False,
            export_formats=["text", "markdown"],
        ),
        description="Pay per query at $0.10. Up to 200 queries/month.",
    ),
    Plan(
        id="pro",
        name="Pro",
        tier=SubscriptionTier.PRO,
        price_per_month_usd=29.0,
        price_per_query_usd=None,
        features=PlanFeatures(
            max_queries_per_month=None,  # unlimited
            max_depth=ResearchDepth.DEEP,
            streaming_enabled=True,
            history_retention_days=365,
            priority_processing=True,
            export_formats=["text", "markdown", "json", "pdf"],
        ),
        description="Unlimited searches, all depths. Best for power users.",
        popular=True,
    ),
    Plan(
        id="enterprise",
        name="Enterprise",
        tier=SubscriptionTier.ENTERPRISE,
        price_per_month_usd=99.0,
        price_per_query_usd=None,
        features=PlanFeatures(
            max_queries_per_month=None,
            max_depth=ResearchDepth.DEEP,
            streaming_enabled=True,
            history_retention_days=730,
            priority_processing=True,
            export_formats=["text", "markdown", "json", "pdf", "docx"],
        ),
        description="Unlimited searches, dedicated support, SLA.",
    ),
]

_TIER_BY_ID = {p.id: p for p in PLANS}

# ---------------------------------------------------------------------------
# Daily quota tracking (in-memory; replace with Redis in production)
# ---------------------------------------------------------------------------

FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "3"))

# Maps wallet -> {date_str -> count}
_daily_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def _today() -> str:
    return date.today().isoformat()


def _get_daily_count(wallet: str) -> int:
    return _daily_counts[wallet][_today()]


def _increment_daily_count(wallet: str) -> None:
    _daily_counts[wallet][_today()] += 1


# ---------------------------------------------------------------------------
# Tier resolution (stub — replace with Mainlayer subscription lookup)
# ---------------------------------------------------------------------------


async def get_tier(wallet: str) -> SubscriptionTier:
    """Resolve the subscription tier for a wallet.

    In production, query the Mainlayer entitlements API.
    For this demo, wallets prefixed with 'pro_' are treated as Pro tier,
    everything else is Free.
    """
    if not wallet or wallet in ("anonymous", ""):
        return SubscriptionTier.FREE
    if wallet.startswith("pro_") or wallet.startswith("ent_"):
        return SubscriptionTier.PRO
    if wallet.startswith("start_"):
        return SubscriptionTier.STARTER
    return SubscriptionTier.FREE


# ---------------------------------------------------------------------------
# Quota check
# ---------------------------------------------------------------------------


def can_run_research(
    tier: SubscriptionTier,
    depth: ResearchDepth,
    wallet: str,
) -> tuple[bool, str]:
    """Return (allowed, reason).

    - Free tier: max 3 queries/day, quick depth only.
    - Starter/Pro/Enterprise: no depth restriction, quota per plan.
    """
    plan = _TIER_BY_ID.get(tier.value)
    if not plan:
        return False, f"Unknown tier: {tier}"

    # Depth check
    depth_order = [ResearchDepth.QUICK, ResearchDepth.STANDARD, ResearchDepth.DEEP]
    max_depth_idx = depth_order.index(plan.features.max_depth)
    requested_idx = depth_order.index(depth)
    if requested_idx > max_depth_idx:
        return (
            False,
            f"Depth '{depth.value}' requires a higher plan. "
            f"Upgrade at mainlayer.fr to unlock '{depth.value}' searches.",
        )

    # Daily quota for free tier
    if tier == SubscriptionTier.FREE:
        count = _get_daily_count(wallet)
        if count >= FREE_DAILY_LIMIT:
            return (
                False,
                f"Free tier limit of {FREE_DAILY_LIMIT} searches/day reached. "
                "Upgrade to Pro at mainlayer.fr for unlimited searches.",
            )
        _increment_daily_count(wallet)

    return True, "ok"
