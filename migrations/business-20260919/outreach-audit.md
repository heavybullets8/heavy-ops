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

## Default FlareSolverr dealer research

The two reported research failures (99 West Trailers and 4 Corners Trailers)
reproduced with both the raw VPN reader and the prior Playwright fallback.
FlareSolverr returned real dealer HTML for both. At the owner's request,
FlareSolverr is now the normal HTML research reader, using one warm session
across each dealer's extraction batches and homepage screenshot. PDFs, images,
search and structured feeds retain their native VPN readers; private demo
screenshots retain their separate Playwright service.

Application revision `e225184ad3bef32e16b33fcd1507181b294116b4` passed Check run
`35472144208`: 1,539 unit tests, 798 database tests, formatting, lint, types,
Fresh guard and build/boot/HTTP smoke checks. The compiled private-demo
isolation regression remains in that lane. Publish run `35472143374` produced
the pinned web, outreach and solver images. Native offline Chromium checks also
passed against the patched solver, together with 13 Python tests.

The dedicated solver and gateway run in `business`. The gateway verifies public
addresses using VPN DNS and opens SOCKS connections to vetted numeric IPs.
Chromium retains its TLS connection inside the tunnel. Cilium admits only
web/outreach to solver, solver to gateway, and gateway to Gluetun (plus DNS).
The solver image enforces the gateway, validates final document HTTP status,
keeps cookies inside the browser, bounds sessions, and reaps idle sessions.
Challenge headers/pages and HTTP 429 are rejected; screenshots share the same
session and throttling aborts the crawl. All crawl and screenshot receipts
remain zero cost, with existing AI budgets and daily call limits preserved.

Deployment validation:

- Support infrastructure: `e8bee86d`; compatible Deno exec probe correction:
  `a00bd635`; application enablement: `0b8260d3`. The gateway process started
  normally, but its original probe used a flag unsupported by the pinned Deno
  image. The corrected live probes match Git; Helm upgrade v2 is Ready.
- Both actual dealer sites returned HTTP 200 and valid screenshots through the
  dedicated service. First reads took 40.9 and 28.1 seconds; subsequent warm
  screenshot reads took 4.7 and 4.2 seconds. API cookie arrays were empty, and
  both sessions were destroyed afterward.
- Eight actual private-address HTTP/CONNECT probes returned 403. Solver direct
  Internet, raw Gluetun, and internal web connections were blocked. Gateway
  direct Internet was blocked. Both pods were Ready with zero restarts.
- Web Helm v11 and outreach Helm v7 are Ready on the tested images. Public home
  and readiness returned HTTP 200; anonymous `/demo` redirected to the generic
  `/demo/start`, without the reported private branding or staff-review links.
- During initial research the solver used about 576 MiB and the gateway 43 MiB;
  the host was using about 17% of its memory. The four-session maximum is a
  safety bound, not a claim of measured four-browser throughput.
- The two original research jobs were resumed through `controlJob`, preserving
  checkpoints, spending and caps. No mail schedule or recipient was changed.

The first concurrent production run exposed an undersized shared gateway limit:
one browser held about 25 tunnels, and the two-browser probe reached 64 TCP
connections (32 browser connections plus 32 upstream connections) before Chrome
reported `ERR_CONNECTION_RESET`. Browser creation itself succeeded, and an
independent offline two-browser navigation passed under the pod's CPU/memory
limits. The 99 West job continued and succeeded; the affected 4 Corners job was
returned to the normal serial queue with its spending and checkpoints intact.

Follow-up application revision `771ee73e257dbd2fce41d0bb895f8c818ed8c2a5` makes
the gateway bootstrap's shared connection ceiling configurable, defaulting to
128 for the existing four-session bound. The generic helper remains at 32.
A regression holds 40 real simultaneous tunnels. The solver also treats an
already-destroyed session as successful cleanup, avoiding the misleading second
error after a failed request already removed its browser. Local checks passed:
1,540 unit tests, 8 gateway tests, 14 Python tests and native Chromium smoke.

A separate ASSESS batch encountered HTTP 429 from `www.city-data.com`. This is
not one of the two reported dealers. The directory-filtering and per-site
cooldown follow-up is recorded on BIG-141; no site throttling or paid budget was
bypassed to clear it.

Both original research jobs subsequently completed successfully: 99 West at
22:32:43 UTC and 4 Corners at 22:39:51 UTC. Their original $2 per-job limits
remain, `overCap=false`, and all attempt receipts are settled. The 10 and 11
new crawl/screenshot receipts respectively total zero microdollars. Total saved
job spending is 60,044 microdollars for 99 West and 76,493 for 4 Corners; the
latter includes its pre-existing 8,000 microdollars. The successful retries
therefore added $0.128537 combined, from paid processing rather than crawling.

Capacity-fix release verification:

- Check `35473676159` passed with 1,540 unit tests, 798 database tests and HTTP
  smoke checks; Publish `35473675743` succeeded for the exact follow-up SHA.
- Infrastructure `483e55b7` deploys only the gateway and solver corrections.
  The solver was idle before rollout. Helm v3 is Ready; web/outreach remain on
  the already-validated `e225184` application images.
- A final concurrent production canary read and photographed both actual
  dealers successfully (HTTP 200, real dealer content, valid PNGs, empty API
  cookie arrays). Repeated session destruction also succeeded. The gateway
  reported its configured 128-connection limit and handled a peak of 184
  established TCP connections, exceeding the old saturation point.
