"""Mainlayer billing integration — entitlement checks and per-query payments.

Base URL: https://api.mainlayer.fr
Auth:     Authorization: Bearer <api_key>
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import HTTPException, status

from models import (
    BillingMode,
    EntitlementCheck,
    EntitlementStatus,
    PaymentResult,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)

MAINLAYER_API_URL = os.getenv("MAINLAYER_API_URL", "https://api.mainlayer.fr")
MAINLAYER_API_KEY = os.getenv("MAINLAYER_API_KEY", "")
PER_QUERY_PRICE_USD = 0.10
REQUEST_TIMEOUT = 10.0


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {MAINLAYER_API_KEY}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Subscription tier mapping
# ---------------------------------------------------------------------------

_TIER_MAP: dict[str, SubscriptionTier] = {
    "free": SubscriptionTier.FREE,
    "starter": SubscriptionTier.STARTER,
    "pro": SubscriptionTier.PRO,
    "enterprise": SubscriptionTier.ENTERPRISE,
}


def _parse_tier(raw: Optional[str]) -> Optional[SubscriptionTier]:
    if not raw:
        return None
    return _TIER_MAP.get(raw.lower())


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def check_entitlement(
    wallet: str,
    endpoint: str,
    require_subscription: bool = False,
) -> EntitlementCheck:
    """Check whether a wallet is entitled to call *endpoint*.

    Logic:
    - If the wallet holds an active subscription, access is granted via
      ``BillingMode.SUBSCRIPTION`` with no per-call charge.
    - If no subscription exists and *require_subscription* is False the caller
      can pay per-query (``BillingMode.PER_QUERY``).
    - If no subscription exists and *require_subscription* is True, access is
      denied with ``EntitlementStatus.SUBSCRIPTION_REQUIRED``.

    When the Mainlayer API is unreachable (e.g. during local development with
    no key set), the function falls back to ``PER_QUERY`` mode so the service
    remains usable.
    """
    if not MAINLAYER_API_KEY:
        logger.warning(
            "MAINLAYER_API_KEY not set — falling back to per-query mode for wallet=%s",
            wallet,
        )
        if require_subscription:
            return EntitlementCheck(
                wallet=wallet,
                endpoint=endpoint,
                status=EntitlementStatus.SUBSCRIPTION_REQUIRED,
                message="A subscription plan is required to access this endpoint.",
            )
        return EntitlementCheck(
            wallet=wallet,
            endpoint=endpoint,
            status=EntitlementStatus.ALLOWED,
            billing_mode=BillingMode.PER_QUERY,
            message="Per-query billing applies ($0.10 per request).",
        )

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                f"{MAINLAYER_API_URL}/v1/entitlements",
                headers=_headers(),
                params={"wallet": wallet, "endpoint": endpoint},
            )

        if response.status_code == 200:
            data = response.json()
            active_subscription = data.get("active_subscription", False)
            tier_raw = data.get("tier")
            remaining = data.get("remaining_queries")

            if active_subscription:
                return EntitlementCheck(
                    wallet=wallet,
                    endpoint=endpoint,
                    status=EntitlementStatus.ALLOWED,
                    tier=_parse_tier(tier_raw),
                    billing_mode=BillingMode.SUBSCRIPTION,
                    remaining_queries=remaining,
                    message="Subscription active — no per-query charge.",
                )

            if require_subscription:
                return EntitlementCheck(
                    wallet=wallet,
                    endpoint=endpoint,
                    status=EntitlementStatus.SUBSCRIPTION_REQUIRED,
                    message="A subscription plan is required to access this endpoint.",
                )

            return EntitlementCheck(
                wallet=wallet,
                endpoint=endpoint,
                status=EntitlementStatus.ALLOWED,
                billing_mode=BillingMode.PER_QUERY,
                message="Per-query billing applies ($0.10 per request).",
            )

        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Mainlayer API key.",
            )

        if response.status_code == 403:
            return EntitlementCheck(
                wallet=wallet,
                endpoint=endpoint,
                status=EntitlementStatus.DENIED,
                message="Access denied by Mainlayer.",
            )

        # Unexpected status — fail open to per-query for non-streaming
        logger.error("Unexpected Mainlayer status %s", response.status_code)
        if require_subscription:
            return EntitlementCheck(
                wallet=wallet,
                endpoint=endpoint,
                status=EntitlementStatus.SUBSCRIPTION_REQUIRED,
                message="Could not verify subscription. Please try again.",
            )
        return EntitlementCheck(
            wallet=wallet,
            endpoint=endpoint,
            status=EntitlementStatus.ALLOWED,
            billing_mode=BillingMode.PER_QUERY,
            message="Per-query billing applies ($0.10 per request).",
        )

    except httpx.RequestError as exc:
        logger.warning("Mainlayer API unreachable: %s — falling back to per-query", exc)
        if require_subscription:
            return EntitlementCheck(
                wallet=wallet,
                endpoint=endpoint,
                status=EntitlementStatus.SUBSCRIPTION_REQUIRED,
                message="Billing service temporarily unavailable.",
            )
        return EntitlementCheck(
            wallet=wallet,
            endpoint=endpoint,
            status=EntitlementStatus.ALLOWED,
            billing_mode=BillingMode.PER_QUERY,
            message="Per-query billing applies ($0.10 per request). Billing service offline.",
        )


async def charge_per_query(wallet: str, amount_usd: float = PER_QUERY_PRICE_USD) -> PaymentResult:
    """Deduct a per-query charge from the wallet via Mainlayer.

    Returns a :class:`PaymentResult`.  When the API key is absent the call is
    a no-op and returns a synthetic successful result (development mode).
    """
    if not MAINLAYER_API_KEY:
        logger.warning(
            "MAINLAYER_API_KEY not set — skipping charge of $%.2f for wallet=%s",
            amount_usd,
            wallet,
        )
        return PaymentResult(
            success=True,
            transaction_id="dev-mode-no-charge",
            amount_usd=amount_usd,
            wallet=wallet,
            message="Development mode — charge not applied.",
        )

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                f"{MAINLAYER_API_URL}/v1/pay",
                headers=_headers(),
                json={
                    "wallet": wallet,
                    "amount_usd": amount_usd,
                    "description": "Research Agent — per-query charge",
                },
            )

        data = response.json()

        if response.status_code in (200, 201):
            return PaymentResult(
                success=True,
                transaction_id=data.get("transaction_id"),
                amount_usd=amount_usd,
                wallet=wallet,
                message="Payment successful.",
            )

        if response.status_code == 402:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=data.get("message", "Insufficient balance to complete the request."),
            )

        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Mainlayer API key.",
            )

        logger.error("Mainlayer /pay returned %s: %s", response.status_code, data)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing service returned an unexpected error.",
        )

    except HTTPException:
        raise
    except httpx.RequestError as exc:
        logger.error("Mainlayer /pay request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing service temporarily unavailable. Please retry.",
        )
