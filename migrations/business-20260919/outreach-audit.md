# Bighorn Byte outreach audit

September 19, 2026. Scope: Bighorn Byte outreach and its shared application
runtime. No Scale TV or customer application changes.

Application revision: `500e0dab62d081476d993d3354eeea237d72e208`.

## Corrections

- Free email screenshot preparation can proceed when paid AI work is held by
  the monetary cap. Zero-cost provider requests still enforce request allowances.
- Spending screens distinguish dollar budgets from free request limits, account
  for outstanding reservations, and use current provider descriptions.
- Production bot checks use the explicit application environment rather than
  treating every non-Deno-Deploy process as a developer workstation.
- Production web requests delegate provider jobs to the dedicated worker.
  The web deployment explicitly sets an empty `OUTREACH_DEPLOY_ROLES` as well.
- Mail settings and enablement validation use the same environment policy as
  the actual mail worker. Preview environments remain isolated.
- The temporary migration-branch image publication trigger is retired.
- Research imports deduplicate equivalent normalized branch contact methods.
  Large research-application transactions have a 60-second timeout; ordinary
  transactions retain their existing 15-second timeout.
- Raising the daily monetary cap wakes jobs held by that cap immediately,
  preserving per-job budgets, checkpoints and recorded spending.

## Validation

- Application checks: 1,524 unit tests passed, two ignored; formatting, lint,
  types, and Fresh guard passed.
- CI production build and HTTP smoke passed.
- CI database lane: 794 tests passed, one ignored.
- Production transport smoke before rollout: guarded VPN fetch HTTP 200;
  private Chromium produced a valid 15,909-byte PNG; free search returned three
  results. No paid model calls, email sends, or database writes were used.

## Capacity and remaining work

The audit found healthy workloads and substantial CPU/memory headroom. Existing
money holds, rather than local resource limits, explained the idle job worker.
Historical paid crawling receipts remain historical charges; new local search,
extraction, and rendering reserve and settle zero monetary cost.

Follow-up work is tracked in BIG-141. Prioritize bounded discovery while AI
assessment waits, then a shared browser context limit and measured parallel
workers. Keep monetary caps and mail pacing independent. Review database pool
waits and repeated downloads before changing pool sizes or adding shared caches.

Other cleanup candidates: retire obsolete Deno cron/configuration paths; replace
IndexNow's same-day sitemap check with proof of the deployed revision; align the
disposable CI database lane with the production PostgreSQL major version; remove
obsolete provider settings without invalidating historical data.

## Authorized recovery

The owner approved resuming the five location-change email holds. All five
passed recipient, location, time-zone, saved-content and suppression checks,
and were resumed through the normal outbox handler. Each has exactly one active
send job, with scheduling and sequence ordering preserved; no immediate send
was requested.

The six pre-cutover research retries reuse their saved checkpoints and normal
budgets. Completed provider work and historical charges are retained.

At 20:00 UTC, all six were verified `SUCCEEDED`: Southwest, Imperial, Zona,
Patriot, Happy and West River. This includes successful production application
of the imports that previously failed on duplicate contact methods or transaction
timeouts. No research job received an over-cap override.

For the owner's requested immediate discovery run, a dated one-off Job restores
the temporary 1,000-cent daily cap to 500 cents at September 20 00:00 UTC
(September 19, 6 p.m. Denver). It passed its live startup validation before any
temporary cap increase. See `restore-outreach-cap.md` for its version checks,
expiry and the different-cap safeguard. The spending ledger is not reset.

The temporary cap was applied at 19:56:59 UTC. All 23 jobs waiting on the daily
monetary cap were released immediately. Existing recorded spending was
4,992,640 microdollars and was preserved.

Two operator-started Alaska discovery batches completed normally. Completed
queries increased from 341 to 343 and found candidates from 70 to 73. Ten new
VPN extraction receipts and two local search receipts all settled at zero cost.
Five DeepSeek receipts settled at a combined 9,751 microdollars ($0.009751),
exactly matching the discovery job's incremental spending; no receipts remained
open for those batches. Automatic work continues under normal shared caps.

Final health checks found both application deployments Ready on the recorded
revision, no container restarts, HTTP 200 from the public home, admin login and
readiness endpoint, and no firing warning or critical alerts. The five resumed
emails remained normally queued, with zero attempts and one active job each.

## Private demo isolation repair

The owner reported the public `/demo` showing a private dealer's branded admin
preview. An anonymous production HTTP request reproduced the exposure without
a cookie: the response contained that dealer's presentation and staff-review
navigation paths. The response was dynamic with `private, no-store`, rather
than a cached public page. Database-backed web routes were placed in maintenance
while the fix was prepared; the marketing site and worker remained available.

The actual compiled application reproduced the same problem over a loopback
HTTP server: private A, private B, then anonymous `/demo` rendered private B.
The application now opens a neutral demo context at its outermost request
middleware, before any routing or observation middleware runs. Private routes
then establish their own authenticated or capability-scoped context normally.
This correction is application revision
`85e5f7c62f0fa44bf599234c6a3ae72c2656d93d` and changes only the web image in
production. No particular Deno vendor defect or version is established as the
cause; smaller standalone async-context harnesses did not reproduce the leak.

Validation before publication:

- The compiled HTTP regression failed before the fix and passed afterward.
- Cold staff-review startup, two private recipient links, public chooser and
  generic storefront, concurrent requests, invalid capabilities, and staff
  review authentication are covered. CI now builds and runs this formerly
  optional compiled-route regression in the database lane.
- Four independent browser contexts passed on the production Deno version,
  including visiting the public demo in the same browser after a private demo
  or staff review. Browser runtime errors: zero.
- Full source checks passed: 1,524 unit tests, formatting, lint, types and Fresh
  guard. The dedicated compiled database test and cold-start check passed.
- A read-only maintenance-window worker audit found no failed or paused research
  work and no affected email-drafting or screenshot jobs. Two normal retries
  concerned external dealer-site access restrictions, not the maintenance page.
  No warning or critical alerts were firing.

Release verification:

- Check run `35467554773` passed for the exact fix revision: 1,524 unit tests,
  795 database tests and build/boot/HTTP smoke checks. Image publication run
  `35467554713` passed.
- Web image pinned to
  `sha256:00655aedc65274e4b4dd0f7464b1cf8df3803e950b664dc3679aef3f1e2f9803`.
- The new image passed a contained production check before reopening and the
  live listener passed the same check afterward: 27 requests, 201 assertions,
  two real existing recipient links, two staff reviews, anonymous chooser,
  generic storefront, concurrent requests and rejected invalid credentials.
  Both temporary verification sessions were deleted successfully. Existing
  revisions, leads and recipient links were not changed.
- Removing the maintenance entry from Helm values left the imperative emergency
  setting on the Deployment. Live verification caught the resulting HTTP 503.
  The desired state now explicitly sets `BHB_MAINTENANCE_MODE=0`, and the live
  Deployment was reconciled to that value before the successful live checks.
- An independent public browser request followed `/demo` to `/demo/start` with
  HTTP 200 and the five generic industry choices. Private navigation links and
  private presentation payloads were absent; browser runtime errors were zero.
  The existing production bot-verification gate remains enabled.
