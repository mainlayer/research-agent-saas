"""Research logic — structured mock research engine.

In production, replace ``_fetch_sources`` and ``_synthesize`` with calls to
real search APIs (e.g. Tavily, Bing, Perplexity) and an LLM summarisation
layer.  The public surface (``run_research`` / ``stream_research``) stays the
same, so no changes to the API layer are required.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import random
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from models import (
    BillingMode,
    ResearchDepth,
    ResearchFormat,
    ResearchResult,
    ResearchSource,
    StreamChunk,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Depth configuration
# ---------------------------------------------------------------------------

_DEPTH_CONFIG: dict[ResearchDepth, dict[str, Any]] = {
    ResearchDepth.QUICK: {
        "num_sources": 3,
        "num_findings": 3,
        "latency_ms": (200, 600),
        "word_multiplier": 1,
        "confidence_base": 0.65,
    },
    ResearchDepth.STANDARD: {
        "num_sources": 6,
        "num_findings": 5,
        "latency_ms": (600, 1400),
        "word_multiplier": 2,
        "confidence_base": 0.78,
    },
    ResearchDepth.DEEP: {
        "num_sources": 10,
        "num_findings": 8,
        "latency_ms": (1400, 3000),
        "word_multiplier": 4,
        "confidence_base": 0.90,
    },
}

# ---------------------------------------------------------------------------
# Deterministic content generation helpers
# ---------------------------------------------------------------------------


def _seed_from_query(query: str) -> int:
    """Derive a stable integer seed from a query string."""
    digest = hashlib.md5(query.encode()).hexdigest()
    return int(digest[:8], 16)


def _make_title(query: str) -> str:
    q = query.strip().rstrip("?").title()
    return f"Research Report: {q}"


def _make_sources(query: str, n: int) -> list[ResearchSource]:
    rng = random.Random(_seed_from_query(query))
    domains = [
        "research.example.com",
        "journal.academic.org",
        "papers.science.io",
        "database.scholarly.net",
        "archive.knowledge.edu",
        "review.expert.co",
        "data.institute.org",
        "hub.publications.com",
        "library.university.edu",
        "digest.professional.io",
    ]
    sources = []
    for i in range(n):
        domain = domains[i % len(domains)]
        slug = query.lower().replace(" ", "-")[:30]
        title_words = query.split()
        title = " ".join(title_words[:4]).title() if title_words else "Reference"
        sources.append(
            ResearchSource(
                title=f"{title} — Study {i + 1}",
                url=f"https://{domain}/articles/{slug}-{i + 1}",
                relevance_score=round(rng.uniform(0.72, 0.99), 2),
                excerpt=(
                    f"This source examines {query.lower()} from a systematic perspective, "
                    f"providing evidence-based insights relevant to the research question. "
                    f"Key data points include statistical analysis across multiple domains."
                ),
            )
        )
    sources.sort(key=lambda s: s.relevance_score, reverse=True)
    return sources


def _make_findings(query: str, n: int) -> list[str]:
    templates = [
        f"Primary analysis of {query} reveals significant patterns across multiple data sources.",
        f"Cross-referencing studies on {query} shows consistent evidence supporting the main hypothesis.",
        f"Quantitative metrics for {query} indicate a measurable trend over the observed period.",
        f"Expert consensus on {query} aligns with the majority of reviewed literature.",
        f"Emerging research on {query} introduces nuanced perspectives not captured in earlier work.",
        f"Comparative analysis places {query} within a broader context of related phenomena.",
        f"Methodological review of {query} studies highlights robust and reproducible findings.",
        f"Longitudinal data on {query} demonstrates stability of core conclusions over time.",
    ]
    rng = random.Random(_seed_from_query(query) ^ 0xDEADBEEF)
    selected = rng.sample(templates, min(n, len(templates)))
    return selected[:n]


def _make_summary(query: str, findings: list[str]) -> str:
    intro = (
        f"This report presents a synthesised analysis of available knowledge on the topic: "
        f'"{query}". Drawing from peer-reviewed literature, authoritative databases, and '
        f"expert commentary, the following conclusions have been reached.\n\n"
    )
    body = "\n\n".join(f"**Finding {i + 1}:** {f}" for i, f in enumerate(findings))
    outro = (
        "\n\n**Conclusion:** The evidence reviewed supports a well-grounded understanding "
        f'of "{query}". Further investigation may be warranted in areas where source '
        "consensus is below 80%."
    )
    return intro + body + outro


def _make_report(query: str, findings: list[str], sources: list[ResearchSource]) -> str:
    sections = [
        f"# Research Report: {query.title()}\n",
        "## Executive Summary\n",
        (
            f'This comprehensive report investigates "{query}" through systematic analysis '
            f"of {len(sources)} authoritative sources. The research employed structured "
            "methodology to ensure objectivity and reproducibility.\n"
        ),
        "## Key Findings\n",
        "\n".join(f"- {f}" for f in findings),
        "\n## Detailed Analysis\n",
        (
            f'The investigation into "{query}" reveals a multifaceted landscape of evidence. '
            "Primary sources demonstrate consistent patterns that have been validated across "
            "independent datasets. Secondary literature corroborates these observations and "
            "provides additional context that enriches the overall understanding.\n\n"
            "Quantitative analysis shows measurable outcomes that align with theoretical "
            "frameworks established in prior research. Where discrepancies exist, they have "
            "been noted and attributed to methodological variance between studies.\n"
        ),
        "## Sources\n",
        "\n".join(
            f"{i + 1}. [{s.title}]({s.url}) — Relevance: {s.relevance_score:.0%}"
            for i, s in enumerate(sources)
        ),
        "\n## Methodology\n",
        (
            "Research was conducted using a structured literature review protocol. Sources "
            "were ranked by relevance score and cross-validated for consistency. Confidence "
            "scoring reflects the degree of consensus across reviewed materials.\n"
        ),
    ]
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_research(
    query: str,
    depth: ResearchDepth,
    fmt: ResearchFormat,
    billing_mode: BillingMode,
    cost_usd: float | None,
) -> ResearchResult:
    """Run a research query and return a structured result."""
    cfg = _DEPTH_CONFIG[depth]
    start_ms = time.monotonic() * 1000

    lo, hi = cfg["latency_ms"]
    await asyncio.sleep(random.uniform(lo / 1000, hi / 1000))

    sources = _make_sources(query, cfg["num_sources"])
    findings = _make_findings(query, cfg["num_findings"])

    if fmt == ResearchFormat.REPORT:
        content = _make_report(query, findings, sources)
    else:
        content = _make_summary(query, findings)

    elapsed_ms = int(time.monotonic() * 1000 - start_ms)
    word_count = len(content.split())

    rng = random.Random(_seed_from_query(query) ^ int(depth.value.__hash__()))
    confidence = round(
        min(cfg["confidence_base"] + rng.uniform(-0.05, 0.05), 1.0),
        2,
    )

    logger.info(
        "Research complete query=%r depth=%s format=%s words=%d latency_ms=%d",
        query,
        depth.value,
        fmt.value,
        word_count,
        elapsed_ms,
    )

    return ResearchResult(
        id=uuid4(),
        query=query,
        depth=depth,
        format=fmt,
        title=_make_title(query),
        content=content,
        key_findings=findings,
        sources=sources,
        confidence_score=confidence,
        word_count=word_count,
        processing_time_ms=elapsed_ms,
        billing_mode=billing_mode,
        cost_usd=cost_usd,
    )


async def stream_research(
    query: str,
    depth: ResearchDepth,
    fmt: ResearchFormat,
) -> AsyncIterator[StreamChunk]:
    """Yield incremental chunks of a research result.

    This generator simulates token-by-token streaming as a real LLM would
    produce.  Replace the body with actual streaming LLM calls in production.
    """
    cfg = _DEPTH_CONFIG[depth]
    sources = _make_sources(query, cfg["num_sources"])
    findings = _make_findings(query, cfg["num_findings"])

    if fmt == ResearchFormat.REPORT:
        full_text = _make_report(query, findings, sources)
    else:
        full_text = _make_summary(query, findings)

    # Split into ~sentence-sized chunks to simulate streaming
    words = full_text.split()
    chunk_size = 12  # words per chunk
    num_chunks = math.ceil(len(words) / chunk_size)

    for i in range(num_chunks):
        chunk_words = words[i * chunk_size : (i + 1) * chunk_size]
        text = " ".join(chunk_words)
        if i < num_chunks - 1:
            text += " "

        is_final = i == num_chunks - 1

        meta: dict[str, Any] | None = None
        if is_final:
            meta = {
                "total_words": len(words),
                "num_sources": len(sources),
                "key_findings_count": len(findings),
            }

        yield StreamChunk(chunk_id=i, content=text, is_final=is_final, metadata=meta)

        # Simulate generation delay
        delay = random.uniform(0.02, 0.07)
        await asyncio.sleep(delay)
