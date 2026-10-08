# Hermes dealer hosting groundwork

Draft, October 6, 2026, for
[BIG-302](https://linear.app/bighorn-byte/issue/BIG-302/evaluate-premium-dealer-assistant-and-plan-portal-integration).
Heavy Ops will host the dealer assistant gateway, Hermes runtime and persistent
browser. M&K Sales and J&M Trailer are the likely pilots; non-dealer sites are
outside this rollout. This branch adds planning only. Independent inactive MCP
foundation work in the kit and isolated local M&K/J&M read integration are
authorized. Publication and host deployment follow accounting's accepted
publication, then qualification of an isolated environment before any pilot
activation.

The shared
[architecture](../../../deno-kit/docs/planning/hermes-dealer-assistant.md)
defines application actions, identity, previews and delivery. This repository
owns deployment configuration and operational policy. Runtime application source
belongs in a proposed dedicated `dealer-agent` repository, not in GitOps files.

## Match the existing app structure

Owner requirement, October 6, also recorded in BIG-302: Hermes and its
supporting workloads must use heavy-ops' existing application layout and
conventions. Follow `kubernetes/apps/<namespace>/<app>/ks.yaml` with an `app/`
resource directory. Use named component directories for separate
runtime/browser/gateway releases where needed, matching the existing
[Bighorn application](../../kubernetes/apps/business/bighorn-byte/ks.yaml). Keep
the same namespace parent kustomization, Flux wiring, names/labels, schema
headers and YAML style as neighboring applications.

Default to the repository's `app-template` OCI chart and `chartRef` pattern;
[scale-tv](../../kubernetes/apps/business/scale-tv/app/helmrelease.yaml) is a
concrete reference. If Hermes or a dependency has a suitable maintained upstream
Helm chart, evaluate and document that choice while retaining the surrounding
directory and Flux structure. Chart availability has not been established. Do
not introduce a bespoke chart or separate deployment tree without a concrete
need.

Match the existing controllers/containers, pinned images, probes, resource
limits, pod security, persistence/backup, reloader, routes/DNS, network policy
and monitoring patterns where applicable. Preserve the configuration and
credential rules below. Review rendered resources against adjacent applications
and explain necessary exceptions; similar-looking YAML alone is not sufficient
evidence of correct behavior. Local preview manifests stay outside the active
Flux resource graph until promotion.

## Reuse infrastructure patterns without sharing customer authority

The existing
[agent-runner release](../../kubernetes/apps/business/agent-runner/app/helmrelease.yaml)
is an owner coding tool. Keep its controller, GitHub access, personal provider
credentials, job storage and browser separate from dealer workloads. Its source
is useful for durable jobs, pinned images and constrained worker patterns, but
its documented trust model does not qualify it for customer isolation.

The
[outreach browser](../../kubernetes/apps/business/bighorn-byte/browser/helmrelease.yaml)
and
[network policy](../../kubernetes/apps/business/bighorn-byte/browser/networkpolicy.yaml)
serve Bighorn's own workflow. They are not a shared dealer browser pool. Do not
inherit that workload's account state, proxy route or access list as customer
defaults.

The repository describes home infrastructure with local persistent storage. Do
not claim a highly available customer assistant from multiple replicas on the
same failure domain. Inventory and accounting must remain available in Business
Ops during a home/Internet/assistant outage. Persist requests on the caller side
and show queued/unavailable state. Measure uptime and recovery before making
customer availability commitments.

The owner confirms a powerful home server and symmetric 5 Gbps fiber. This
supports the plan to keep Hermes, browser sessions and a self-hosted memory
service on Heavy Ops. Measure end-to-end mobile/browser interaction and model
response times during the pilot; link throughput alone does not measure them.
Home-host maintenance pauses execution, while durable requests and reconnect
notices remain visible through the dealer application. Continuous execution
during a host reboot would require another independent execution host.

## Proposed deployment units

| Unit                   | Identity and storage                                                                                            | Exposure                                                                     |
| ---------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Assistant gateway      | Dedicated service identity; durable Postgres run/event/grant/usage store; no dealer DB superuser                | Authenticated HTTPS for registered dealer backends and scoped viewer routes  |
| Provisioner            | Narrow controller rights to approved worker resources/namespaces, quotas and secret references                  | Internal only; model processes cannot invoke arbitrary Kubernetes operations |
| Hermes worker          | Immutable image; runtime home scoped to business and effective staff/automation access; bounded scratch storage | Internal gateway interface and authorized downstream tool/model access       |
| Browser worker         | Persistent account-specific profile and exclusive lease; no shared mounts with unrelated workers                | Internal CDP/display only; viewer goes through an authorized gateway         |
| Provider access broker | Metered request identity and budget enforcement; provider credentials inaccessible to worker shell              | Allowed provider calls only; no general credentialed proxy                   |
| Artifact storage       | Private objects with business/conversation/proposal ownership and retention                                     | Authorized application retrieval; no public worker filesystem                |

Use one durable gateway/job store with transactional admission and an event
outbox initially; a separate queue technology is unnecessary until measured load
requires it. The exact database deployment and backup arrangement must be
selected during implementation. This plan does not provision a new database or
assume an existing one has spare capacity.

M&K and J&M receive separate business execution/data contexts. Private staff
conversations require further partitioning where access differs. One runtime
home for every employee would make automatically ingested memory a privacy
problem. Share only explicit business facts through an authorized interface.

## Isolation to qualify

Hermes profiles and Bot Screen control leases are state organization, not
customer security boundaries; see the
[upstream research](../../../deno-kit/docs/planning/hermes-primary-research.md).
Select a dedicated VM or reviewed sandbox runtime per execution/access domain.
Ordinary Kubernetes namespaces and network policies alone do not establish safe
isolation for a terminal-capable agent processing external content. Qualify the
actual choice against browser, subprocess, filesystem and network access tests.

Workers require non-root execution, dropped capabilities, read-only images,
bounded writable mounts, resource/ephemeral-storage limits and no host paths,
Docker socket, host network or automounted cluster token. CDP, displays, cookies
and login state remain inside the selected execution context. No unrelated
tenant or shared worker can reach their loopback/socket endpoints.

Use default-deny ingress/egress with explicit gateway, DNS, tool/provider broker
and approved account-web access. Deny cluster/control-plane, host/LAN and cloud
metadata destinations, including redirects, alternate address forms and DNS
rebinding. An outbound public-web allowance alone must not expose private
services. Downloads/uploads and browser navigation pass the same policy.

Raw model-provider credentials, unrestricted terminal networking or unmanaged
Hermes cron would bypass plan limits. Restrict those paths through a metered
broker/admission system. If a chosen Hermes/browser mode requires broader
terminal access, prove its controls before activating it; a configuration label
is not enforcement.

## Connectivity and browser control

Use registered HTTPS origins and resource audiences for dealer installations. No
pod-CIDR routing between Business Ops and Heavy Ops is needed for the initial
design. Dealer backends submit work; the gateway/Hermes invokes the specifically
registered dealer MCP endpoint with an appropriate delegation. Ordinary customer
cookies and accounting broker credentials are not cross-cluster authentication.

Never expose raw Hermes operator APIs, VNC or CDP publicly. Browser-viewer
admission binds the signed-in person, business, account, run and control role.
Use short-lived single-use tickets, redact them from access logs, expire active
control on revocation, and enforce origin checks. A durable lease with a fencing
token serializes agent/human input and rejects a stale worker after takeover.

External publication needs both account authorization and an enforceable effect
policy. If raw browser control can bypass a required confirmation, provide an
attended final action for that adapter until constrained execution is proven.
Retain task preparation, live view and human handoff rather than claiming a
permission guarantee that exists only in a prompt.

## Configuration and recovery

Reuse established 1Password items after checking consumers. Shared
model/provider credentials belong in provider-named items; runtime-specific keys
and closely paired metadata belong in the runtime application's item. Production
uses the base name, development uses `-development`, and both use identical
ordinary environment-variable names. Dynamic dealer browser credentials/state
belong in the runtime's encrypted, scoped store, not a single shared provider
item.

Public settings belong in HelmRelease `env`; common public values use
`kubernetes/components/common/vars`. Image digest, gateway/issuer/resource URLs,
feature flags and numeric limits are public configuration. Secret material is
projected through the established secret-management pattern. Do not create or
rename items as part of this documentation work.

Back up the gateway database, profiles, explicit memory and private artifacts
with documented retention and encryption/key recovery. A restore must start with
schedules and external effects disabled, invalidate prior leases, reauthorize
accounts as needed and reconcile outstanding provider/listing effects before
dispatch. Recovery must not cause another invoice or Marketplace listing.

Measure warm/idle worker CPU/RAM, browser sessions, storage growth, startup
time, queue age, home-link bandwidth and concurrency. Enforce resource quotas
and backpressure so the customer assistant cannot starve existing business
workloads. Alerts cover failed admission, budget anomalies, lost heartbeats,
unknown effects, expired backups and reconnect failures, with redacted logs.

## Later activation evidence

Before registering any new Flux resource, require the accepted accounting
release, an exact Hermes/browser/MCP image and source pin, passing
cross-business/private staff isolation, budget bypass and browser lease tests, a
restore rehearsal and an agreed bounded pilot. Any sandbox/preview gets isolated
data, identities, origins and provider accounts with the same configuration
contract.

No active `ks.yaml`, HelmRelease, namespace, DNS, secret, service account or
workflow is registered by this branch. The active
[business kustomization](../../kubernetes/apps/business/kustomization.yaml) and
[Flux root](../../kubernetes/flux/cluster/ks.yaml) remain the authority for what
runs; planning files are outside their resource graph.

## October 8 runtime implementation and inactive staging

The clean planning worktree was switched to `feat/big-302-hermes-runtime` from
`origin/main` `c8c1be7f866194708341dd4d66d1013ecb6c29ca`; the main checkout and
original planning branch were preserved. Runtime source remains in
[dealer-agent](../../../dealer-agent/README.md#kubernetes-installation-preparation).
The same executable now selects local Docker or a native Kubernetes backend. The
latter uses a dedicated namespace per installation, private person/book PVCs,
immutable per-attempt state, no worker service-account token and a
controller-only API-server transport. Pod UIDs survive controller restart in an
attempt Secret metadata binding. The native app remains the durable ownership,
permission and usage authority; Heavy Ops introduces no second dealer database.

The [public renderer](hermes-runtime/render.py) prepares M&K/J&M development
settings and a copy of the normal namespace/app layout under
`hermes-runtime/staged/kubernetes/apps/`. These files have `suspend: true` and
zero controller replicas. Image tag publication, issuer registration, registry
access, TLS/DNS and actual cluster acceptance remain outstanding. The examples
use reserved `.example` origins and disabled app/budgets. They neither discover
existing credentials nor create vault items.

Each public input explicitly names its installation. The generated app and
runtime environments carry the same `ASSISTANT_INSTALLATION_ID`, and the planner
refuses a different cluster installation name. Both sides start with
`ASSISTANT_ENABLED=0` and `ASSISTANT_BROWSER_ENABLED=0`; restore and
installation preparation must not admit new turns or browser effects implicitly.

Keep staging outside `kubernetes/apps`: the existing Flux root points there
without a top-level Kustomize file, so Flux can discover new namespace trees
automatically. Promotion must be an explicit reviewed move after acceptance.
Never treat a new directory beneath that active path as an inactive preview.

Regenerate without cluster, vault, database or provider access:

```bash
python3 .github/planning/hermes-runtime/render.py \
  --runtime ../dealer-agent \
  --output /tmp/dealer-runtime-staged-20261008
kubectl kustomize /tmp/dealer-runtime-staged-20261008/kubernetes/apps/dealer-mk-development/dealer-agent/app
```

Both installations rendered locally with the existing app-template 5.2.1 archive
and Kubernetes 1.35 capabilities. Their values/outputs are retained at
`/tmp/dealer-runtime-staged-20261008/` and
`/tmp/dealer-{mk,jm}-development-rendered.yaml`. Controller Service selectors,
projected API credentials, private worker port, namespace-scoped Role, non-root
security, suspended activation and distinct origins were checked. These are
configuration artifacts, not deployed installation or isolation evidence.

The existing `onepassword` ClusterSecretStore allows only the `talos` vault. The
examples therefore reference a separately approved Bighorn Byte-capable store
named `dealer-agent-onepassword`. Establish its authorization before activation;
do not copy dealer bundles into talos or rename established items.
Runtime-specific fields stay in `mk-sales`/`jm-trailer` or their development
items; shared OpenAI credentials stay in the selected existing provider item.
The environment/build contract remains identical.

Controller readiness verifies the restricted namespace, immutable relay source,
Service identity, resource quota, exact worker Cilium policy, absence of
additional permissive namespace policies and expected controller Role/Binding.
Workers have no DNS egress: their relay uses the resolved controller Service IP.
The controller has only app/provider DNS destinations plus authenticated API
access. Namespace policy is configuration, not proof of a process/renderer
sandbox, cluster-wide policy interactions or physical node fencing.

Kubernetes authentication removes the bearer before serving a successfully
authenticated request; the private control key uses a separate header, and the
relay rejects unexpected forwarded `Authorization`. Verify the actual pinned
API-server path before activation.
[Official authentication filter](https://github.com/kubernetes/apiserver/blob/master/pkg/endpoints/filters/authentication.go).
ReadWriteOncePod requires CSI support; OpenEBS mount behavior and actual writer
fencing still need qualification. Use graceful UID-precondition deletion;
force-deleting an API object is insufficient evidence of a stopped process.
[Persistent-volume access modes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes),
[Kubernetes force-deletion behavior](https://kubernetes.io/docs/tasks/run-application/force-delete-stateful-set-pod/).

Local synthetic evidence now covers two isolated API installations plus the
actual pinned-image read-only history reader. The offline encrypted restore
proof recovered 300 rows per installation through SQLite's consistent backup and
AES-GCM, with foreign-session, wrong-UID and wrong-key refusals. It used
task-owned fixtures, not an app database, production keys or customer data.
CSI/WAL, Pod proxy streams, Cilium paths, quotas, host restart, Kopiur mover
security/retention, encryption-key recovery and real restore remain acceptance
work. Keep each home quiescent before snapshots, or first take a verified
SQLite-consistent copy; do not assume the common copy policy quiesces a worker.
Per-home enrollment must use the existing Kopiur pattern with UID/GID 10000 and
profile-specific PVC names; no backup schedule is activated by staging.

Restore while dispatch is disabled and no old writer remains. Reconcile/revoke
app attempts and external outcomes, recover the stable home and approved keys,
then select a fresh runtime generation. New derived capabilities differ from old
ones; changing the generation alone does not revoke a bearer already bound in
the app. A lease is released only after actual worker removal and retained
history recovery.

The application and runtime now implement a separate browser account lease,
private native viewer and attended listing journal for an owned local fixture.
This local driver requires Chromium's sandbox and refuses the Kubernetes
controller backend. The staged installations keep it disabled. A deployed
browser needs its own Pod or VM, restricted control transport, network policy,
profile storage and restore qualification before external accounts can be
enabled. Local fixture evidence does not establish Turnstile compatibility.