- Public home and readiness returned HTTP 200 after both research jobs finished.
  Anonymous `/demo` still opened the generic chooser without TNJ, 99 West,
  4 Corners or staff-review navigation content. No warning or critical alerts
  were firing.

## Browser origins after TLS termination

The operator reported HTTP 403 from the events page's "Mark all read" action.
A temporary owner session reproduced the actual public HTTPS request without
changing any notifications (`seenAt=invalid`): authenticated GET returned 200,
but POST returned 403. The same internal HTTP POST succeeded only when its
Origin was also HTTP. The application was comparing the browser's HTTPS Origin
to Deno's internal HTTP request URL. This concerns incoming HTTPS routing, not
the outbound crawler/VPN proxy. Controlled 403 responses are not emitted by the
application's server-error logger, so a clean error log did not detect this.

Application correction `b4b924823de85536dc778f44e81425b87bdb16ca`:

- Resolve browser writes against validated `BHB_PUBLIC_ORIGIN`. Missing, null,
  foreign and internal origins remain forbidden. Forwarded host/proto headers
  cannot override that trusted origin; invalid configuration fails closed.
- Apply the shared guard to outreach forms, mail JSON actions, preview contact
  forms, preview browser events and browser error reporting.
- Use the public origin for analytics classification, demo navigation/referrers,
  mail workspace/composer URLs, screenshot requests and captured mail tracking.
  Entry and preview visit cookies now retain Secure behind TLS termination.
- Configure the auth package's separate `SITE_URL` and `DENO_ENV` inputs in the
  web deployment. A harmless missing-fields login probe confirmed the old
  configuration rejected even the legitimate HTTPS origin before credentials
  were checked. The existing www redirect already canonicalizes to the apex.

Local verification passed: 1,547 unit tests and 59 affected database tests.
The compiled app regression drives the real HTTP boundary with an owner session,
marks only notifications visible at the page's saved cutoff, leaves newer
notifications unread and rejects foreign/missing/null/internal origins. It also
checks the sign-in origin gate without credentials or external bot verification.
Existing private-preview isolation checks still pass. Production canaries use
short-lived sessions held only inside the web pod and delete them afterward.

Release gate: Check `35475428862` passed for that exact application revision,
including source/unit checks, compiled-page smoke and the full database lane.
Publish `35475428027` succeeded. The prepared web image is pinned to digest
`sha256:53cd6c66ed40c0e97b6f41333398e4f0e43274f54aafc512b8260d091894f4ef`.
The HelmRelease passed a server dry-run before reconciliation. The separate
outreach worker and crawler deployments retain their already-verified images.

Production verification after infrastructure `21f2ca5a`:

- CI's complete database lane passed 799 tests (20 steps), with zero failures.
- Web Helm release v12 is Ready on the exact digest above. The new pod is
  available; application maintenance remains explicitly disabled.
- Authenticated public events GET returned 200. The no-op `read_all` POST now
  returns 303 for the legitimate HTTPS origin, while foreign, missing, null and
  internal HTTP origins each return 403. No real notifications were marked.
- The real mail workspace API returned 200 and HTTPS public context. A sign-in
  form with empty credentials reached required-field validation for the proper
  origin, while the foreign origin still hit the security-policy rejection.
- The temporary probe session was deleted. The new web pod logged no errors,
  and Prometheus reported no firing warning or critical alerts.
- Public home/readiness returned 200. Anonymous `/demo` still opened the
  generic chooser without any of the tested private dealer brands.

Documentation-only app commit `265eeda` removes the development template's
explicitly blank public origin and documents matching auth/app configuration.
It changes no runtime code; the deployed application remains the verified
`b4b9248` image. Its local required checks also passed all 1,547 unit tests.


## DR Trailer Sales: stop an endless Sent-folder reconciliation

The dealer's September 17 business suppression, “Asked not to be contacted,”
was present and its opportunity closed. Three unsent messages were stopped.
The waiting ARCHIVE_EMAIL task concerned one message accepted on September 15,
before that suppression; it was not another delivery attempt. The copy result
was unknown and its worker kept polling every 15 minutes without a deadline.
The operations list's cancel button also went through the generic job handler,
which intentionally refuses mail jobs.

Cancelled only that exact stale copy job, preserving the original sent timestamp,
single delivery attempt, uncertain copy journal and business suppression. After
cancellation there were zero active mail jobs or queued/sending messages for DR.
No message was sent or copied as part of this repair.

The permanent change gives Sent-copy tasks a dedicated cancellation operation,
uses a lease/state fence before recording late worker results, and stops unknown
copy reconciliation after 24 hours. An unknown copy is never appended again.
Delivery jobs retain their existing separate controls. The operations detail
exposes cancellation and describes unresolved copies as “Sent copy unconfirmed.”

Local regression coverage passes all 49 affected mail and action database tests,
including bounded reconciliation, DNC/delivery preservation, idempotent
cancellation, a late result after cancellation, and rejection of generic mail
send cancellation.

The required repository check passed 1,548 unit tests with no failures, plus
formatting, lint, types and Fresh guard. Application commit: `76021d3`.
All four image builds in Publish `35477063860` succeeded. The web and outreach
image updates passed a server dry-run in the existing business namespace.
Production's other 100 Sent-copy jobs were all successful; this was its only
unresolved copy task. Warning/critical firing alerts were empty before rollout.

Release gate: Check `35477055724` passed for exact application revision
`76021d3e20b7fdc545e44b92e2eee90d3042a132`, including compiled-page smoke and
the full database lane. Web and outreach use the corresponding immutable
digests recorded in their HelmRelease manifests.
