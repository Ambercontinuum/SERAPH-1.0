# How Seraph was made

Public process report, 2026-10-14. Project direction: Amber Anson / Ambercontinuum
Research. Prepared with OpenAI Codex from selected dated development records,
the public implementation, and recorded verification. Claude contributed to
the development and critique described here. This is a retrospective case
account, not an independently audited study or a comparative benchmark.

## Purpose and human direction

Seraph grew through a human-directed, AI-assisted engineering process. The
objective was to turn governance commitments into inspectable constraints,
decisions, execution contracts, and falsifiable examples. A model's persuasive
description of its own behavior was insufficient evidence that those
commitments were enforced.

Amber supplied and corrected the design direction, challenged explanations,
set disclosure boundaries, and decided what the project should serve. One
concrete correction was the integration audience: locally hosted agents and
local models, with OpenClaw and Ollama as the reference pilot. Another was
making the system operable rather than treating a polished architecture
description as a substitute for an actual deployment.

The AI contribution was substantial: Claude and Codex proposed mechanisms,
wrote and revised code and documentation, investigated counterexamples, and
helped run verification. Their roles varied across sessions; they were not
permanently divided into one author and one reviewer. Human direction here
includes architecture, requirements, correction, and release decisions;
implementation assistance and verification are also explicitly credited.
AI-generated output remained subject to inspection and testing.

## Human intent as a runtime governance commitment

Amber's framing is that Seraph should be a "conscience made by you": explicit
human commitments accompany the agent into action. This expresses the purpose
of the architecture. Its technical substance is the constraint, evidence, and
execution contract implemented at a mediated boundary.

Onboarding instructions tell an agent what is expected. Seraph adds a runtime
path where encoded commitments can affect whether a proposed action proceeds,
what evidence is required, and how the result is checked. People remain
responsible for defining, inspecting, and revising those commitments. A runtime
can apply their encoded form repeatedly without a human approving each call;
it does not automatically capture the whole of a person's intent.

This matters to governance research because it connects stated constraints to
inspectable decisions and observed consequences. The public implementation
provides a concrete object for investigating four questions:

- **Completeness:** Which modeled affected entities and consequences must be
  accounted for before a transition is admitted?
- **Uncertainty:** What happens when a required observation is unresolved,
  missing, or refuted?
- **Accountability:** Can authorization be bound to a specific action, and can
  proposals be distinguished from host-reported execution?
- **Continuity:** Can immediate or delayed divergence trigger containment, and
  do commitments remain effective when execution moves through another path?

Users can inspect why Seraph intervened and challenge whether its encoded policy
represents what they meant. That is visibility into the governance layer's
decision, not an explanation of all the model's internal reasoning. Keeping
that distinction explicit makes disagreement actionable: the policy, evidence,
integration, or claim can be examined and corrected.

