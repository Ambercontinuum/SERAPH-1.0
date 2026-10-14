# Public research alpha: provenance and validation

Publication target: `https://github.com/Ambercontinuum/seraph-open`.
Prepared on 2026-10-14 from reviewed source snapshot
`95ef9971734a61b7ad6fd531627d1f3114a42f5d`, with publication-specific changes.
This repository begins with fresh history. The migration receipt and original
development history remain in the private research archive.

Amber Anson directed the architecture, constraints, integration audience, and
release decisions. Claude and OpenAI Codex assisted with implementation,
critique, and verification. The working process does not establish novelty or
superiority over other research methods. See [design lineage](design_lineage.md)
for foundations and claim boundaries.

The public set includes the kernel, generic adapters, examples, tests, formal
definitions, documentation, and CI. It excludes raw conversations, scratchpad
notes, private history, agent state, credentials, local runtime binaries,
machine-specific launch helpers, and the uncommitted Claude Code hook. No
private methods report or proprietary application topology is published here.

## Additional release work

- Removed unsupported tool-name-derived symbolic-pressure observations.
  Missing pressure remains distinct from observed zero; explicit evidence and
  required-evidence gates remain active.
- Added HTTP fault injection. Testing exposed missing response-shape validation:
  incomplete replies could throw in the hook rather than return an explicit
  blocking result. Invalid shapes now produce `seraph_invalid_response`.
- Added `validation/` to Docker's package source and excluded local build state
  from Docker context. Docker execution was not tested locally.
- Moved the SDK needed only by the CHANDRA live example to the optional
  `chandra` extra. The core kernel requires no cloud-model SDK.
- CI uses pytest to include five cases omitted by unittest discovery, installs
  locked Node dependencies, and has no automatic npm publication step.
- Replaced the machine-dependent deployment walkthrough with a generic local
  setup and added contributor and security-boundary documentation.

## Evidence on the prepared source

| Check | Result |
|---|---|
| Python pytest suite | 180 passed |
| Python unittest discovery | 175 passed; five pytest-style cases are additional |
| Runtime-governance corpus | 17/17 passed |
| Demo scenarios | 8/8 passed |
| Python OpenClaw simulation | 6/6 passed |
| TypeScript build | Passed |
| Host-event motion ledger | 8/8 passed |
| Plugin plus real temporary HTTP sidecar | 7/7 passed |
| Local HTTP fault injection | 8/8 passed |
| Lean build and independent proof replay | Passed; 13 build jobs |
| Source distribution and wheel build | Passed |
| Fresh wheel install outside checkout | CLI, demos, web export, and 17-case corpus passed |

Fault injection covers HTTP 500, malformed JSON, missing fields, unknown
decisions, invalid reason fields, a valid allow control, the intentional
warn-only bypass, and connection refusal. It does not test every networking
failure or establish an upper bound on request latency.

Earlier private live-host checks used a pinned OpenClaw/Ollama deployment.
Reads executed; exec was blocked by environment policy without invented
pressure. The model duplicated requested calls and one combined trial timed
out. Those limitations remain; the live pilot is not a broad compatibility
or reliability claim, and raw agent logs are not part of this publication.

The integration cases include a denied short read/write history and an admitted
read/read/write control. FLUX policy thresholds are unchanged. Some short or alternating read/write
histories can still be held for fragmentation or oscillation. Passing the
current corpus does not establish a useful policy for every workload.

Formal results cover their definitions, not automatic refinement of Python or
truth of external telemetry. See [validation](validation.md) and
[security boundaries](../SECURITY.md). The GitHub CI result is separately
inspectable in the repository's Actions tab; local checks do not imply CI passed.
