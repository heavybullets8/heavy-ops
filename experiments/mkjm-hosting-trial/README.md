# M&K / J&M home hosting trial

This directory is deliberately outside `kubernetes/` and its Flux roots. It creates one disposable namespace containing two copies of the same prebuilt app image and a standalone PostgreSQL 17 database. No public route, DNS record, cloud resource, or production database is involved.

## Home build handoff

The source-staging helper computes a deterministic tree hash and leaves the source and a byte-identical `/work/build-request.json` on the dedicated `mkjm-hosting-build/builder` pod. The committed request has exactly these fields:

```json
{
  "schemaVersion": 1,
  "sourceBaseCommit": "b5337989ca4615ad57f14471435b9bd44af0102d",
  "sourceTreeSha256": "<64 lowercase hex characters>",
  "imageTag": "ghcr.io/heavybullets8/mkjm-hosting-trial-private:trial-b5337989ca46-<first 12 source hash characters>",
  "platform": "linux/amd64"
}
```

Publishing runs through the [private publisher repository](https://github.com/heavybullets8/mkjm-hosting-publisher) using its [image workflow](https://github.com/heavybullets8/mkjm-hosting-publisher/blob/main/.github/workflows/image.yaml) and a temporary home runner with a namespace-scoped service account defined in its [publisher.yaml](https://github.com/heavybullets8/mkjm-hosting-publisher/blob/main/experiments/mkjm-hosting-trial/publisher.yaml). The legacy workflow in this public repository is gated on `repository.private` and cannot publish from here. Before publishing any application layers to GHCR, the publisher must push a metadata-only scratch image to the intended package and verify through package metadata that its visibility is **private**. Stop if the package is public or visibility cannot be verified. A previous trial package unexpectedly inherited public visibility and was deleted; a package name ending in `-private` is not itself proof of privacy. Compare the staged `/work/build-request.json` with the request used by the publisher, then retain the immutable image digest from `/work/build-result.json` in the trial manifest. Remove the temporary publisher credentials and runner when publishing ends.

The image must have its default entrypoint set to the trial launcher. Kubernetes passes `mk` or `jm` as its sole argument. Each pod receives `HOSTING_TRIAL=1`, the matching `SITE_SCOPE`, `PORT=8000`, and a generated `DATABASE_URL`. Both use a single image digest so code and dependencies are identical. The launcher must not start migrations automatically; migrate and seed only the disposable database through the separate trial fixture workflow.

## Resource and state model

`postgres:17.11-alpine3.23` runs independently of the existing CloudNativePG cluster and needs no extensions or huge pages. Its 4 GiB `openebs-zfs-16k` PVC lasts across pod restarts and is deleted with this namespace. Treat the PVC as disposable: teardown irreversibly removes all trial data. PostgreSQL requests 500m CPU / 512 MiB and is limited to 1 CPU / 1 GiB. Each app requests 200m CPU / 256 MiB and is limited to 1 CPU / 1 GiB. These are trial caps, not measured sizing recommendations.

Pods use restricted security contexts, no mounted service account token, and read-only root filesystems. The apps can write only to their bounded `/tmp` volume. All pods are ingress and egress isolated by default. The only allowed app egress is TCP 5432 to the trial PostgreSQL pod and TCP/UDP 53 to CoreDNS pods in `kube-system`. PostgreSQL accepts TCP 5432 only from these trial app pods. Kubernetes [NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/) is additive; keep this namespace free of other policies that broaden access.

## Operator steps

Use the dedicated home-cluster kubeconfig and an image already available to the cluster by immutable digest. The script checks that context `main` points to `https://192.168.200.16:6443`, requires the trial namespace to be absent before starting, and never uses the ambient current context. It generates a random database password at start, stores it only in a namespace Secret, and does not print it. For a private image, supply a temporary, mode-0600 Docker config JSON via `--pull-secret-file`; the script creates `trial-registry` only in the trial namespace and references it from both app pods. Remove the temporary file after the command returns.

```sh
export TRIAL_KUBECONFIG=/absolute/path/to/home-kubeconfig
./trial.sh start 'registry.example/mkjm@sha256:<64-hex-digest>' --pull-secret-file /private/tmp/.dockerconfigjson
./trial.sh status
./trial.sh access mk 18080
```

The last command listens only on `127.0.0.1`; visit `http://127.0.0.1:18080`. In another terminal, run `./trial.sh access jm 18081`. A VPN user can SSH into the operator host with a local SSH tunnel to its loopback port. The services are `ClusterIP` only, and no HTTPRoute, Ingress, or NodePort is created. [Kubernetes port forwarding](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/) is controlled by API server authorization and may bypass NetworkPolicy, so grant port-forward rights only to trial operators.

Before taking measurements, deploy migrations and synthetic fixtures solely against `postgres.mkjm-hosting-trial.svc.cluster.local:5432/mkjm_hosting_trial`; check that source URLs point at this namespace. Record the exact image digest, migration revision, fixture version, node placement, PVC class, pod resources, and client location alongside latency and errors. The namespace contains no production assets: images that need assets should use local placeholders.

For a fresh trial, stop port-forward processes and run:

```sh
./trial.sh teardown destroy-mkjm-hosting-trial
```

The namespace and PVC must be fully gone before another `start`. The explicit phrase and namespace ownership label guard deletion. Never use a broad `kubectl delete -f kubernetes/` command for this trial.

## Isolation check before benchmarking

Confirm that `deny-all`, `apps-to-trial-postgres`, `apps-to-cluster-dns`, and `trial-apps-to-postgres` are present and that no other policy selects the trial pods. Apply `network-probe.yaml` with the same guarded kubeconfig/context, wait for its pod to run, and execute these checks in it:

```sh
kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context main apply -f network-probe.yaml
kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context main -n mkjm-hosting-trial wait --for=condition=Ready pod/network-probe --timeout=2m
kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context main -n mkjm-hosting-trial exec network-probe -- nslookup postgres.mkjm-hosting-trial.svc.cluster.local
kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context main -n mkjm-hosting-trial exec network-probe -- nc -z -w 3 postgres.mkjm-hosting-trial.svc.cluster.local 5432
kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context main -n mkjm-hosting-trial exec network-probe -- nc -z -w 3 1.1.1.1 443
kubectl --kubeconfig "$TRIAL_KUBECONFIG" --context main -n mkjm-hosting-trial delete pod network-probe
```

DNS and trial PostgreSQL must succeed; the public IP attempt must fail. Repeat the negative check against the actual live production database service after confirming it exists from a trusted non-trial vantage point, so a nonexistent endpoint cannot yield a false pass. Inspect Cilium drop verdicts for the probe during the failed attempts. Check that neither app logs a QBO, email, R2, or production database connection attempt. A port-forward request to each `/api/health` should succeed without exposing either service publicly.

Observed results and the selected business database direction are recorded in the [private trial report](https://github.com/heavybullets8/mkjm-hosting-publisher/blob/main/RESULTS.md).
