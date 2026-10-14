# Getting started

SERAPH is a governance component you connect to an application or agent host.
It is not a model or a chat application. Begin with the examples, then connect
one adapter and inspect the decisions it produces.

## Run the examples

With Git and Python 3.11 or newer installed:

```console
git clone https://github.com/Ambercontinuum/seraph-open.git
cd seraph-open
python -m venv .venv
```

Activate the environment in PowerShell with `.\.venv\Scripts\Activate.ps1`,
or on Linux/macOS with `source .venv/bin/activate`. Then:

```console
python -m pip install -e ".[serve,test]"
python -m seraph --pretty
python -m seraph_demo --quiet
python -m validation.runtime_governance
```

The demo checks eight expected-outcome scenarios. The validation command checks
17 declared cases, including one safe admission and adversarial omission,
execution-binding, and consequence cases. These are bounded examples, not an
assessment of your deployment. See [validation](validation.md).

## Try the HTTP API

Start a foreground server:

```console
seraph-serve --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765/docs> for the interactive API explorer, or
<http://127.0.0.1:8765/health> for health. This explorer is an API interface;
it is not an agent conversation. Leave the server terminal open.

In the API explorer, expand `POST /govern`, choose **Try it out**, and submit:

```json
{
  "session_id": "first-check",
  "trajectory": ["observe", "observe"],
  "distillation": { "symbolic_pressure": null },
  "request_commit": false
}
```

This observation example should return `allow`. For an unsafe environment
example, use a different session:

```json
{
  "session_id": "environment-check",
  "trajectory": ["observe", "observe", "critical"],
  "environment": {
    "reversibility": 0,
    "containment": 0,
    "blast_radius_control": 0,
    "externality_control": 0
  },
  "distillation": { "symbolic_pressure": null },
  "request_commit": true
}
```

The second example should return `deny` with an environment failure reason.
These requests use declared HTTP defaults for other channels. They do not
attest that real-world constraints or sensors are correct, and no actual tool
is executed by either request. Applications must supply and protect the
topology, evidence, and execution integration they depend on.

## Run the sidecar with Docker

As an alternative to the foreground Python server, from the checkout root:

```console
docker build -t seraph-local:0.1.0 .
docker run --rm -p 127.0.0.1:8765:8000 seraph-local:0.1.0
```

Use the same browser links above. Choose one server path at a time; two
processes cannot bind the same port. Ctrl+C stops the foreground server/container.
For local orchestration, follow the [Kubernetes guide](../deploy/kubernetes/README.md).

## Connect an agent

For OpenClaw with Ollama, follow the
[local agent guide](../adapters/openclaw/LOCAL_DEPLOYMENT.md). Set the plugin's
`serverUrl` to the endpoint you started and use enforcing mode
(`warnOnly: false`). Keep agent execution in a disposable workspace.

The reference policy admits reads and blocks shell execution, even harmless
echo. Two reads followed by a declared reversible write pass the tested
integration case; one read followed by a write is held for fragmentation.
Model replies alone are not enforcement evidence. Inspect the host tool result
and `/audit/session/{session_id}` separately.

## What to build next

Useful first contributions are a reproducible adapter defect, an independently
tested host integration, a small workload with explicit expected dispositions,
or a comparator using equivalent evidence and execution opportunities. A real
outside installation is more informative than a broad safety or novelty claim.

Read the [development process](development-process.md) to understand the design
and correction history, and [contribution guide](../CONTRIBUTING.md) to propose
a change. The [security boundary](../SECURITY.md) describes what a deployment
must provide beyond this prototype.
