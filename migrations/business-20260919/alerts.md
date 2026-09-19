# Migration alert investigation — 2026-09-19 UTC

Actual Alertmanager and Prometheus data were queried from 15:00 UTC onward.
At 18:30:32 UTC there were **zero firing warning/critical alerts**. Alertmanager
contained only Watchdog and InfoInhibitor (both severity none).

## Cause and impact

The document-service namespace move left two generated monitoring ConfigMaps in
`default` while creating the same entries in `business`. Gatus watches all
namespaces. It loaded both copies and exited with code 2:

`invalid endpoint external_docmost-bhb: name and group combination must be unique`

The affected stale objects were `default/docmost-bhb-gatus-ep` and
`default/documenso-gatus-ep`. Their endpoint names/groups/URLs were identical to
the new business ConfigMaps. The old default apps were no longer referenced by
their parent Kustomization. This was migration-caused, not an OOM or node-pressure
failure. Capacity measurements independently showed no node pressure or current
business/DB OOMs.

| Signal | Severity | Observed UTC interval |
| --- | --- | --- |
| Notes and Sign endpoint probes failed | metric | 17:36–17:41, after healthy samples through 17:35:30 |
| GatusEndpointDown, docmost-bhb + documenso | critical | firing sample 17:41:30; samples disappeared when Gatus crashed |
| Gatus application crash loop | pod state | began about 17:41; 14 restarts before replacement |
| TargetDown, Gatus | warning | began 17:51:52; cleared after recovery scrape |
| KubePodNotReady, Gatus | warning | began 17:56:53; cleared after replacement |
| KubeDeploymentReplicasMismatch, Gatus | warning | began 17:56:53; cleared after replacement |
| KubePodCrashLooping, old Gatus pod | warning | began 17:57:23; cleared by 18:30:32 after its 5-minute lookback expired |
| CPUThrottlingHigh, Flux kustomize-controller manager | info | firing samples 17:44:30–17:46; subsequently pending during reconciliations |

The monitoring gap from about 17:41 to 18:25 is not continuous-uptime evidence.
Current successful probes prove recovery; disappearing old endpoint alerts alone
did not. No other firing warning/critical alerts were present in the queried
migration interval.

## Fix and verification

Removed only the two stale default monitoring
ConfigMaps and restarted Gatus. No application state, PVC, secret, or alert
silence was changed. Gatus became 2/2 Ready with zero restarts, its Prometheus
scrape returned up=1, and Notes/Sign probes succeeded.

Bighorn and Scale TV lacked endpoint monitoring. Added unique public `/readyz`
checks in commit `9b41d7af`, pushed and reconciled. Scale TV uses the existing
external Gatus component; Bighorn uses the same labeled ConfigMap pattern for
the apex hostname (the shared template always inserts a subdomain).

At 18:29:21 all four `gatus_results_endpoint_success` series were 1:
`bighorn-byte-web`, `scale-tv`, `docmost-bhb`, `documenso`.

The repeatable check `/tmp/bhb-alert-check.py` queried actual firing warning and
critical alerts. It exited 1 while the fault/old-pod lookback remained and exited
0 at 18:30:32 after recovery. API access used temporary localhost forwards to
Prometheus 19090 and Alertmanager 19093. Historical evidence is retained in
`/tmp/bhb-alert-history.json` (alert labels and timestamps only).

No alert suppression or capacity-limit changes were used to obtain the green
result. A separate informational Flux CPU throttle condition remains pending,
not a firing warning or critical alert.
