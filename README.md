# Prior Authorization AI Economics Demo

A simple Streamlit teaching app that connects model sensitivity/specificity to prior-authorization workflow economics.

## What it demonstrates

The app has two tabs:

1. **Existing workflow** — portal → RN → human MD. Defaults reproduce the supplied workbook baseline as a deterministic funnel: 1,000 initial cases, 700 portal approvals, 300 RN reviews, 120 MD reviews, 60 denials, $18,000 review cost, and $60,000 gross savings.
2. **Model implementation** — adds a nurse model and an MD model. You can vary model sensitivity and specificity, plus workflow costs.

The central teaching point is visible in the MD-model value decomposition: a human MD review costs $100 by default, while a missed inappropriate case forfeits $1,000 in denial savings. A model can therefore have apparently strong statistical performance and still destroy business value.

## Definitions / assumptions

- **Positive class = inappropriate / denial-worthy.**
- **Sensitivity** = fraction of truly inappropriate cases flagged for escalation rather than approved.
- **Specificity** = fraction of truly appropriate cases correctly approved rather than unnecessarily escalated.
- The **human MD is treated as the reference standard** for the exercise.
- In the Existing Workflow tab, the workbook's 6% is treated as the observed detected inappropriate / denial rate produced by the funnel, not as true underlying inappropriate prevalence.
- In the Model Implementation tab, portal approvals are still assumed to be deterministic **safe approvals of appropriate cases only** until that tab is revised.

## Run locally

```bash
cd prior_auth_demo
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`.

## Run tests

```bash
pytest -q
```

## Package structure

```text
prior_auth_demo/
├── app.py
├── prior_auth/
│   ├── __init__.py
│   └── engine.py
├── tests/
│   └── test_engine.py
├── requirements.txt
└── README.md
```

## Suggested classroom use

Start with the Existing Workflow tab and show how approval rates create the observed denial rate and baseline economics.

On the Model tab, vary MD sensitivity around 90–100%. Compare the value of MD reviews avoided with the denial value lost to false negatives. This makes the distinction between **statistical metrics** and **business metrics** concrete.
