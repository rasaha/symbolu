# Cloud Platform Evaluation for Symbol-U / Cognade Labs

**Date:** 2026-03-26
**Status:** Recommendation Complete

## Stack Summary

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic |
| Frontend | React 18, TypeScript, Vite, Zustand, Tailwind CSS |
| LLM Providers | Anthropic Claude (primary), Google Gemini (secondary) |
| Storage (current) | In-memory SessionStore (dict-based, thread-safe) |
| Storage (future) | PostgreSQL (CTM+), Redis (CTM+), Generic KV |
| AI/ML | 48-phase deterministic pipeline, Phase Attention Transformer, CUDA/DeepSpeed (CTM+/PCAM) |
| Deployment (current) | Heroku (Procfile), GitHub Actions CI/CD |
| Auth | API key, rate limiting, tier-based licensing (Enterprise/Consumer/Dev) |

## Platform Comparison

| Factor | AWS | Google Cloud (GCP) | Azure |
|--------|-----|-------------------|-------|
| Python/FastAPI hosting | Excellent (ECS, Lambda, App Runner) | Excellent (Cloud Run, GKE) | Good (App Service, AKA) |
| LLM API proximity | Anthropic on Bedrock (native) | Gemini native; Claude via Vertex AI | OpenAI-focused; no native Claude |
| GPU for PCAM/CTM+ | P4/A10/A100 (EC2, SageMaker) | TPUs + A100s (best price/perf) | A100s available but pricier |
| Managed PostgreSQL | RDS — mature | Cloud SQL — solid | Azure Database — good |
| Managed Redis | ElastiCache — excellent | Memorystore — good | Azure Cache — good |
| Startup cost | Free tier generous; complex pricing | $300 credit; pay-per-request Cloud Run | $200 credit; BizSpark |
| Serverless containers | App Runner / Fargate | Cloud Run (best fit) | Container Apps |
| Static frontend hosting | S3 + CloudFront | Firebase Hosting + CDN | Blob + CDN |
| Complexity | Highest | Moderate — developer-friendly | Moderate — enterprise-oriented |
| Enterprise B2B readiness | Best (Fortune 500 dominant) | Good — growing | Strong — Microsoft ecosystem |

## Recommendation: Google Cloud Platform (GCP)

### Why GCP

1. **Dual LLM provider alignment** — Claude available via Vertex AI Model Garden; Gemini is native to GCP. Lowest latency and tightest integration for both providers from a single cloud.

2. **Cloud Run fits FastAPI perfectly** — Heroku Procfile maps directly to Cloud Run. Auto-scaling, pay-per-request, zero cost when idle. No Kubernetes complexity unless needed later.

3. **Best AI/ML infrastructure for the roadmap** — PCAM and CTM+ (CUDA/DeepSpeed) need GPU compute. GCP offers TPUs and A100s at the best price/performance. Vertex AI unifies model deployment.

4. **Cost efficiency for a startup** — Pay-per-request beats always-on. $300 free credit + generous free tier. Simpler pricing than AWS.

5. **Developer experience** — `gcloud` CLI is straightforward. Firebase Hosting for React. Cloud SQL (PostgreSQL) and Memorystore (Redis) ready when moving off in-memory. GitHub Actions integrates via Workload Identity Federation.

### When to consider AWS

- Enterprise customers mandate AWS (finance, healthcare, government)
- Going all-in on Anthropic Bedrock and dropping Gemini
- Need AWS-specific services like SageMaker

### When to consider Azure

- Targeting Microsoft ecosystem customers (Teams, Office 365)
- Pivoting to OpenAI as primary LLM provider

## Suggested GCP Architecture

```
React Frontend → Firebase Hosting (CDN)
        ↓
FastAPI Backend → Cloud Run (auto-scaling containers)
        ↓
┌───────────────────────────────────────┐
│  Cloud SQL (PostgreSQL) — persistence │
│  Memorystore (Redis) — session/cache  │
│  Vertex AI — Claude + Gemini APIs     │
│  GCE/GKE + GPUs — PCAM/CTM+ compute  │
│  Cloud Storage — artifacts/logs       │
│  Secret Manager — API keys            │
└───────────────────────────────────────┘
```

## Migration Path from Heroku

1. **Phase 1:** Containerize FastAPI → deploy to Cloud Run
2. **Phase 2:** Move React frontend to Firebase Hosting
3. **Phase 3:** Add Cloud SQL (PostgreSQL) + Memorystore (Redis)
4. **Phase 4:** Route LLM calls through Vertex AI
5. **Phase 5:** Provision GPU instances for PCAM/CTM+ workloads
