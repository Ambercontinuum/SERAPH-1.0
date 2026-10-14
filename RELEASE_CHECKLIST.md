# SERAPH Release Checklist

SERAPH is package-ready before it is public-release-ready. Use this checklist
before publishing to PyPI, creating GitHub releases, or tagging npm packages.

## Release Posture

- Confirm the intended release label: private candidate, public alpha, or
  production-facing release.
- Confirm version in `pyproject.toml` and `seraph/server.py`.
- Confirm README status language still says "research artifact and formalized
  prototype" unless the certification posture has changed.
- Confirm adapters are clearly marked as core, example, or experimental.
- Confirm wheel contents stay limited to `seraph/`, Python `adapters/`,
  `seraph_demo/`, and the public `validation/` harness unless a release
  explicitly expands that boundary.
- Confirm attribution language for MCC, FLUX, SENTINEL, AEGIS, Claude Code, and
  OpenAI Codex is current.
- Confirm every published validation claim is supported by a named case and
  preserves the claim boundaries in `docs/validation.md`.

## Verification Gates

Run these from the repository root:

```powershell
python -m pip install -e ".[serve,test]"
python -m pytest -q
python -m seraph --pretty
python -m seraph_demo --quiet
python -m validation.runtime_governance --output runtime-governance-report.json
python -m seraph_demo.web_export
python adapters\openclaw\test_adapter.py
python -m build --sdist --wheel
```

If Node/npm is available, also run:

```powershell
Set-Location adapters\openclaw
npm install
npm run build
npm run validate:ledger
npm run validate:failures
Set-Location ..\..
```

## Publication Gates

- Do not publish to PyPI until Amber explicitly approves public release.
- For a migration from private development, create a new clean publication
  repository and migrate an explicitly reviewed artifact set. This repository
  is the resulting public research snapshot; preserve that disclosure boundary.
- Do not copy private Git history into the publication repository. Bind the
  migration receipt to the reviewed working-source commit and the new public
  root commit.
- Exclude raw transcripts, research prototypes, internal repository paths,
  private topology, Optimus calibration and implementation detail, and other
  non-public working material from the migration set.
- Package publication requires a separate explicit release decision; this CI
  validates source and artifacts without publishing to PyPI or npm.
- Do not add API tokens, private endpoint URLs, private repository paths, or
  unpublished research notes to release artifacts.
- Confirm AGPL-3.0 licensing and commercial licensing notes are intentional.
- Confirm `CHANGELOG.md` has a dated release entry before publication.

## Final Smoke Test

In a fresh environment, install the package and verify:

```powershell
python -m pip install .
seraph --pretty
seraph-demo --quiet
seraph-demo-export --output seraph-demo-data.js
```
