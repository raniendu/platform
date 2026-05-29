# Model Provider Comparison — raman

Local reference doc. Not for commit. Snapshot dated **2026-05-10**. Personal-use
context: CLI + FastAPI on **Pydantic AI**, hosting on DigitalOcean, ~1M input +
500K output tokens/month, OSS-leaning, allergic to ecosystem lock-in.

---

## TL;DR

- **Obvious cheap default:** Gemini 2.5 Flash-Lite (free tier handles your
  volume entirely; pay $0.10/$0.40 if you outgrow it).
- **Obvious quality default:** Sonnet 4.6 ($3/$15) — best tool-calling
  reliability for an assistant, prompt caching halves the bill in practice.
- **Obvious "all on DO" pick:** DigitalOcean Serverless Inference with
  Llama 3.3 70B ($0.65/$0.65) — same billing/region/IAM as your droplets
  and App Platform, OpenAI-compatible endpoint, no SDK lock-in.
- **Skip:** OpenAI for an assistant (more expensive than Anthropic at
  comparable quality and no real upside for your stack), DeepSeek (China
  hosting is a values mismatch for personal-data assistant work), Cerebras
  (overkill for sub-1M tok/month).

---

## Big comparison table

Pricing is per million tokens, input/output. "Ecosystem pull" = how much
adopting this provider would drag your code/infra toward their stack vs.
remaining swappable behind Pydantic AI's `Model` interface.

| Provider | Catalog (cheap → flagship) | $ in/out (range) | Free tier | Tool calling | Prompt caching | Context | Multimodal | Max throughput | OAI-compat | Hosting | Ecosystem pull |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **DO Serverless Inference** | Ministral 3 14B → Llama 3.3 70B → Qwen3-32B → Trinity Large → Anthropic/OpenAI passthrough | $0.20/$0.20 → $5/$25 (Opus 4.7 passthrough) | $25 tier-1 credit | Yes (open-weight + Anthropic); spotty on smaller open models | Yes on Anthropic passthrough | Model-dep (8K–200K) | Limited (Anthropic models only) | ~standard | **Yes** (`inference.do-ai.run/v1/`) | DO regions (NYC/SFO/AMS/etc) | **Low** (pure OAI shim) |
| **Anthropic** | Haiku 4.5 → Sonnet 4.6 → Opus 4.7 | $1/$5 → $5/$25 | Free credits on signup, no permanent tier | **Excellent** — best in class | **Yes, 90% off cached** | 200K | Yes (vision) | ~standard | No (own SDK; OAI-compat exists in beta) | US/EU regions | **Medium** (own SDK common, but Pydantic AI abstracts) |
| **OpenAI** | GPT-5.4-nano → mini → 5.4 → 5.5 | $0.20/$1.25 → $5/$30 | Free credits trial | Excellent | Yes, automatic | 400K (5.4+) | Yes | ~standard | **Native** (everyone copies their API) | US/global | **High** — their schema *is* the standard, but switching off them stays easy |
| **Google Gemini** | Flash-Lite → Flash → 2.5 Pro → Gemini 3 Pro | $0.10/$0.40 → $2/$12 | **1500 req/day Flash via AI Studio, no card** | Yes (good) | Yes (context caching) | 1M–2M | Yes (best multimodal) | ~standard | Partial (OAI-compat endpoint exists) | US/global | **Medium** — pulls toward Google AI Studio + Vertex if you go deep |
| **DeepSeek** | V3.2 | $0.28/$0.42 | Limited credits | Yes | Yes (cached input cheap) | 128K | Text | ~standard | Yes | **China** | Low (just an endpoint) — but data-residency concerns dominate |
| **Groq** | Llama 8B/70B, Qwen3, etc. | $0.05/$0.08 → $0.59/$0.79 | Yes — all models, generous | Yes (varies by model) | No | 8K–128K (model-dep) | Limited | **300–1000 tok/s** | Yes | US | Low |
| **Cerebras** | Llama 8B/70B, Qwen3 | $0.60/$0.80 → $3.90 (range) | 30 RPM / 1M tok/day | Yes | No | Model-dep | No | **1800+ tok/s** | Yes | US | Low |
| **OpenRouter** | 200+ models, every major + open | passthrough + ~5% | Per-model varies | Per-model | Per-model | Per-model | Per-model | Per-model | **Yes** | Routes globally | **Low** (purpose-built to *avoid* lock-in) |
| **Ollama (current dev)** | Any GGUF you pull (gemma4:26b-mlx today) | Free (electricity) | n/a | Yes | No | Model-dep | Limited | Hardware-bound | Yes | **localhost** | None |

