# Research Agent SaaS — Mainlayer

AI-powered research agent with subscription tiers, monetised via [Mainlayer](https://mainlayer.fr).

- **Free**: 3 quick searches/day, no card required
- **Starter**: $9/month or $0.10/query
- **Pro**: $29/month — unlimited, all depths
- **Enterprise**: $99/month — SLA + priority

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/research` | Start a research job |
| `GET` | `/research/{id}` | Fetch results |
| `GET` | `/plans` | List plans |

## Quick start

```bash
pip install -e ".[dev]"
MAINLAYER_API_KEY=sk_... uvicorn src.main:app --reload
```

## Example — free tier

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Benefits of solar energy", "depth": "quick"}'
```

## Example — Pro tier (unlimited)

```bash
curl -X POST http://localhost:8000/research \
  -H "x-wallet: pro_my_wallet" \
  -H "Content-Type: application/json" \
  -d '{"query": "AI impact on knowledge work", "depth": "deep", "format": "report"}'
```

## Depth levels

| Depth | Sources | Latency | Tier |
|-------|---------|---------|------|
| `quick` | 3 | ~0.5s | Free+ |
| `standard` | 6 | ~1s | Starter+ |
| `deep` | 10 | ~2s | Pro+ |

## Running tests

```bash
pytest tests/ -v
```
