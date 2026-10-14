/**
 * Separates tool proposals from host-reported executions.
 *
 * Governance evaluates the current proposal against prior correlated execution
 * history. A proposal enters that history only after OpenClaw emits a matching
 * after_tool_call event.
 */

export interface MotionContext {
  sessionId: string;
  runId?: string;
  toolCallId?: string;
  toolName: string;
}

export interface SeraphObservedProposal extends MotionContext {
  proposalId: string;
  observedAtMs: number;
  governanceDecision?: string;
  governanceBlocked?: boolean;
}

export interface HostReportedExecution extends MotionContext {
  proposalId: string;
  eventId: string;
  reportedAtMs: number;
}

export type ExecutionResolution =
  | { status: "resolved"; execution: HostReportedExecution }
  | { status: "deferred"; proposalId: string }
  | { status: "duplicate" }
  | { status: "quarantined" }
  | { status: "unmatched" };

function contextKey(context: MotionContext): string | undefined {
  if (!context.toolCallId) return undefined;
  return JSON.stringify([
    context.sessionId,
    context.runId ?? null,
    context.toolCallId,
  ]);
}

function sameFallbackContext(
  proposal: SeraphObservedProposal,
  context: MotionContext,
): boolean {
  return (
    proposal.sessionId === context.sessionId &&
    proposal.runId === context.runId &&
    proposal.toolName === context.toolName
  );
}

export class MotionLedger {
  private sequence = 0;
  private readonly instanceId: string;
  private readonly proposals = new Map<string, SeraphObservedProposal>();
  private readonly pendingIds = new Set<string>();
  private readonly pendingByKey = new Map<string, string[]>();
  private readonly completedKeys = new Set<string>();
  private readonly quarantinedContexts = new Set<string>();
  private readonly executedBySession = new Map<string, string[]>();
  private readonly deferredByProposal = new Map<string, HostReportedExecution>();

  constructor(instanceId: string = globalThis.crypto.randomUUID()) {
    this.instanceId = instanceId;
  }

  beginProposal(context: MotionContext, observedAtMs = Date.now()): SeraphObservedProposal {
    this.sequence += 1;
    const proposal: SeraphObservedProposal = {
      ...context,
      proposalId:
        `seraph-proposal-${this.instanceId}-${observedAtMs}-${this.sequence}`,
      observedAtMs,
    };
    this.proposals.set(proposal.proposalId, proposal);
    this.pendingIds.add(proposal.proposalId);

    const key = contextKey(context);
    if (key) {
      const pending = this.pendingByKey.get(key) ?? [];
      pending.push(proposal.proposalId);
      this.pendingByKey.set(key, pending);
    }
    return proposal;
  }

  recordGovernance(
    proposalId: string,
    decision: string,
    blocked: boolean,
  ): HostReportedExecution | undefined {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) return undefined;
    proposal.governanceDecision = decision;
    proposal.governanceBlocked = blocked;
    const deferred = this.deferredByProposal.get(proposalId);
    if (!deferred) return undefined;
    this.deferredByProposal.delete(proposalId);
    this.completeExecution(proposal);
    return deferred;
  }

  closeWithoutExecution(proposalId: string): void {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) return;
    this.pendingIds.delete(proposalId);
    this.deferredByProposal.delete(proposalId);
    const key = contextKey(proposal);
    if (!key) return;
    const pending = (this.pendingByKey.get(key) ?? []).filter(
      (candidate) => candidate !== proposalId,
    );
    if (pending.length === 0) this.pendingByKey.delete(key);
    else this.pendingByKey.set(key, pending);
  }

  executedTrajectory(sessionId: string): string[] {
    return [...(this.executedBySession.get(sessionId) ?? [])];
  }

  pendingProposalIds(sessionId?: string): string[] {
    return [...this.pendingIds].filter((proposalId) => {
      if (sessionId === undefined) return true;
      return this.proposals.get(proposalId)?.sessionId === sessionId;
    });
  }

  private completeExecution(proposal: SeraphObservedProposal): void {
    this.closeWithoutExecution(proposal.proposalId);
    const key = contextKey(proposal);
    if (key) this.completedKeys.add(key);

    const history = this.executedBySession.get(proposal.sessionId) ?? [];
    history.push(proposal.toolName);
    this.executedBySession.set(proposal.sessionId, history);
  }

  private quarantineContext(
    quarantineKey: string,
    candidateIds: string[],
  ): ExecutionResolution {
    this.quarantinedContexts.add(quarantineKey);
    for (const proposalId of candidateIds) {
      this.closeWithoutExecution(proposalId);
    }
    return { status: "quarantined" };
  }

  resolveExecution(
    context: MotionContext,
    reportedAtMs = Date.now(),
  ): ExecutionResolution {
    const key = contextKey(context);
    const quarantineKey = key ?? JSON.stringify([
      "fallback",
      context.sessionId,
      context.runId ?? null,
      context.toolName,
    ]);
    if (this.quarantinedContexts.has(quarantineKey)) {
      return { status: "quarantined" };
    }
    if (key && this.completedKeys.has(key)) return { status: "duplicate" };

    let candidateIds: string[];
    if (key) {
      candidateIds = [...(this.pendingByKey.get(key) ?? [])];
    } else {
      candidateIds = [...this.proposals.values()]
        .filter(
          (proposal) =>
            this.pendingIds.has(proposal.proposalId) &&
            sameFallbackContext(proposal, context),
        )
        .map((proposal) => proposal.proposalId);
    }

    if (candidateIds.length === 0) return { status: "unmatched" };
    if (candidateIds.length !== 1) {
      return this.quarantineContext(quarantineKey, candidateIds);
    }

    const proposalId = candidateIds[0];
    const proposal = this.proposals.get(proposalId);
    if (!proposal) return { status: "unmatched" };
    if (this.deferredByProposal.has(proposalId)) return { status: "duplicate" };

    const execution: HostReportedExecution = {
      ...context,
      proposalId,
      eventId: `seraph-execution-${proposalId}`,
      reportedAtMs,
    };
    if (proposal.governanceDecision === undefined) {
      this.deferredByProposal.set(proposalId, execution);
      return { status: "deferred", proposalId };
    }

    this.completeExecution(proposal);
    return { status: "resolved", execution };
  }
}