---

## DigitalOcean Serverless Inference — deep dive

This is the new info. The old "GenAI Platform" rebranded to **Gradient AI
Platform**, and the raw inference layer underneath it is now exposed
separately as **Serverless Inference** at `inference.do-ai.run/v1/`.

### Inference Engine — the four pillars (April 2026 launch)

DO restructured the inference offering in late April 2026 into a single
"Inference Engine" product with four explicit tiers. Worth knowing the shape
even if raman only uses one of them, because the marketing pages now lead
with this taxonomy:

| Pillar | What it is | When raman would use it |
|---|---|---|
| **Serverless Inference** | Pay-per-token, scale-to-zero, OpenAI-compatible. The `inference.do-ai.run/v1/` endpoint described in the rest of this section. | **Default.** Personal-scale request rate fits cleanly. |
| **Inference Router** | A routing layer that picks the cheapest model in a price/quality band per request. Free during public preview. | Optional. Useful if you want "cheap-by-default, escalate to Sonnet on hard turns" without hand-coding the policy. |
| **Batch Inference** | Submit a job, get results minutes-to-hours later at a steep discount (typically ~50% off real-time). | If you ever run an evals dataset over thousands of prompts, this is where it goes. Not the chat path. |
| **Dedicated Inference** | Reserved GPU capacity (H100/H200/B300, MI300X/MI350X). Hourly billing, predictable latency, no rate-limit ceiling. | Skip. Personal scale never justifies dedicated; the math only works above ~5–10× our token volume. |

For raman, only Serverless is in scope. Inference Router becomes interesting
*after* you've shipped a baseline and want auto-cost-optimization without
writing it yourself.

### What's actually available

Two sets of models, two billing models:

1. **DO-hosted open-weight models** — billed by DO per-token, prices align
   with the typical open-weight market. These run on DO's own GPU fleet
   (H100/H200/B300, AMD MI300X/MI350X) and your prompts/completions are
   **not logged or used for training**. Examples (May 2026):
   - Ministral 3 14B (Mistral) — **$0.20 / $0.20**
   - Qwen3-32B (Alibaba) — **$0.25 / $0.55**
   - Llama 3.3 70B (Meta) — **$0.65 / $0.65**
   - Trinity Large (Arcee) — **$0.25 / $0.90**
   - Kimi K2.5, Minimax M2.5 — **30% off during 05:00–11:00 UTC** (off-peak)
2. **Commercial passthrough** — Anthropic (Claude Haiku/Sonnet/Opus) and
   OpenAI (GPT-5.x). Two billing modes:
   - DO-managed key: billed *by DO* at provider-published rates. One
     consolidated invoice.
   - BYO API key: billed directly by Anthropic/OpenAI; DO is just a router.

### Free tier / credits

- **Tier 1** comes with **$25 included usage** before charges kick in.
- **Inference Router** (model-routing layer that picks the cheapest model that
  can handle a given request) is **free during public preview**.
- BYOM (bring-your-own-weights to DO storage): **$5/month** flat for storage.

### OpenAI-compatible? Yes, fully

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://inference.do-ai.run/v1/",
    api_key=os.environ["DO_INFERENCE_KEY"],
)
client.chat.completions.create(model="llama3.3-70b-instruct", messages=[...])
```

Standard `chat.completions`, `stream=True`, the works. Custom DO **Agents**
(their RAG/knowledge-base wrapper) live under a different base URL
(`https://<agent-id>.agents.do-ai.run/api/v1/`) and accept an
`extra_body={"include_retrieval_info": True}` flag — you can ignore that
entirely if you're not using DO Agents, which you shouldn't be (it's the
ecosystem-pull layer; the raw inference endpoint is the clean swap).

### Tool calling

Reliable on Anthropic and OpenAI passthrough (those models do tool calling
well anywhere). On the open-weight side it varies by model — Llama 3.3 70B
and Qwen3-32B are the safer picks; the small Mistral isn't great at
multi-step tool use. If raman leans on tools heavily, default to Sonnet
passthrough or Llama 3.3 70B on DO.

