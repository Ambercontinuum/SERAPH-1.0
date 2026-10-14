/** Actual HTTP failure responses exercise the plugin's enforcing boundary. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { randomUUID } from 'node:crypto';
import plugin from '../dist/index.js';

let reply = { status: 200, body: '{}' };
const server = createServer((req, res) => {
  if (req.url === '/health') { res.end('{}'); return; }
  res.writeHead(reply.status, { 'content-type': 'application/json' });
  res.end(reply.body);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const serverUrl = `http://127.0.0.1:${server.address().port}`;
function host(warnOnly = false) {
  const hooks = new Map();
  plugin.register({ config: {}, pluginConfig: { serverUrl, warnOnly },
    on(name, callback) { hooks.set(name, callback); } });
  return () => hooks.get('before_tool_call')(
    { toolName: 'read', toolCallId: randomUUID() },
    { sessionId: randomUUID(), runId: randomUUID() });
}
const enforcing = host();
const cases = [];
try {
  for (const [name, status, body] of [
    ['http_500', 500, '{}'],
    ['malformed_json', 200, '{'],
    ['missing_fields', 200, '{}'],
    ['unknown_decision', 200, '{"decision":"invented","reasons":[]}'],
    ['invalid_reasons', 200, '{"decision":"allow","reasons":null}'],
  ]) {
    reply = { status, body };
    assert.equal((await enforcing()).block, true, name);
    cases.push(name);
  }
  reply = { status: 200, body: '{"decision":"allow","reasons":[]}' };
  assert.notEqual((await enforcing()).block, true);
  cases.push('valid_allow_control');
  reply = { status: 503, body: '{}' };
  assert.notEqual((await host(true)()).block, true);
  cases.push('warn_only_explicitly_permits_http_error');
  await new Promise(resolve => server.close(resolve));
  assert.equal((await enforcing()).block, true);
  cases.push('connection_refused');
  console.log(JSON.stringify({ passed: cases.length, cases,
    claimBoundary: 'Synthetic host hooks and local HTTP fault injection; no OS confinement claim.' }, null, 2));
} finally {
  if (server.listening) await new Promise(resolve => server.close(resolve));
}
