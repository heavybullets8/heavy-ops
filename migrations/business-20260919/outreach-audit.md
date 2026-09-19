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

For the owner's requested immediate discovery run, a dated one-off Job restores
the temporary 1,000-cent daily cap to 500 cents at September 20 00:00 UTC
(September 19, 6 p.m. Denver). It passed its live startup validation before any
temporary cap increase. See `restore-outreach-cap.md` for its version checks,
expiry and the different-cap safeguard. The spending ledger is not reset.