### Regions

DO has 20 global DCs with GPU capacity (NYC, SFO, AMS, FRA, LON, SGP, BLR,
TOR, SYD, plus the new Richmond AI-native one). Inference routes
automatically; you don't pin regions for serverless, but co-locating with
your App Platform region keeps egress on DO's backbone.

### Integration with the rest of DO

This is the actual reason to consider DO inference:

- **App Platform**: same project, same billing, same VPC for in-region calls.
  Your FastAPI app gets a low-latency private hop to inference instead of
  going out to api.openai.com.
- **Managed Postgres / Spaces**: same IAM, same tags, same monthly bill line.
- **Spaces**: BYOM weights are stored in a service-managed (not user-visible)
  Spaces bucket — the integration is invisible but it's the same underlying
  object store.
- **Observability**: shows up in the same DO monitoring dashboard as your
  droplets. One throat to choke for capacity issues.

### Honest assessment

**Worth it if:**
- You actually deploy on DO App Platform / droplets and want one bill, one
  region, one support contract.
- You'd otherwise route open-weight calls through Groq/Together/OpenRouter
  anyway — DO's open-weight pricing is competitive enough that the
  consolidation wins.
- You want Anthropic Sonnet but prefer one invoice from DO over a separate
  Anthropic relationship (the BYO-key option keeps things vendor-neutral on
  the contract side too).

**Not worth it if:**
- Pure cost-minimization is the goal. Gemini Flash-Lite at $0.10/$0.40 and
  Groq's free tier both beat DO on raw price.
- You want bleeding-edge models day-one. DO's open-weight catalog lags the
  Hugging Face frontier by a few weeks.
- You're not actually hosting other workloads on DO. There's no reason to
  pay DO for inference if you'd otherwise use Anthropic/OpenAI direct.

**Ecosystem pull:** Low **if** you stick to the raw `inference.do-ai.run/v1/`
endpoint via the OpenAI SDK shim. Goes to **High** if you adopt DO Agents,
Knowledge Bases, or the `gradient` CLI workflow — those are the lock-in
layers. For raman, just use the inference endpoint and keep agents in
Pydantic AI.

---

## Personal-use cost math

1M input + 500K output tokens/month. Cheapest viable model per provider.
Excludes prompt-caching savings (which would knock 30–60% off Anthropic in
real usage).

| Provider / Model | Input cost | Output cost | **Monthly** |
|---|---|---|---|
| Ollama gemma4:26b-mlx (current) | — | — | **$0** (electricity) |
| Gemini 2.5 Flash-Lite via AI Studio free tier | — | — | **$0** (1500 req/day covers it) |
| Gemini 2.5 Flash-Lite (paid) | $0.10 | $0.20 | **$0.30** |
| Groq Llama 3.1 8B | $0.05 | $0.04 | **$0.09** |
| DeepSeek V3.2 | $0.28 | $0.21 | **$0.49** |
| Gemini 2.5 Flash | $0.30 | $1.25 | **$1.55** |
| DO Ministral 3 14B | $0.20 | $0.10 | **$0.30** |
| DO Llama 3.3 70B | $0.65 | $0.33 | **$0.98** |
| OpenAI GPT-5.4-nano | $0.20 | $0.63 | **$0.83** |
| OpenAI GPT-5.4-mini | $0.75 | $2.25 | **$3.00** |
| Anthropic Haiku 4.5 | $1.00 | $2.50 | **$3.50** |
| Gemini 2.5 Pro | $1.25 | $5.00 | **$6.25** |
| Groq Llama 70B | $0.59 | $0.40 | **$0.99** |
| Cerebras Llama 70B | ~$0.60 | ~$0.40 | **~$1.00** |
| Anthropic Sonnet 4.6 | $3.00 | $7.50 | **$10.50** |
| OpenAI GPT-5.4 | $2.50 | $7.50 | **$10.00** |
| Gemini 3 Pro | $2.00 | $6.00 | **$8.00** |
| Anthropic Opus 4.7 | $5.00 | $12.50 | **$17.50** |
| OpenAI GPT-5.5 | $5.00 | $15.00 | **$20.00** |
| DO passthrough Sonnet 4.6 | $3.00 | $7.50 | **$10.50** |

