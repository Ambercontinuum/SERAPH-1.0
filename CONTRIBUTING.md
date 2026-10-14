# Contributing

SERAPH is a research alpha. Useful contributions include reproducible defects,
adapter integrations, comparator implementations, and challenges to its claims.
Keep issues free of credentials, private deployment state, and raw conversations.
The [development process report](docs/development-process.md) explains the
project's human-directed AI-assisted workflow. Contributions should preserve
decision rationale and counterexamples without posting private transcripts.

Install Python 3.11 or newer, then run:

```console
python -m pip install -e ".[serve,test]"
python -m pytest -q
python -m validation.runtime_governance
python -m seraph_demo --quiet
```

For OpenClaw, use Node 24 and the host version pinned in package.json:

```console
cd adapters/openclaw
npm ci
npm run build
npm run validate:ledger
```

Run `npm run validate:adapter` with `SERAPH_TEST_URL` pointing at a disposable
local sidecar. Formal contributors should run `lake build` and `lake env
leanchecker` inside `formal/`.

Describe the expected and observed behavior, provide a minimal reproduction,
and state which validation supports your change. Separate a policy proposal
from an implementation correction. Do not silently change scientific thresholds.
