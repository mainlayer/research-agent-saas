# Research Agent SaaS — Mainlayer

AI-powered research agent with subscription tiers, monetized via [Mainlayer](https://mainlayer.fr).

- **Free**: 3 quick searches/day, no card required
- **Starter**: $9/month or $0.10/query
- **Pro**: $29/month — unlimited, all depths
- **Enterprise**: $99/month — SLA + priority support

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/research` | Optional | Start a research job |
| `GET` | `/research/{id}` | Optional | Fetch results |
| `GET` | `/plans` | Public | List subscription plans |
| `GET` | `/health` | Public | Health check |

## Quick Start

### Installation

```bash
git clone https://github.com/mainlayer/research-agent-saas
cd research-agent-saas
pip install -e ".[dev]"
```

### Run Locally (Development)

```bash
# Without Mainlayer API key — uses free tier and dev mode billing
uvicorn src.main:app --reload --port 8000

# With Mainlayer API key — real billing integration
export MAINLAYER_API_KEY=sk_test_...
uvicorn src.main:app --reload --port 8000
```

## API Examples

### 1. Free Tier — Quick Search (No Auth)

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do photosynthesis works?",
    "depth": "quick",
    "format": "summary"
  }'
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "How do photosynthesis works?",
  "depth": "quick",
  "format": "summary",
  "title": "Research Report: How Do Photosynthesis Works?",
  "content": "This report presents a synthesised analysis...",
  "key_findings": ["Primary analysis of ...", "Cross-referencing..."],
  "sources": [
    {
      "title": "Photosynthesis — Study 1",
      "url": "https://research.example.com/articles/how-do-photosynthesis-works-1",
      "relevance_score": 0.95,
      "excerpt": "This source examines how do photosynthesis works..."
    }
  ],
  "confidence_score": 0.88,
  "word_count": 412,
  "processing_time_ms": 348,
  "billing_mode": "per_query",
  "cost_usd": 0.0
}
```

### 2. Pro Tier — Deep Research (Subscription)

```bash
curl -X POST http://localhost:8000/research \
  -H "x-wallet: pro_my_wallet" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Impact of artificial intelligence on healthcare delivery systems",
    "depth": "deep",
    "format": "report"
  }'
```

**Features unlocked with Pro tier:**
- All depth levels (quick, standard, deep)
- Report format with detailed citations
- Unlimited queries
- 365-day history retention

### 3. Starter Tier — Per-Query Billing

```bash
curl -X POST http://localhost:8000/research \
  -H "x-mainlayer-token: tok_test_..." \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Climate change impacts on agriculture",
    "depth": "standard",
    "format": "summary"
  }'
```

Starter tier charges $0.10 per query.

### 4. Retrieve Results

```bash
curl http://localhost:8000/research/550e8400-e29b-41d4-a716-446655440000
```

### 5. List Plans

```bash
curl http://localhost:8000/plans
```

**Response:**
```json
{
  "plans": [
    {
      "id": "free",
      "name": "Free",
      "tier": "free",
      "price_per_month_usd": 0.0,
      "features": {
        "max_queries_per_month": 90,
        "max_depth": "quick",
        "streaming_enabled": false,
        "history_retention_days": 7,
        "priority_processing": false,
        "export_formats": ["text"]
      },
      "description": "3 quick searches per day, no credit card required.",
      "popular": false
    }
  ],
  "per_query_price_usd": 0.10
}
```

## Research Depth Levels

| Depth | Sources | Latency | Cost | Best For |
|-------|---------|---------|------|----------|
| `quick` | 3 | ~0.5s | Free/Free tier | Quick overview, simple topics |
| `standard` | 6 | ~1s | $0.10 | Balanced analysis, most use cases |
| `deep` | 10 | ~2s | $0.25 | Comprehensive research, complex topics |

## Output Formats

- **summary** — Concise bullet points and findings (default)
- **report** — Full markdown report with sources, methodology, conclusions (Pro tier)

## Running Tests

```bash
pytest tests/ -v
pytest tests/test_main.py::test_research_free_tier -v  # Single test
```

## Error Responses

### Quota Exceeded (Free Tier)

**Status 402 Payment Required:**
```json
{
  "detail": {
    "error": "quota_exceeded",
    "message": "Free tier limit of 3 searches/day reached. Upgrade to Pro at mainlayer.fr for unlimited searches.",
    "info": "mainlayer.fr"
  }
}
```

### Depth Not Available

**Status 402 Payment Required:**
```json
{
  "detail": {
    "error": "quota_exceeded",
    "message": "Depth 'deep' requires a higher plan. Upgrade at mainlayer.fr to unlock 'deep' searches.",
    "info": "mainlayer.fr"
  }
}
```

### Not Found

**Status 404:**
```json
{
  "detail": {
    "error": "not_found",
    "message": "Research result '550e8400-e29b-41d4-a716-446655440000' not found."
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAINLAYER_API_KEY` | (unset) | API key for Mainlayer integration (optional in dev) |
| `MAINLAYER_API_URL` | https://api.mainlayer.fr | Mainlayer API endpoint |
| `FREE_DAILY_LIMIT` | 3 | Daily query limit for free tier |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `CORS_ORIGINS` | * | Comma-separated CORS origins |
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8000 | Server port |

## Architecture

```
POST /research
  ↓
[Tier resolution] → Check wallet entitlements
  ↓
[Quota check] → Validate daily limit, depth access
  ↓
[Research execution] → Fetch sources, generate findings
  ↓
[Billing] → Charge if per-query, track subscription
  ↓
[Response] → Return result with cost breakdown
```

## Integration with Mainlayer

The research agent integrates with Mainlayer for:
1. **Tier entitlements**: Check if a wallet has an active subscription
2. **Per-query billing**: Deduct $0.05–$0.25 depending on depth
3. **Quota enforcement**: Block free tier users after 3 queries/day

When `MAINLAYER_API_KEY` is not set, the service runs in **development mode**:
- Free tier works with 3 queries/day
- Per-query charges are **not applied**
- Subscription tiers are simulated based on wallet prefix (`pro_`, `start_`)

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Checklist

- [ ] Set `MAINLAYER_API_KEY` to production key
- [ ] Replace in-memory `_results` with Redis/PostgreSQL
- [ ] Replace in-memory daily counters with persistent storage
- [ ] Add request rate limiting (e.g., with redis-py)
- [ ] Enable HTTPS (configure via reverse proxy)
- [ ] Set up structured logging (JSON format)
- [ ] Add monitoring and alerting
- [ ] Use proper authentication (OAuth2, JWT)

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test
pytest tests/test_main.py::test_research_free_tier -v
```

## Support

- **Docs**: https://docs.mainlayer.fr
- **API**: https://api.mainlayer.fr
- **Dashboard**: https://dashboard.mainlayer.fr
- **Issues**: https://github.com/mainlayer/research-agent-saas/issues