For your volume, **everything below $5/month is rounding error**. The
question stops being "what's cheapest" and becomes "what gives me the best
assistant for ~$10/month and which provider's values match mine." If you
stay on Gemini Flash free tier you literally pay $0.

---

## Recommendation matrix

| Want | Pick | Why |
|---|---|---|
| **All on DO, single-platform billing** | DO Serverless Inference + Llama 3.3 70B (default) + Sonnet 4.6 passthrough (hard prompts) | One invoice, one region, one IAM. OpenAI-compatible so swap cost stays zero. |
| **Best free tier** | Gemini 2.5 Flash via AI Studio (1500 req/day, no card) | Your entire monthly volume fits. Period. |
| **Best OSS-aligned (open weights + neutral infra)** | DO Llama 3.3 70B *or* Groq Llama 70B | Open-weight model on a provider that doesn't push proprietary frameworks. DO wins if you're already there; Groq wins on raw $ and speed. |
| **Best assistant quality regardless of cost** | Anthropic Sonnet 4.6 (direct or via DO passthrough) | Best tool-calling, prompt-cache-friendly, ~$10/mo at your volume. |
| **Best speed** | Cerebras (1800+ tok/s) > Groq (300–1000) | Only matters if you're streaming long outputs interactively. For a CLI/FastAPI assistant, both feel instant. |
| **Best ecosystem-neutral commercial option** | OpenRouter (or DO Inference) | OpenRouter exists *to be* a swap layer. DO is neutral as long as you stay on raw inference and skip Agents. |

**If forced to pick one for "personal assistant on DO hosting":**
**DO Serverless Inference, Llama 3.3 70B as default, Sonnet 4.6 passthrough
for hard tool-calling turns.** Single bill, your prompts don't train anyone,
OpenAI-compat shim means you can rip it out in an afternoon.

**Compatibility verified (2026-05-10).** Pydantic AI 1.93.0 ships
`OpenAIChatModel` + `OpenAIProvider(base_url=..., api_key=...)`, and the only
code in raman that names the provider is `raman/settings.py::build_model`.
The swap is ~10 lines: replace the `OllamaModel`/`OllamaProvider` pair with
`OpenAIChatModel("<do-model-id>", provider=OpenAIProvider(base_url=
"https://inference.do-ai.run/v1", api_key=settings.do_inference_api_key))`,
add the env var to `RamanSettings`/`.env.example`/README, and update the
default model id (the current `gemma4:26b-mlx` is an Ollama tag, not a DO catalog
name). Tool calling is the one runtime risk to validate per chosen model —
Llama 3.3 70B and the Anthropic passthrough are the safe picks; smaller
open-weight models in the catalog are inconsistent on multi-step tools.

---

## Wiring snippets for Pydantic AI

Pydantic AI's `OpenAIChatModel` + `OpenAIProvider(base_url=...)` pattern is
the universal escape hatch — works for DO, Ollama, Groq, OpenRouter, vLLM,
anything that speaks OpenAI's wire format.

### DO Serverless Inference

```python
# raman/providers/do.py
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
import os

def do_model(name: str = "llama3.3-70b-instruct") -> OpenAIChatModel:
    return OpenAIChatModel(
        model_name=name,
        provider=OpenAIProvider(
            base_url="https://inference.do-ai.run/v1/",
            api_key=os.environ["DO_INFERENCE_KEY"],
        ),
    )

# Anthropic Sonnet via DO passthrough — same shim, different model string
def do_sonnet() -> OpenAIChatModel:
    return do_model("claude-sonnet-4-6")
```

Then in `build_agent`:

```python
from pydantic_ai import Agent
from raman.providers.do import do_model

agent = Agent(do_model(), system_prompt=spec.system_prompt, tools=[...])
```

### Same shim for Ollama / Groq / OpenRouter

Just swap the `base_url`:

