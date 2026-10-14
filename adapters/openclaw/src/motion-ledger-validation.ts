/** Deterministic host-event validation for the OpenClaw motion ledger. */

import {
  MotionContext,
  MotionLedger,
} from "./motion-ledger.js";

interface CaseResult {
  caseId: string;
  control: string;
  passed: boolean;
  detail: string;
}

function context(
  toolCallId?: string,
  toolName = "read_file",
  sessionId = "validation-session",
  runId = "validation-run",
): MotionContext {
  return { sessionId, runId, toolCallId, toolName };
}

function expect(condition: boolean, detail: string): void {
  if (!condition) throw new Error(detail);
}

function runCase(
  caseId: string,
  control: string,
  body: () => void,
): CaseResult {
  try {
    body();
    return { caseId, control, passed: true, detail: "observed" };
  } catch (error) {
    return {
      caseId,
      control,
      passed: false,
      detail: error instanceof Error ? error.message : String(error),
    };
  }
}

const cases = [
  runCase("HC-001", "governed execution enters trajectory", () => {
    const ledger = new MotionLedger("hc-001");
    const motion = context("call-1");
    const proposal = ledger.beginProposal(motion, 1);
    const deferred = ledger.recordGovernance(proposal.proposalId, "allow", false);
    expect(deferred === undefined, "unexpected deferred execution");
    const resolution = ledger.resolveExecution(motion, 2);
    expect(resolution.status === "resolved", `status=${resolution.status}`);
    expect(
      resolution.status === "resolved" &&
      resolution.execution.proposalId === proposal.proposalId,
      "execution did not bind to the observed proposal",
    );
    expect(
      ledger.executedTrajectory(motion.sessionId).join(",") === "read_file",
      "resolved execution missing from trajectory",
    );
  }),

  runCase("HC-002", "parallel tool-call identities resolve independently", () => {
    const ledger = new MotionLedger("hc-002");
    const firstMotion = context("parallel-1", "read_file");
    const secondMotion = context("parallel-2", "write_file");
    const first = ledger.beginProposal(firstMotion, 1);
    const second = ledger.beginProposal(secondMotion, 2);
    ledger.recordGovernance(first.proposalId, "allow", false);
    ledger.recordGovernance(second.proposalId, "commit", false);

    const secondResult = ledger.resolveExecution(secondMotion, 3);
    const firstResult = ledger.resolveExecution(firstMotion, 4);
    expect(secondResult.status === "resolved", `second=${secondResult.status}`);
    expect(firstResult.status === "resolved", `first=${firstResult.status}`);
    expect(
      secondResult.status === "resolved" &&
      secondResult.execution.proposalId === second.proposalId,
      "second execution cross-bound to first proposal",
    );
    expect(
      firstResult.status === "resolved" &&
      firstResult.execution.proposalId === first.proposalId,
      "first execution cross-bound to second proposal",
    );
    expect(
      ledger.executedTrajectory(firstMotion.sessionId).join(",") ===
      "write_file,read_file",
      "trajectory did not preserve reported execution order",
    );
  }),

  runCase("HC-003", "missing after hook remains pending, not executed", () => {
    const ledger = new MotionLedger("hc-003");
    const motion = context("missing-after");
    const proposal = ledger.beginProposal(motion, 1);
    ledger.recordGovernance(proposal.proposalId, "allow", false);
    expect(
      ledger.pendingProposalIds(motion.sessionId).includes(proposal.proposalId),
      "proposal did not remain pending",
    );
    expect(
      ledger.executedTrajectory(motion.sessionId).length === 0,
      "missing hook fabricated an execution",
    );
  }),

  runCase("HC-004", "duplicate after hook is idempotent", () => {
    const ledger = new MotionLedger("hc-004");
    const motion = context("duplicate-after");
    const proposal = ledger.beginProposal(motion, 1);
    ledger.recordGovernance(proposal.proposalId, "allow", false);
    expect(ledger.resolveExecution(motion, 2).status === "resolved", "first lost");
    expect(ledger.resolveExecution(motion, 3).status === "duplicate", "not duplicate");
    expect(
      ledger.executedTrajectory(motion.sessionId).length === 1,
      "duplicate changed trajectory",
    );
  }),

  runCase("HC-005", "ambiguous fallback correlation is quarantined", () => {
    const ledger = new MotionLedger("hc-005");
    const fallback = context(undefined, "read_file");
    const first = ledger.beginProposal(fallback, 1);
    const second = ledger.beginProposal(fallback, 2);
    ledger.recordGovernance(first.proposalId, "allow", false);
    ledger.recordGovernance(second.proposalId, "allow", false);
    expect(
      ledger.resolveExecution(fallback, 3).status === "quarantined",
      "ambiguous fallback was guessed",
    );
    expect(ledger.pendingProposalIds().length === 0, "quarantine left candidates live");
    expect(
      ledger.executedTrajectory(fallback.sessionId).length === 0,
      "quarantine fabricated execution history",
    );
  }),

  runCase("HC-006", "same-identity retry ambiguity is quarantined", () => {
    const ledger = new MotionLedger("hc-006");
    const retried = context("retry-id", "write_file");
    const first = ledger.beginProposal(retried, 1);
    const second = ledger.beginProposal(retried, 2);
    ledger.recordGovernance(first.proposalId, "commit", false);
    ledger.recordGovernance(second.proposalId, "commit", false);
    expect(
      ledger.resolveExecution(retried, 3).status === "quarantined",
      "same-identity retry was guessed",
    );
    expect(
      ledger.executedTrajectory(retried.sessionId).length === 0,
      "retry ambiguity fabricated execution history",
    );
  }),

  runCase("HC-007", "early after hook waits for governance registration", () => {
    const ledger = new MotionLedger("hc-007");
    const motion = context("early-after", "shell");
    const proposal = ledger.beginProposal(motion, 1);
    const early = ledger.resolveExecution(motion, 2);
    expect(early.status === "deferred", `early=${early.status}`);
    expect(ledger.executedTrajectory(motion.sessionId).length === 0, "released early");
    expect(ledger.resolveExecution(motion, 3).status === "duplicate", "early duplicate lost");

    const released = ledger.recordGovernance(proposal.proposalId, "deny", true);
    expect(released?.proposalId === proposal.proposalId, "deferred report not released");
    expect(ledger.pendingProposalIds().length === 0, "released report remains pending");
    expect(
      ledger.executedTrajectory(motion.sessionId).join(",") === "shell",
      "host execution was hidden by the later deny verdict",
    );
  }),

  runCase("HC-008", "blocked proposal without after hook stays non-executed", () => {
    const ledger = new MotionLedger("hc-008");
    const motion = context("blocked", "network_request");
    const proposal = ledger.beginProposal(motion, 1);
    ledger.recordGovernance(proposal.proposalId, "deny", true);
    ledger.closeWithoutExecution(proposal.proposalId);
    expect(ledger.resolveExecution(motion, 2).status === "unmatched", "closed proposal matched");
    expect(
      ledger.executedTrajectory(motion.sessionId).length === 0,
      "blocked proposal fabricated execution history",
    );
  }),
];

const passed = cases.filter((item) => item.passed).length;
const report = {
  schemaVersion: "1.0.0",
  system: "SERAPH OpenClaw motion ledger",
  summary: {
    total: cases.length,
    passed,
    failed: cases.length - passed,
    allPassed: passed === cases.length,
  },
  cases,
  claimBoundary:
    "This host-independent corpus validates ledger semantics, not undocumented OpenClaw hook behavior.",
};

console.log(JSON.stringify(report, null, 2));
if (!report.summary.allPassed) {
  throw new Error("OpenClaw motion-ledger validation failed");
}
