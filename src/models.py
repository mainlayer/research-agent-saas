"""Pydantic models for the Research Agent SaaS."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResearchDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ResearchFormat(str, Enum):
    SUMMARY = "summary"
    REPORT = "report"


class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class BillingMode(str, Enum):
    PER_QUERY = "per_query"
    SUBSCRIPTION = "subscription"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000, description="Research question or topic")
    depth: ResearchDepth = Field(ResearchDepth.STANDARD, description="Research depth level")
    format: ResearchFormat = Field(ResearchFormat.SUMMARY, description="Output format")


class ResearchSource(BaseModel):
    title: str
    url: Optional[str] = None
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    excerpt: str


class ResearchResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    query: str
    depth: ResearchDepth
    format: ResearchFormat
    title: str
    content: str
    key_findings: list[str]
    sources: list[ResearchSource]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    word_count: int
    processing_time_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    billing_mode: BillingMode
    cost_usd: Optional[float] = None


class StreamChunk(BaseModel):
    chunk_id: int
    content: str
    is_final: bool = False
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Plan / subscription models
# ---------------------------------------------------------------------------


class PlanFeatures(BaseModel):
    max_queries_per_month: Optional[int] = None  # None = unlimited
    max_depth: ResearchDepth
    streaming_enabled: bool
    history_retention_days: int
    priority_processing: bool
    export_formats: list[str]


class Plan(BaseModel):
    id: str
    name: str
    tier: SubscriptionTier
    price_per_month_usd: float
    price_per_query_usd: Optional[float] = None
    features: PlanFeatures
    description: str
    popular: bool = False


class PlansResponse(BaseModel):
    plans: list[Plan]
    per_query_price_usd: float = 0.10


# ---------------------------------------------------------------------------
# History models
# ---------------------------------------------------------------------------


class HistoryEntry(BaseModel):
    id: UUID
    query: str
    depth: ResearchDepth
    format: ResearchFormat
    title: str
    billing_mode: BillingMode
    cost_usd: Optional[float]
    created_at: datetime
    word_count: int


class HistoryResponse(BaseModel):
    wallet: str
    entries: list[HistoryEntry]
    total_queries: int
    total_spend_usd: float


# ---------------------------------------------------------------------------
# Mainlayer / billing models
# ---------------------------------------------------------------------------


class EntitlementStatus(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    SUBSCRIPTION_REQUIRED = "subscription_required"


class EntitlementCheck(BaseModel):
    wallet: str
    endpoint: str
    status: EntitlementStatus
    tier: Optional[SubscriptionTier] = None
    billing_mode: Optional[BillingMode] = None
    remaining_queries: Optional[int] = None
    message: str


class PaymentResult(BaseModel):
    success: bool
    transaction_id: Optional[str] = None
    amount_usd: float
    wallet: str
    message: str


# ---------------------------------------------------------------------------
# Error models
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
