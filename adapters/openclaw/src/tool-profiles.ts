/**
 * Risk profiles for OpenClaw tools.
 *
 * Each profile maps to SERAPH EnvironmentVector fields.
 * Unknown tools fall through to inferProfile(), which classifies
 * by name — same logic as adapters/tool_guard.py:_infer_risk().
 */

export interface ToolProfile {
  isCommit: boolean;
  reversibility: number;
  containment: number;
  blastRadiusControl: number;
  externalityControl: number;
}

// Known OpenClaw tool profiles
const PROFILES: Record<string, ToolProfile> = {
  // Safe reads — no side effects
  read:              { isCommit: false, reversibility: 1.0, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },
  list_files:         { isCommit: false, reversibility: 1.0, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },
  read_file:          { isCommit: false, reversibility: 1.0, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },
  sessions_list:      { isCommit: false, reversibility: 1.0, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },
  sessions_history:   { isCommit: false, reversibility: 1.0, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },
  canvas:             { isCommit: false, reversibility: 1.0, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },

  // Writes — local, partially reversible
  write_file:         { isCommit: true, reversibility: 0.85, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 },
  delete_file:        { isCommit: true, reversibility: 0.0,  containment: 1.0, blastRadiusControl: 0.5, externalityControl: 1.0 },
  cron:               { isCommit: true, reversibility: 0.6,  containment: 0.8, blastRadiusControl: 0.8, externalityControl: 0.8 },

  // Browser — external, partially observable
  browser:            { isCommit: true, reversibility: 0.5,  containment: 0.6, blastRadiusControl: 0.7, externalityControl: 0.5 },

  // Messaging — irreversible, crosses system boundary
  sessions_send:      { isCommit: true, reversibility: 0.2,  containment: 0.7, blastRadiusControl: 0.8, externalityControl: 0.3 },

  // Shell / node execution — zero blast control, low containment
  nodes:              { isCommit: true, reversibility: 0.0,  containment: 0.3, blastRadiusControl: 0.0, externalityControl: 0.3 },
  execute_command:    { isCommit: true, reversibility: 0.0,  containment: 0.3, blastRadiusControl: 0.0, externalityControl: 0.3 },

  // Network / exfiltration — all fields zero → always blocked by environment invariant
  network_request:    { isCommit: true, reversibility: 0.0,  containment: 0.0, blastRadiusControl: 0.0, externalityControl: 0.0 },
};

// Fallback: classify by tool name using keyword heuristics
export function inferProfile(toolName: string): ToolProfile {
  const n = toolName.toLowerCase();

  if (/delete|remove|drop|destroy|kill|terminate|truncate/.test(n))
    return { isCommit: true,  reversibility: 0.0,  containment: 0.5, blastRadiusControl: 0.2, externalityControl: 0.9 };

  if (/exfil|export|extract|upload|transmit/.test(n))
    return { isCommit: true,  reversibility: 0.0,  containment: 0.2, blastRadiusControl: 0.2, externalityControl: 0.0 };

  if (/send|post|network|request|http|notify/.test(n))
    return { isCommit: true,  reversibility: 0.2,  containment: 0.4, blastRadiusControl: 0.4, externalityControl: 0.3 };

  if (/exec|run|spawn|launch|start/.test(n))
    return { isCommit: true,  reversibility: 0.0,  containment: 0.3, blastRadiusControl: 0.0, externalityControl: 0.3 };

  if (/write|save|create|insert|append|update|patch/.test(n))
    return { isCommit: true,  reversibility: 0.85, containment: 1.0, blastRadiusControl: 1.0, externalityControl: 1.0 };

  // Unknown — treat as low-reversibility commit; let SERAPH decide
  return { isCommit: true, reversibility: 0.3, containment: 0.5, blastRadiusControl: 0.3, externalityControl: 0.5 };
}

export function getProfile(toolName: string): ToolProfile {
  return PROFILES[toolName] ?? inferProfile(toolName);
}
