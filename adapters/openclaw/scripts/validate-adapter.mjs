/** Synthetic host hooks against a real SERAPH HTTP sidecar; no model required. */
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import plugin from '../dist/index.js';
import { SeraphClient } from '../dist/seraph-client.js';

const serverUrl = process.env.SERAPH_TEST_URL;
if (!serverUrl) throw new Error('Set SERAPH_TEST_URL to a running test sidecar.');
const sessions = [];
const requests = [];
const results = [];
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  if (String(input) === `${serverUrl}/govern`) requests.push(JSON.parse(init.body));
  return nativeFetch(input, init);
};
const hooks = new Map();
plugin.register({
  config: {},
  pluginConfig: { serverUrl, warnOnly: false },
  on(name, handler) { hooks.set(name, handler); },
});

function context() {
  const sessionId = `adapter-regression-${randomUUID()}`;
  sessions.push(sessionId);
  return { sessionId, runId: randomUUID() };
}
async function propose(ctx, toolName) {
  const event = { toolName, toolCallId: randomUUID(), runId: ctx.runId };
  const result = await hooks.get('before_tool_call')(event, ctx);
  return { event, result, request: requests.at(-1) };
}
async function execute(ctx, event) {
  // Declared host reports test correlation, not physical side effects.
  await hooks.get('after_tool_call')({ ...event, durationMs: 10 }, ctx);
}
async function audit(ctx) {
  const response = await nativeFetch(`${serverUrl}/audit/session/${ctx.sessionId}`);
  assert.equal(response.status, 200);
  return response.json();
}
const safeEnvironment = {
  reversibility: 1, containment: 1, blast_radius_control: 1, externality_control: 1,
};

try {
  const ctx = context();
  const read = await propose(ctx, 'read');
  assert.equal(read.result?.block, undefined);
  assert.equal(read.request.distillation.symbolic_pressure, null);
  await execute(ctx, read.event);
  const exec = await propose(ctx, 'exec');
  assert.equal(exec.request.distillation.symbolic_pressure, null);
  assert.deepEqual(Object.keys(exec.request.distillation), ['symbolic_pressure']);
  assert.equal(exec.result.block, true);
  assert.match(exec.result.blockReason, /environment_invariant_failed/);
  assert.doesNotMatch(exec.result.blockReason, /symbolic_pressure|distillation/);
  // OpenClaw also emits an after hook for a plugin-blocked result.
  await execute(ctx, exec.event);
  const recorded = await audit(ctx);
  assert.deepEqual(recorded.proposals.map(p => [p.tool_name, p.decision]),
    [['read', 'allow'], ['exec', 'deny']]);
  assert.equal(recorded.host_reported_executions.length, 1);
  assert.equal(recorded.host_reported_executions[0].tool_name, 'read');
  results.push('read_then_exec_uses_environment_gate_without_invented_pressure');

  const varied = context();
  for (const name of ['read', 'list_files', 'read_file', 'sessions_list',
    'sessions_history', 'canvas', 'read', 'read_file', 'list_files']) {
    const call = await propose(varied, name);
    assert.equal(call.request.distillation.symbolic_pressure, null);
    assert.equal(call.result?.block, undefined);
    await execute(varied, call.event);
  }
  assert.equal((await audit(varied)).host_reported_executions.length, 9);
  results.push('varied_observation_history_does_not_become_semantic_evidence');

  const short = context();
  const first = await propose(short, 'read');
  await execute(short, first.event);
  const shortWrite = await propose(short, 'write_file');
  assert.equal(shortWrite.result.block, true);
  assert.match(shortWrite.result.blockReason, /fragmentation/);
  assert.doesNotMatch(shortWrite.result.blockReason, /symbolic_pressure/);
  results.push('short_read_write_history_retains_flux_fragmentation_policy');

  const stable = context();
  for (const name of ['read', 'read', 'write_file']) {
    const call = await propose(stable, name);
    assert.notEqual(call.result?.block, true);
    await execute(stable, call.event);
  }
  assert.equal((await audit(stable)).host_reported_executions.length, 3);
  results.push('stable_read_read_write_control_is_admitted');

  const client = new SeraphClient(serverUrl);
  const required = context();
  const missing = await client.govern(required.sessionId, ['observe', 'observe'],
    safeEnvironment, true, { symbolic_pressure: null, symbolic_pressure_required: true });
  assert.equal(missing.blocked, true);
  assert.ok(missing.reasons.includes('distillation_evidence_unresolved'));
  assert.ok(missing.reasons.includes('symbolic_pressure_unresolved'));
  results.push('required_missing_pressure_remains_unresolved_and_blocks_commit');

  const observed = context();
  const pressure = await client.govern(observed.sessionId, ['observe', 'observe'],
    safeEnvironment, true, { symbolic_pressure: 1 });
  assert.equal(pressure.blocked, true);
  assert.ok(pressure.reasons.includes('symbolic_pressure'));
  assert.equal(requests.at(-1).distillation.symbolic_pressure, 1);
  results.push('explicit_pressure_observation_still_reaches_the_kernel_gate');

  const zero = context();
  const clear = await client.govern(zero.sessionId, ['observe', 'observe'],
    safeEnvironment, false, { symbolic_pressure: 0 });
  assert.equal(clear.allowed, true);
  assert.equal(requests.at(-1).distillation.symbolic_pressure, 0);
  results.push('measured_zero_remains_distinct_from_missing');
  console.log(JSON.stringify({ passed: results.length, cases: results,
    claimBoundary: 'Synthetic host hooks and real HTTP/kernel decisions; not OS confinement or a model trial.' }, null, 2));
} finally {
  globalThis.fetch = nativeFetch;
  await Promise.all(sessions.map(session => nativeFetch(`${serverUrl}/session/${session}`, { method: 'DELETE' })));
}
