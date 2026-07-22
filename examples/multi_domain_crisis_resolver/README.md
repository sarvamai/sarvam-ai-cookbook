# Multi-Domain Crisis Resolver

A LangChain cookbook built on `sarvam-105b` that resolves crises faced by India's informal-sector
workers -- auto drivers, construction laborers, street vendors -- whose health, financial, and legal
problems rarely arrive one at a time. A hospitalization is also lost income; lost income can become a
loan default; a loan default can become a legal dispute. This notebook orchestrates domain-expert
LangChain chains and then reasons across their outputs to catch exactly those interactions.

## Features

- **Dynamic triage**: a structured-output call decides which of health, financial, and legal domains
  a case actually touches, so a purely financial crisis never pays for a health or legal chain it
  doesn't need
- **Parallel domain experts**: three grounded LangChain chains (health, financial, legal), each
  returning a typed Pydantic assessment, run concurrently via `RunnableParallel`
- **Reasoning-mode synthesis**: a second `sarvam-105b` call with `reasoning_effort="high"` reasons in
  plain text over every domain assessment together to surface cross-domain risks, then a lightweight
  call fits that answer into a structured action plan
- **Grounded, not hallucinated**: every chain is restricted to citing scheme names and helpline
  numbers from a curated resource list, instead of relying on the model to recall them
- Full trace (triage, domain assessments, reasoning, and final plan) saved as JSON to `outputs/`

## Getting Started

### Prerequisites

- Python 3.10+ (required by `langchain-sarvamai`)
- Jupyter (or VS Code / another notebook-capable editor)
- A Sarvam AI API key

### Getting your API key

1. Visit the [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for a new account (1,000 free credits on signup)
3. Generate a key from the API Keys section

### Setup

```bash
cd examples/multi_domain_crisis_resolver
cp .env.example .env        # then paste your key into .env
pip install -r requirements.txt
jupyter notebook multi_domain_crisis_resolver.ipynb
```

## Usage

Run the notebook top to bottom. It resolves two sample cases:

```python
case_1 = CrisisCase(
    profile=WorkerProfile(
        occupation="auto-rickshaw driver",
        location="Bengaluru, Karnataka",
        monthly_income_range_inr="9000-12000",
        dependents=3,
    ),
    narrative="Ramesh fractured his leg in a road accident...",
)

result_1 = resolve_crisis(case_1)
```

The first case (`Ramesh`) touches all three domains and shows the full pipeline, including the
cross-domain risks the synthesis step catches. The second case (`Sunita`) is purely financial and
shows triage correctly skipping the health and legal chains. Both results are saved to `outputs/`.

To resolve your own case, construct a `CrisisCase` with a `WorkerProfile` and a free-text `narrative`,
then call `resolve_crisis(case)`.

## Architecture

```
CrisisCase
    |
    v
triage_chain (DomainTriage: which domains apply?)
    |
    v
RunnableParallel of only the relevant domain chains
    health_chain -> HealthAssessment
    financial_chain -> FinancialAssessment
    legal_chain -> LegalAssessment
    |
    v
synthesis_draft_chain (reasoning_effort="high", plain text + reasoning_content)
    |
    v
structure_chain (fits the draft into CrisisResolutionPlan)
```

Each domain chain and the synthesis prompt are grounded with `KNOWN_RESOURCES`, a curated list of
real Indian welfare schemes and helplines (Ayushman Bharat, PM Jan Dhan Yojana, PM SVANidhi, NALSA,
and others), so the model cites from that list rather than inventing scheme names or phone numbers.

## Disclaimer

This notebook demonstrates LLM orchestration patterns -- structured output, dynamic parallel chains,
reasoning-then-structure synthesis -- not verified advice. The schemes, eligibility details, and
helpline numbers referenced are illustrative and may go stale. Confirm them against official sources
before sharing this output with a real worker; it is not a substitute for professional legal, medical,
or financial advice.

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Build with Sarvam AI in LangChain**: [docs.sarvam.ai/api/integration/langchain](https://docs.sarvam.ai/api/integration/langchain)
- **Chat Completions overview**: [docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview](https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/overview)
- **Reasoning effort**: [docs.sarvam.ai/api/api-guides-tutorials/chat-completion/how-to/adjust-the-models-thinking-level](https://docs.sarvam.ai/api/api-guides-tutorials/chat-completion/how-to/adjust-the-models-thinking-level)
- **langchain-sarvamai on GitHub**: [github.com/sarvamai/langchain-sarvam](https://github.com/sarvamai/langchain-sarvam)
- **Community**: [Join the Discord Community](https://discord.com/invite/5rAsykttcs)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)