| Provider | base_url | api_key env |
|---|---|---|
| DO | `https://inference.do-ai.run/v1/` | `DO_INFERENCE_KEY` |
| Ollama | `http://localhost:11434/v1/` | `"ollama"` (any string) |
| Groq | `https://api.groq.com/openai/v1/` | `GROQ_API_KEY` |
| Cerebras | `https://api.cerebras.ai/v1/` | `CEREBRAS_API_KEY` |
| OpenRouter | `https://openrouter.ai/api/v1/` | `OPENROUTER_API_KEY` |
| DeepSeek | `https://api.deepseek.com/v1/` | `DEEPSEEK_API_KEY` |
| Gemini (OAI mode) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY` |

### Native providers (when you want first-class features like prompt caching or thinking blocks)

`pydantic-ai-slim[openai,anthropic,google,groq]` extras already give you
typed providers that expose provider-specific knobs (Anthropic prompt
caching, Gemini thinking budget, Groq fast paths) without the OAI shim.

```python
# pyproject.toml
"pydantic-ai-slim[openai,anthropic,google,groq]"

# Anthropic native — gets prompt caching ergonomics
from pydantic_ai.models.anthropic import AnthropicModel
agent = Agent(AnthropicModel("claude-sonnet-4-6"), ...)

# Gemini native — gets thinking budget knob
from pydantic_ai.models.google import GoogleModel
agent = Agent(GoogleModel("gemini-2.5-flash"), ...)
```

Rule of thumb: **OAI shim for swap-friendliness, native providers when you
need a feature only that vendor exposes well** (Anthropic caching, Gemini
context caching + thinking budgets, Groq's deterministic fast-path
selectors).

### Spec-driven model selection

Make the model swap a one-line spec change rather than a code change:

```toml
# spec/raman/agent.toml
[model]
provider = "do"          # do | anthropic | gemini | groq | openrouter | ollama
name = "llama3.3-70b-instruct"
```

```python
# raman/providers/__init__.py
def resolve(provider: str, name: str):
    match provider:
        case "do":         return do_model(name)
        case "anthropic":  return AnthropicModel(name)
        case "gemini":     return GoogleModel(name)
        case "groq":       return groq_model(name)
        case "openrouter": return openrouter_model(name)
        case "ollama":     return ollama_model(name)
        case _: raise ValueError(provider)
```

Now switching providers is editing `agent.toml`, not chasing imports.

---

## Honest tradeoffs called out

- **Gemini free tier is too good to ignore.** For 1M+0.5M tok/month it's
  literally free. The catch: Google AI Studio TOS allows training on
  free-tier prompts. If raman is reading your inbox, that's a
  values-mismatch — pay the $1.55/mo for Flash on the paid endpoint or use
  DO open-weight where DO commits to no-training.
- **OpenAI is a worse buy than Anthropic for your use case.** Sonnet 4.6
  beats GPT-5.4 on tool-calling reliability for assistant-style workflows
  and costs the same. The only reason to pick OpenAI is if you want
  GPT-5.5 specifically for hard reasoning, in which case Opus 4.7 is also
  there at $5 cheaper on output.
- **DeepSeek is the cheapest "real" model but it's hosted in China.** For
  a personal assistant that touches Gmail/Calendar/Drive, that's a hard no
  on data-residency grounds. Skip.
- **Cerebras's speed is a solution looking for your problem.** 1800 tok/s
  is wonderful for batch workloads or live coding. For a CLI that emits a
  paragraph, 300 tok/s already feels instant. Don't pay the premium.
- **OpenRouter is the *ideologically* correct neutral pick** but adds a
  hop and a small markup. If you genuinely want to A/B 10 models, it's
  great. If you've already decided which 2 you'll use, point at them
  directly and skip the middleman.
- **DO Inference vs. native Anthropic on the same model:** identical price,
  identical latency (DO is just a router for passthrough). Pick DO if you
  want one invoice; pick native Anthropic if you want prompt-caching headers
  and the Anthropic SDK's batch API. Pydantic AI's `AnthropicModel` exposes
  caching cleanly; the OAI shim through DO does not.

---

## Sources (for the DO research)

- DigitalOcean Inference Pricing: https://docs.digitalocean.com/products/inference/details/pricing/
- DigitalOcean Inference overview: https://docs.digitalocean.com/products/inference/
- Serverless Inference + OpenAI SDK tutorial: https://www.digitalocean.com/community/tutorials/serverless-inference-openai-sdk
- Gradient AI Platform: https://docs.digitalocean.com/products/gradient-ai-platform/
- DO regional availability: https://docs.digitalocean.com/platform/regional-availability/
