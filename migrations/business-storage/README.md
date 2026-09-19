# Docmost and Documenso namespace migration

The manifests in `kubernetes/apps/business/docmost-bhb` and
`kubernetes/apps/business/documenso` are deliberately absent from the business
namespace kustomization. Both workloads remain at zero replicas, and their PVCs
pin the final cutover snapshots named in `final-snapshots.yaml`.

## Live storage inventory

| App | Container mount | Current PVC and UID | Current PV and ZFS dataset | Capacity |
| --- | --- | --- | --- | --- |
| Docmost | `/app/data/storage` | `default/docmost-bhb`, `311d746e-0ac6-4278-951f-d12451ea64fa` | `pvc-59c2438a-ec5b-4609-80b6-e2372dc3a770`, `speed/pvc-59c2438a-ec5b-4609-80b6-e2372dc3a770` | 20 GiB |
| Documenso | `/app/data` | `default/documenso`, `e2da3813-b9d5-4754-9f11-8a6c38e59734` | `pvc-217c88f7-635f-4ea9-9540-7852f2f39e80`, `speed/pvc-217c88f7-635f-4ea9-9540-7852f2f39e80` | 10 GiB |

Both PVs use `openebs-zfs-1m`, are bound to `heavy-control`, and have a `Delete`
reclaim policy. Keep the old PVCs intact for rollback. The 2026-09-19 audit
found both mounted filesystems empty (`du -sb` returned 2 and `find -type f`
returned 0); application state remains in the existing `docmostbhb` and
`documenso` databases on `postgres16-rw.database.svc.cluster.local`.

Kopiur currently keeps 22 successful snapshots per app across Truenas and R2.
The latest verified snapshots were `docmost-bhb-20260919090000-repo-truenas-55b3abff`,
`docmost-bhb-20260919090000-repo-r2-d3841ba3`,
`documenso-20260919090000-repo-truenas-4812a2c0`, and
`documenso-20260919090000-repo-r2-c4105346`. The shared Postgres cluster was
healthy with three instances, and its 2026-09-19 scheduled backup completed.

Set the kubeconfig explicitly for every live command:

```bash
export KUBECONFIG=/home/heavy/Github/heavy-ops/kubeconfig
```

## Preflight validation

The Snapshot and Restore fields match the installed
`kopiur.home-operations.com/v1alpha1` CRDs. Before cutover, validate the exact
objects against the live admission chain without persisting them:

```bash
kubectl apply --dry-run=server -f migrations/business-storage/final-snapshots.yaml
flux build kustomization docmost-bhb -n business \
  --path ./kubernetes/apps/business/docmost-bhb/app \
  --kustomization-file ./kubernetes/apps/business/docmost-bhb/ks.yaml --dry-run
flux build kustomization documenso -n business \
  --path ./kubernetes/apps/business/documenso/app \
  --kustomization-file ./kubernetes/apps/business/documenso/ks.yaml --dry-run
kustomize build kubernetes/apps/database/dragonfly/cluster
```

## Cutover

1. Suspend the two default-namespace Flux Kustomizations so Flux cannot restart
   the old Deployments, scale both Deployments to zero, and wait until their
   pods terminate. This is the write fence for the shared databases and PVCs;
   keep both old workloads stopped until the business workloads are ready.

   ```bash
   flux suspend kustomization docmost-bhb -n default
   flux suspend kustomization documenso -n default
   kubectl -n default scale deployment/docmost-bhb deployment/documenso --replicas=0
   kubectl -n default wait --for=delete pod \
     -l app.kubernetes.io/name=docmost-bhb --timeout=5m
   kubectl -n default wait --for=delete pod \
     -l app.kubernetes.io/name=documenso --timeout=5m
   ```
2. Apply `final-snapshots.yaml`. Wait for all four objects to report `Ready=True`
   and `status.phase=Succeeded` before creating either business PVC:

   ```bash
   kubectl apply -f migrations/business-storage/final-snapshots.yaml
   kubectl -n default wait --for=condition=Ready --timeout=20m \
     snapshot/docmost-bhb-business-cutover-truenas \
     snapshot/docmost-bhb-business-cutover-r2 \
     snapshot/documenso-business-cutover-truenas \
     snapshot/documenso-business-cutover-r2
   kubectl -n default get snapshot \
     docmost-bhb-business-cutover-truenas \
     docmost-bhb-business-cutover-r2 \
     documenso-business-cutover-truenas \
     documenso-business-cutover-r2 \
     -o custom-columns='NAME:.metadata.name,PHASE:.status.phase,READY:.status.conditions[?(@.type=="Ready")].status,SNAPSHOT_ID:.status.snapshot.kopiaSnapshotID'
   ```

3. Add the two business app references to
   `kubernetes/apps/business/kustomization.yaml`, reconcile, and keep the new
   Deployments at zero replicas. The passive Kopiur Restores create new PVCs
   from the exact pinned Truenas snapshots. Wait for both restores to complete
   and both PVCs to bind:

   ```bash
   kubectl -n business wait --for=condition=Ready --timeout=20m \
     restore/docmost-bhb restore/documenso
   kubectl -n business wait --for=jsonpath='{.status.phase}'=Bound \
     --timeout=5m pvc/docmost-bhb pvc/documenso
   ```

4. Verify the restored mount sizes with temporary, non-writing inspection pods
   or the still-zero application Deployments. Remove the two old app references
   from `kubernetes/apps/default/kustomization.yaml` and wait for their old
   HTTPRoutes to disappear before scaling the business Deployments up. Two
   Routes with the same hostname and Gateway listener can leave Envoy selecting
   the old zero-endpoint Service.
5. Start one business workload at a time and wait for readiness. The URLs,
   images, Postgres databases, and 1Password item names are unchanged. Docmost
   requires `dragonfly-allow-business-namespace` before startup. Keep the old
   PVCs present through the rollback window; their prune-disabled annotations
   preserve them when the old Kustomizations are removed. Do not delete either
   old PVC while its PV reclaim policy is `Delete`.

The new business SnapshotSchedules have `runOnCreate: false`; their first normal
daily backup establishes the new `business` Kopia identity after cutover. The
four final `default` snapshots are pinned and retained as migration recovery
points.
