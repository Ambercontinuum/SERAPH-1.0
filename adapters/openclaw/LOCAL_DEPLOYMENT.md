# OpenClaw + Ollama local research setup

The plugin is tested against OpenClaw `2026.7.1-2`, Node 24, and the SERAPH
sidecar. Configure Ollama and select a local tool-capable model through your
OpenClaw installation before adding this plugin. Model reliability varies;
SERAPH enforces host tool proposals, not the model's prose.

Choose one sidecar: the foreground Python server below, the
[Docker example](../../docs/getting-started.md#run-the-sidecar-with-docker), or
[local Kubernetes](../../deploy/kubernetes/README.md). The Docker/Kubernetes
guides expose `http://127.0.0.1:8765`; use that value for the plugin's
`serverUrl` instead of the Python example's port 8000. If the sidecar is already
running, skip starting a second one. Building and configuring the plugin is
still required. None of these server paths automatically attaches an agent.

From the SERAPH checkout, create a Python environment, activate it, then run:

```console
python -m pip install -e ".[serve]"
seraph-serve --host 127.0.0.1 --port 8000
```

Leave that terminal open. In a second terminal, build the plugin:

```console
cd adapters/openclaw
npm ci
npm run build
npm run validate:ledger
npm run validate:failures
```

Add the following fragment to your existing OpenClaw configuration, merging
with existing plugin entries. Replace `/absolute/path/to/seraph-open` with the
actual checkout path (Windows JSON paths can use forward slashes):

```json
{
  "plugins": {
    "load": { "paths": ["/absolute/path/to/seraph-open/adapters/openclaw"] },
    "entries": {
      "seraph-governance": {
        "enabled": true,
        "config": { "serverUrl": "http://127.0.0.1:8000", "warnOnly": false }
      }
    }
  }
}
```

Restart your OpenClaw host after configuration changes. Keep gateway
credentials private and the gateway and sidecar bound to loopback. Use a
disposable workspace with only a test text file. Ask the agent to read it,
then separately ask it to run `echo SERAPH_PROBE` with its exec tool.

Under the current coarse tool profiles, read is admitted and exec is blocked
by environment policy, including harmless echo. This is not shell-command
classification or OS isolation. Mixed read/write histories may also be held
by FLUX fragmentation or oscillation policy. Do not disable those gates just
to obtain a successful demo; report the actual disposition.

Verify host tool results, not just a textual refusal. The pinned host's denied
result names `plugin-before-tool-call`; `/audit/session/{session_id}` separates
proposals from host-reported executions. A denied exec should have no admitted
execution record. Missing audit evidence alone does not prove nonexecution.
Stopping the sidecar should cause enforcing-mode calls to block. Warn-only
mode deliberately allows them and must not be described as enforcement.

Run the deterministic real-sidecar integration in PowerShell:

```powershell
$env:SERAPH_TEST_URL = 'http://127.0.0.1:8000'
npm run validate:adapter
```

Stop the foreground sidecar with Ctrl+C. State is in memory and is lost on
restart. See [security boundaries](../../SECURITY.md) and
[validation evidence](../../docs/publication.md). The original machine-specific
helper, runtime downloads, configuration, credentials, and logs are not included.

The [development process report](../../docs/development-process.md) describes
the human direction, AI contributions, critique, and corrections behind this
integration without exposing conversations or private operational state.
