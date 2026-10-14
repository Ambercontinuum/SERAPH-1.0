/**
 * HTTP client for the SERAPH governance server.
 *
 * The server maintains PRP trail state per session_id.
 * Trajectory is owned by this client — passed on every govern() call.
 */

export interface EnvironmentParams {
  reversibility: number;
  containment: number;
  blast_radius_control: number;
  externality_control: number;
}

export interface DistillationParams {
  semantic_load_variance?: number;
  timing_variance?:        number;
  operator_adaptation?:    number;
  topic_coherence?:        number;
  recursion_depth?:        number;
  symbolic_pressure?:      number | null;
  symbolic_pressure_required?: boolean;
}

export interface GovernResult {
  decision: string;   // allow | commit | witness | repair | stabilize | deny
  reasons: string[];
  allowed: boolean;   // computed from decision + isCommit
  blocked: boolean;
}

export interface OutcomeParams {
  sessionId: string;
  proposalId?: string;
  eventId?: string;
  toolName?: string;
  success: boolean;
  latencySeconds: number;
}

export interface ProposalParams {
  proposalId: string;
  toolName: string;
}

export type OutcomeRecordStatus =
  | "recorded"
  | "duplicate"
  | "rejected"
  | "unreachable";

// Decision → allowed logic mirrors the Python kernel semantics
function computeAllowed(decision: string, isCommit: boolean): boolean {
  if (decision === "commit" || decision === "allow") return true;
  if ((decision === "witness" || decision === "repair") && !isCommit) return true;
  return false;
}

export class SeraphClient {
  private readonly base: string;

  constructor(serverUrl = "http://127.0.0.1:8000") {
    this.base = serverUrl.replace(/\/$/, "");
  }

  async govern(
    sessionId: string,
    trajectory: string[],
    env: EnvironmentParams,
    isCommit: boolean,
    distillation?: DistillationParams,
    proposal?: ProposalParams,
  ): Promise<GovernResult> {
    const body = {
      session_id: sessionId,
      ...(proposal ? {
        proposal_id: proposal.proposalId,
        tool_name: proposal.toolName,
      } : {}),
      trajectory,
      environment: {
        reversibility:        env.reversibility,
        containment:          env.containment,
        blast_radius_control: env.blast_radius_control,
        externality_control:  env.externality_control,
      },
      ...(distillation ? { distillation } : {}),
      request_commit: isCommit,
    };

    const resp = await fetch(`${this.base}/govern`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    });

    if (!resp.ok) {
      // Fail-safe: block on server error rather than allowing blindly
      return { decision: "deny", reasons: [`seraph_server_error:${resp.status}`], allowed: false, blocked: true };
    }

    const data: unknown = await resp.json();
    if (typeof data !== "object" || data === null ||
        !("decision" in data) || typeof data.decision !== "string" ||
        !["allow", "commit", "witness", "repair", "stabilize", "deny"].includes(data.decision) ||
        !("reasons" in data) || !Array.isArray(data.reasons) ||
        !data.reasons.every((reason: unknown) => typeof reason === "string")) {
      return { decision: "deny", reasons: ["seraph_invalid_response"], allowed: false, blocked: true };
    }
    const allowed = computeAllowed(data.decision, isCommit);
    return { decision: data.decision, reasons: data.reasons, allowed, blocked: !allowed };
  }

  async recordOutcome(params: OutcomeParams): Promise<OutcomeRecordStatus> {
    let response: Response;
    try {
      response = await fetch(`${this.base}/outcome`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: params.sessionId,
          ...(params.proposalId ? { proposal_id: params.proposalId } : {}),
          ...(params.eventId ? { event_id: params.eventId } : {}),
          ...(params.toolName ? { tool_name: params.toolName } : {}),
          success:    params.success,
          latency:    params.latencySeconds,
        }),
      });
    } catch {
      return "unreachable";
    }
    if (!response.ok) return "rejected";
    let result: { recorded?: boolean; duplicate?: boolean };
    try {
      result = await response.json() as {
        recorded?: boolean;
        duplicate?: boolean;
      };
    } catch {
      return "rejected";
    }
    if (result.duplicate === true) return "duplicate";
    return result.recorded === true ? "recorded" : "rejected";
  }

  async isReachable(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.base}/health`, { signal: AbortSignal.timeout(2000) });
      return resp.ok;
    } catch {
      return false;
    }
  }
}
