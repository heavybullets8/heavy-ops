# One-off outreach cap restoration

This dated Job restores the temporary 1,000-cent daily cap to 500 cents at
2026-09-20 00:00 UTC. It does not reset spend, reservations, request allowances,
job budgets or over-cap approvals. It exits without changing a different cap.
It also refuses to restore after 2026-09-21 00:00 UTC.

The script uses the application's scheduler owner selection and
`saveOutreachSettings`. Each save submits only the daily cap, with the freshly
read settings version. A version conflict rereads the current cap before retrying
(five attempts maximum). Unrelated settings and decrypted secret values are
preserved by the supported settings handler. The handler re-encrypts secrets as
part of its normal save; ciphertext bytes therefore need not remain identical.

Startup validates the database, decryption, owner permission and current cap,
then closes the database while waiting. The `--check` argument performs only
that read-only startup validation and exits. Logs contain status, cap values and
safe failure phases/codes, never credentials or owner identifiers.

These files are deliberately outside all Flux/Kustomize references. The Job has
a 24-hour active deadline, two retries and one-day completion retention. It uses
the existing runtime Secret and verified image digest. Its labels cannot select
it into the outreach jobs Service.

After review and authorization, deploy the prepared ConfigMap and Job once:

```sh
kubectl --kubeconfig /home/heavy/Github/heavy-ops/kubeconfig apply \
  -f migrations/business-20260919/restore-outreach-cap-configmap.yaml \
  -f migrations/business-20260919/restore-outreach-cap-job.yaml
```

Confirm the Job logs show `preflight_ok` before raising the temporary cap. After
midnight, expect `restored`, or `skipped_changed_cap` if another cap was chosen.
The Job TTL does not remove its ConfigMap; remove that dated ConfigMap after
confirming the final result. Do not recreate this Job as a recurring schedule.

If the TypeScript file changes during review, regenerate its embedded ConfigMap:

```sh
kubectl --kubeconfig /home/heavy/Github/heavy-ops/kubeconfig -n business \
  create configmap bighorn-byte-restore-cap-20260920 \
  --from-file=restore-outreach-cap.ts=migrations/business-20260919/restore-outreach-cap.ts \
  --dry-run=client -o yaml \
  > migrations/business-20260919/restore-outreach-cap-configmap.yaml
```
