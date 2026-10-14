/**
 * SERAPH governance plugin for OpenClaw.
 *
 * Intercepts every tool call before execution. The SERAPH kernel evaluates
 * constraint closure, trajectory, PRP trail, and environment invariants. Tools that
 * In enforcing mode, tools that fail invariant checks are blocked before
 * execution. In warn-only audit mode, would-block calls are logged and allowed
 * through for observation.
 *
 * Requires the SERAPH governance server running as a local sidecar:
 *   python -m seraph._serve --port 8000
 *
 * Configuration (openclaw.json):
 *   plugins.entries["seraph-governance"].config = {
 *     serverUrl: "http://127.0.0.1:8000", warnOnly: false
 *   }
 */

import {
  definePluginEntry,
  type OpenClawPluginDefinition,
} from "openclaw/plugin-sdk/plugin-entry";
import { SeraphClient } from "./seraph-client.js";
import { getProfile, ToolProfile } from "./tool-profiles.js";
import {
  HostReportedExecution,
  MotionContext,
  MotionLedger,
} from "./motion-ledger.js";

interface SeraphConfig {
  serverUrl?: string;
  warnOnly?: boolean;  // log blocks without enforcing — for migration/audit mode
}

const motionLedger = new MotionLedger();

function motionContext(
  event: { toolName: string; toolCallId?: string; runId?: string },
  context: { sessionId?: string; runId?: string },
): MotionContext {
  return {
    sessionId: context.sessionId ?? "default",
    runId: event.runId ?? context.runId,
    toolCallId: event.toolCallId,
    toolName: event.toolName,
  };
}

interface ObservedOutcome {
  success: boolean;
  latencySeconds: number;
}

function toolState(toolName: string, profile: ToolProfile): string {
  if (!profile.isCommit) return "observe";
  if (
    profile.containment <= 0.3 ||
    profile.blastRadiusControl <= 0.2 ||
    profile.externalityControl <= 0.3 ||
    profile.reversibility <= 0.2
  ) return "critical";
  if (profile.containment < 0.7 || profile.blastRadiusControl < 0.7) return "elevate";
  return "modify";
}

function operationalTrajectory(
  rawHistory: string[],
  toolName: string,
  profile: ToolProfile,
): string[] {
  const operationalHistory = rawHistory.map((name) => toolState(name, getProfile(name)));
  const operationalTrajectory = [...operationalHistory, toolState(toolName, profile)].slice(-8);
  const seededOperationalTrajectory = operationalTrajectory.length < 2
    ? ["observe", "observe", ...operationalTrajectory]
    : operationalTrajectory;

  return seededOperationalTrajectory;
}