The ambition extends across tools, delegation, and agent collectives. Current
evidence establishes bounded kernel behavior and the tested host integration;
unmediated code and arbitrary downstream agents do not automatically inherit
enforcement. Demonstrating that commitments remain attached through those
boundaries is a research obligation. See [validation](validation.md),
[execution contracts](manifold_compiler.md), and the
[OpenClaw motion contract](../adapters/openclaw/README.md#motion-contract).

## The collaboration loop

Amber describes the collaboration as a cybernetic feedback loop: distinct
participants propose, observe consequences, challenge one another, revise,
and continue. The practical process used these steps:

1. State the intended behavior and the constraint that must survive a change.
2. Make assumptions explicit and build a concrete implementation or example.
3. Challenge the mechanism with counterexamples, including ordinary useful work.
4. Check the actual source, tools, host events, or primary reference behind a claim.
5. Revise the mechanism or narrow the claim when the evidence requires it.
6. Retain the rationale, test, disagreement, and unresolved boundary for handoff.

In Amber's formulation, care meant preserving participation and the possibility
of truthful correction: shared intent should remain visible, disagreement should
remain possible, and a correction should leave a credible route to improvement.
This is a stated design commitment, not a measured property of model intentions.

The private decision archive preserves more than a change list. Amber required
notes to explain the question, evidence, assumptions, alternatives, tradeoffs,
uncertainties, and what would reverse a conclusion. This is transferable
decision rationale, not hidden model deliberation or a transcript of cognition.
Exclusive checkout leases were used to separate writers and prevent one agent
from committing another participant's unfinished work.

The record is imperfect: some entries were backfilled after reminders, some
claims were corrected, and the agents shared context. A second AI reviewer is
not an independent laboratory, and agreement between agents is not a result.

## Case 1: critique changed affected-set enforcement

September 6 records show a substantive challenge to affected-inhabitant
coverage: an earlier implementation relied on effect subjects and affected
entities supplied by the proposal itself. That could validate a declared set
without independently deriving modeled downstream consequences.

The subsequent implementation added topology-owned consequence edges and
deterministic transitive affected-set closure. Follow-up review also exposed
order-sensitive proposal identity. Canonicalizing a digest alone was
insufficient: evaluation had to produce the same complete certificate for
equivalent reordered inputs.

The present code and regressions let readers inspect these outcomes in
[the manifold compiler](../seraph/manifold.py),
[affected-set tests](../tests/test_affected_set_closure.py), and
[proposal identity tests](../tests/test_manifold_compiler.py).

The surviving limitation matters: closure begins at proposal-declared effect
roots and uses the compiled topology and observed state. It cannot discover a
real effect root that was never declared. The process improved both the
implementation and the accuracy of its claim; it did not eliminate the trusted
proposal and sensor boundary.

## Case 2: both novelty enthusiasm and criticism required correction

The development records contain affirmative novelty arguments and a broad
counterclaim that the mechanisms reduced to existing work. Later review
retracted that counterclaim after checking the cited source and distinguishing
resemblance or expressibility from a demonstrated equivalence.

That retraction did not prove Seraph novel. The release position became a
bounded one: acknowledge established foundations, expose the implementation
and its differences, and leave academic novelty open. The same evidentiary
standard applies to a flattering claim and a hostile one. Neither an agent's
confidence nor the absence of an item in one search settles priority.

The public [design-lineage account](design_lineage.md) documents that position.
This report does not republish the private novelty dossier or claim to have
conducted a new comprehensive literature review.

## Case 3: live use invalidated an apparent pressure signal

In the October local-agent pilot, an ordinary read followed by an exec probe
was labeled as symbolic pressure. Investigation found that tool-name switching
and uniqueness were being converted into a semantic measurement. An operational
sequence did not justify that inference.

Increasing the threshold would have preserved the unsupported measurement.
The correction removed it: the adapter now sends missing pressure as `null`,
distinct from a measured zero. Explicit pressure observations and required-
evidence checks remain separate contracts; environment and trajectory policy
still govern tool use.

The corrected live pilot admitted reads and blocked exec through environment
policy without the invented pressure finding. The small model duplicated tool
requests, and one combined prompt timed out; those failures were retained.
Subsequent [real-sidecar integration cases](../adapters/openclaw/scripts/validate-adapter.mjs)
also check a denied short read/write history and an admitted read/read/write
control. A passing test is not permission to erase inconvenient behavior or
silently tune scientific thresholds for a demonstration.

## Case 4: release testing found another implementation defect

Local HTTP fault injection found that incomplete sidecar replies could throw
inside the host hook instead of producing an explicit blocking result. The
client now checks response shape and rejects invalid decisions or reason fields.
[Fault-injection cases](../adapters/openclaw/scripts/validate-failures.mjs)
include invalid replies, connection refusal, a successful control, and the
deliberate warn-only bypass. This is an implemented failure-handling check,
not a claim to cover all network failures or bound request latency.

Other release checks corrected packaging and operation: including the
validation harness in Docker, testing the installed wheel outside the source
checkout, including pytest-style cases in CI, and deploying the same sidecar
locally in Docker and Kubernetes. Reaching a Ready pod established operation
under that configuration, not correctness for every workload.

## What is public and reproducible

The public repository contains the kernel, adapters, examples, regression
tests, formal definitions, CI, this process account, and a
[local Kubernetes manifest](../deploy/kubernetes/README.md). The initial source
publication begins at commit
`da6a2ed0865984d6c2f0dfa0feacbcd8d61067a0`; the tested container-CI checkpoint is
`bd0a42dbf95bd79e43896bff1b9081f07f9e2396`. Public history starts fresh; private
development history remains archived rather than being exposed through Git.

The [publication record](publication.md) names the validation boundaries.
Readers can reproduce tests and challenge the implementation. Historical
interpretations in this report also rely on selected private decision records,
which readers cannot independently inspect here. They are paraphrased and
attributed, not presented as a complete or externally audited record.

Raw conversations, private research notes, credentials, local agent state,
and proprietary application details are excluded. Disclosing the process does
not require publishing those materials. No controlled supplement is promised.

## What the process does and does not establish

These cases show specific challenges followed by inspectable implementation
or claim changes. They support a descriptive account of how this artifact was
developed. They do not establish that AI-assisted collaboration outperforms
another workflow, that encouragement demonstrates human control, that shared
agent judgments are independent, or that test counts establish safety.

A comparative process study would need a defined task set, comparison method,
predeclared outcomes, records of failures and corrections, and evaluation beyond
the participating agents' judgments. That study has not been performed here.

Seraph's immediate purpose is therefore practical and bounded: an inspectable
research artifact people can run, connect to a host, criticize, and improve.
The [getting-started guide](getting-started.md) is the next step for using it.
