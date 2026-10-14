# Local Kubernetes sidecar

This example was exercised on Docker Desktop 4.95.0 with its **kind** provisioner,
one Kubernetes 1.36.1 node, and the containerd image store. It runs one Seraph
sidecar and an internal service. It is a local research deployment, not a
production or cloud installation template.

Prerequisites: Docker Desktop running, its Kubernetes cluster created, the
`docker-desktop` context available, and `kubectl` on PATH. In a new terminal,
from the repository root:

```console
docker build -t seraph-local:0.1.0 .
kubectl --context docker-desktop get nodes
kubectl --context docker-desktop apply -f deploy/kubernetes/local.yaml
kubectl --context docker-desktop -n seraph rollout status deployment/seraph --timeout=90s
kubectl --context docker-desktop -n seraph port-forward service/seraph 8765:8000 --address 127.0.0.1
```

Leave the port-forward terminal running. Open <http://127.0.0.1:8765/docs> or
<http://127.0.0.1:8765/health>. The internal service address is
`seraph.seraph.svc.cluster.local:8000` for applications inside this cluster.
OpenClaw running on your Windows host should use the loopback URL instead.
Do not start another forward if that host port is already in use.

The tested Desktop kind setup resolved this locally built image through its
image integration using `IfNotPresent`. Other Kubernetes setups need an image
import or registry workflow; the local tag is not a publicly published image.
If a pod reports `ImagePullBackOff`, inspect its events rather than assuming the
application started:

```console
kubectl --context docker-desktop -n seraph get pods
kubectl --context docker-desktop -n seraph describe pods -l app=seraph
```

## Verify the deployment

In a second terminal:

```console
kubectl --context docker-desktop -n seraph get pods
kubectl --context docker-desktop -n seraph logs deployment/seraph
kubectl --context docker-desktop -n seraph exec deployment/seraph -- python -m validation.runtime_governance
```

Expect one Ready pod and 17/17 validation cases. To exercise the real plugin
hooks against this endpoint, build the OpenClaw adapter, then in PowerShell:

```powershell
cd adapters/openclaw
$env:SERAPH_TEST_URL = 'http://127.0.0.1:8765'
npm run validate:adapter
```

Seven cases should pass. These checks use synthetic host events, not a new
local-model trial. [Agent configuration](../../adapters/openclaw/LOCAL_DEPLOYMENT.md)
is separate from sidecar startup.

## Operating limits

The manifest uses a non-root container, read-only root filesystem, writable
temporary volume, dropped capabilities, health probes, and CPU/memory limits.
It mounts no Kubernetes service-account token. These settings do not prove
confinement of an external agent or completeness of its evidence.

Keep **one replica**: session and audit state live in one process and disappear
when its pod is replaced. `Recreate` avoids overlapping replicas during an
update; it does not add persistence. Horizontal scaling is not established.

The service is ClusterIP only, without an ingress or NodePort. It is reachable
inside the cluster and is not authenticated. The localhost port-forward is a
separate process; restart it after a host restart or if its selected pod is
replaced. Kubernetes keeps the deployment running independently of that forward.

To remove this example's resources, after checking you intend to remove this
local deployment:

```console
kubectl --context docker-desktop delete -f deploy/kubernetes/local.yaml
```

The manifest includes the `seraph` namespace, so deletion removes everything
placed in that namespace. Use this namespace only for this example.