const plugin: OpenClawPluginDefinition = definePluginEntry({
  id:          "seraph-governance",
  name:        "SERAPH Governance",
  description: "Gates every OpenClaw tool call through the SERAPH invariant kernel before execution.",

  register(api) {
    const config: SeraphConfig = (api.pluginConfig as SeraphConfig) ?? {};
    const client = new SeraphClient(
      config.serverUrl ?? "http://127.0.0.1:8000",
    );
    const warnOnly = config.warnOnly ?? false;
    const deferredOutcomes = new Map<string, ObservedOutcome>();

    async function recordExecution(
      execution: HostReportedExecution,
      outcome: ObservedOutcome,
    ): Promise<void> {
      const status = await client.recordOutcome({
        sessionId: execution.sessionId,
        proposalId: execution.proposalId,
        eventId: execution.eventId,
        toolName: execution.toolName,
        success: outcome.success,
        latencySeconds: outcome.latencySeconds,
      });
      if (status === "rejected" || status === "unreachable") {
        console.error(
          `[SERAPH] execution evidence ${status}: ` +
          `${execution.toolName} proposal=${execution.proposalId}`,
        );
      }
    }

    // Verify sidecar is reachable at startup
    client.isReachable().then((up) => {
      if (!up) {
        console.warn(
          "[SERAPH] Governance server not reachable at",
          config.serverUrl ?? "http://127.0.0.1:8000",
          "— start the sidecar and verify the configured serverUrl."
        );
      } else {
        console.log("[SERAPH] Governance server connected. All tool calls gated.");
      }
    });

    // ── before_tool_call: evaluate before execution ─────────────────
    api.on("before_tool_call", async (event, context) => {
      const motion = motionContext(event, context);
      const proposal = motionLedger.beginProposal(motion);
      const sessionId = motion.sessionId;
      const toolName = motion.toolName;
      const profile    = getProfile(toolName);
      const trajectory = operationalTrajectory(
        motionLedger.executedTrajectory(sessionId),
        toolName,
        profile,
      );

      let result: Awaited<ReturnType<SeraphClient["govern"]>>;
      try {
        result = await client.govern(sessionId, trajectory, {
          reversibility:        profile.reversibility,
          containment:          profile.containment,
          blast_radius_control: profile.blastRadiusControl,
          externality_control:  profile.externalityControl,
        }, profile.isCommit, {
          // Tool-name changes do not measure semantic pressure, coherence, or
          // recursion. Preserve absence rather than fabricate danger or safe 0.
          // Other channels use the sidecar's declared profile defaults.
          symbolic_pressure: null,
        }, {
          proposalId: proposal.proposalId,
          toolName,
        });
      } catch (err) {
        // Network error reaching SERAPH — fail-safe: block
        console.error(`[SERAPH] Server unreachable for '${toolName}': ${err}`);
        motionLedger.closeWithoutExecution(proposal.proposalId);
        deferredOutcomes.delete(proposal.proposalId);
        if (warnOnly) return {};
        return { block: true, blockReason: "seraph_server_unreachable" };
      }

      const deferredExecution = motionLedger.recordGovernance(
        proposal.proposalId,
        result.decision,
        result.blocked,
      );
      if (deferredExecution) {
        const deferredOutcome = deferredOutcomes.get(proposal.proposalId);
        deferredOutcomes.delete(proposal.proposalId);
        if (deferredOutcome) {
          await recordExecution(deferredExecution, deferredOutcome);
        } else {
          console.error(
            `[SERAPH] deferred execution lost outcome fields: ` +
            `proposal=${proposal.proposalId}`,
          );
        }
      }
      const reasonStr = result.reasons.join(", ");

      if (result.blocked) {
        console.warn(
          `[SERAPH] BLOCKED  ${toolName}  [${result.decision}]  {${reasonStr}}`
        );
        if (warnOnly) {
          // Audit mode: keep the proposal pending until the host reports execution.
          return {};
        }
        motionLedger.closeWithoutExecution(proposal.proposalId);
        return {
          block:       true,
          blockReason: `SERAPH ${result.decision}: ${reasonStr}`,
        };
      }

      console.log(`[SERAPH] ${result.decision.toUpperCase().padEnd(7)}  ${toolName}  {${reasonStr}}`);
      return {};
    }, { priority: 100 });  // high priority — run before all other before_tool_call hooks

    // ── after_tool_call: record outcome for PRP trail ───────────────
    api.on("after_tool_call", async (event, context) => {
      const motion = motionContext(event, context);
      const resolution = motionLedger.resolveExecution(motion);
      const outcome: ObservedOutcome = {
        success: event.error == null,
        latencySeconds: (event.durationMs ?? 1000) / 1000,
      };
      if (resolution.status === "deferred") {
        deferredOutcomes.set(resolution.proposalId, outcome);
        console.warn(
          `[SERAPH] execution arrived before governance resolved: ` +
          `${motion.toolName} proposal=${resolution.proposalId}`,
        );
        return;
      }
      if (resolution.status !== "resolved") {
        console.warn(
          `[SERAPH] execution telemetry ${resolution.status}: ` +
          `${motion.toolName} session=${motion.sessionId}`,
        );
        return;
      }

      await recordExecution(resolution.execution, outcome);
    });
  },
});

export default plugin;
