"""Mainlayer billing for the Research Agent SaaS.

Per-query charges are applied when a wallet does not hold an active
subscription.  The module delegates to mainlayer.py for the actual HTTP call.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from fastapi import HTTPException, status

from models import BillingMode, ResearchDepth, SubscriptionTier

logger = logging.getLogger(__name__)

MAINLAYER_API_KEY = os.getenv("MAINLAYER_API_KEY", "")

# Price per query by depth
DEPTH_PRICES: dict[ResearchDepth, float] = {
    ResearchDepth.QUICK: 0.05,
    ResearchDepth.STANDARD: 0.10,
    ResearchDepth.DEEP: 0.25,
}


async def check_and_charge(
    wallet: str,
    token: str,
    depth: ResearchDepth,
) -> Tuple[BillingMode, Optional[float]]:
    """Determine billing mode and apply a charge if per-query.

    Returns a (billing_mode, cost_usd) tuple.
    - If the wallet has a subscription: returns (SUBSCRIPTION, None).
    - If per-query token provided: charges and returns (PER_QUERY, cost).
    - If neither and dev mode: returns (PER_QUERY, cost) without charging.
    """
    # Pro/Enterprise wallets are covered by subscription
    from .tiers import get_tier
    tier = await get_tier(wallet)
    if tier in (SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE):
        return BillingMode.SUBSCRIPTION, None

    # Free tier — no charge
    if tier == SubscriptionTier.FREE:
        return BillingMode.PER_QUERY, 0.0

    # Starter or unknown — charge per query
    cost = DEPTH_PRICES.get(depth, 0.10)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "payment_required",
                "info": "mainlayer.fr",
                "amount_usd": cost,
                "message": "Supply x-mainlayer-token for per-query billing.",
            },
        )

    if not MAINLAYER_API_KEY:
        logger.debug("Dev mode: skipping charge of $%.4f", cost)
        return BillingMode.PER_QUERY, cost

    from mainlayer import charge_per_query
    await charge_per_query(wallet=wallet, amount_usd=cost)

    return BillingMode.PER_QUERY, cost
