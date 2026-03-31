"""Example: run a basic research query (free tier, quick depth).

Usage:
    python examples/basic_research.py
"""

import os

import httpx

BASE_URL = os.environ.get("RESEARCH_API_URL", "http://localhost:8000")


def main() -> None:
    print("Submitting research query (free tier, quick depth)...")

    resp = httpx.post(
        f"{BASE_URL}/research",
        json={
            "query": "What are the main benefits of renewable energy?",
            "depth": "quick",
            "format": "summary",
        },
        timeout=30,
    )

    if resp.status_code == 402:
        data = resp.json()
        print(f"Quota exceeded: {data.get('detail', {}).get('message', 'Unknown')}")
        return

    resp.raise_for_status()
    result = resp.json()

    print(f"\nTitle       : {result['title']}")
    print(f"Result ID   : {result['id']}")
    print(f"Depth       : {result['depth']}")
    print(f"Confidence  : {result['confidence_score']:.0%}")
    print(f"Word count  : {result['word_count']}")
    print(f"Sources     : {len(result['sources'])}")

    print("\nKey findings:")
    for finding in result["key_findings"]:
        print(f"  • {finding}")

    print("\nContent preview:")
    print(result["content"][:400] + "...")

    print(f"\nFetch result later: GET {BASE_URL}/research/{result['id']}")


if __name__ == "__main__":
    main()
