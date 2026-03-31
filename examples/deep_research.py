"""Example: run a deep research query (Pro tier, subscription billing).

Usage:
    MAINLAYER_TOKEN=pro_... python examples/deep_research.py
"""

import os

import httpx

BASE_URL = os.environ.get("RESEARCH_API_URL", "http://localhost:8000")
TOKEN = os.environ.get("MAINLAYER_TOKEN", "pro_demo")  # Pro-tier wallet prefix


def main() -> None:
    query = os.environ.get(
        "QUERY",
        "Analyse the impact of large language models on knowledge work and productivity",
    )

    print(f"Submitting deep research: {query!r}")

    resp = httpx.post(
        f"{BASE_URL}/research",
        json={
            "query": query,
            "depth": "deep",
            "format": "report",
        },
        headers={
            "x-mainlayer-token": TOKEN,
            "x-wallet": TOKEN,
        },
        timeout=60,
    )

    if resp.status_code == 402:
        data = resp.json()
        print(f"\nPayment/quota error: {data.get('detail', {}).get('message', 'Unknown')}")
        print("Set MAINLAYER_TOKEN=pro_<wallet> for Pro tier access.")
        return

    resp.raise_for_status()
    result = resp.json()

    print(f"\n{'=' * 60}")
    print(f"  {result['title']}")
    print("=" * 60)
    print(f"ID           : {result['id']}")
    print(f"Depth        : {result['depth']}")
    print(f"Format       : {result['format']}")
    print(f"Confidence   : {result['confidence_score']:.0%}")
    print(f"Word count   : {result['word_count']}")
    print(f"Processing   : {result['processing_time_ms']} ms")
    print(f"Billing mode : {result['billing_mode']}")
    if result.get("cost_usd") is not None:
        print(f"Cost         : ${result['cost_usd']:.4f}")

    print("\nSources consulted:")
    for i, src in enumerate(result["sources"], 1):
        print(f"  {i}. {src['title']} ({src['relevance_score']:.0%} relevance)")
        print(f"     {src['url']}")

    print("\nFull report:")
    print(result["content"])


if __name__ == "__main__":
    main()
