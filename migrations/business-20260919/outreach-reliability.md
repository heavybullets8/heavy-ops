# Outreach search recovery and state progress

Application revision: `845a67ccf58607ad3ab4db26061113d823714185`.

## Evidence

- The latest campaigns for 48 states stopped on the free search engine's
  access block. The exact saved error was “Free search requested a pause;
  retry later or use locator catalogs.” The server was not resource-bound.
- One bounded query per engine through the existing VPN returned Brave HTTP
  429 and a DuckDuckGo timeout. FlareSolverr probes also failed; no working
  alternative was established during this incident.
- Three website-assessment jobs failed after 316–334 seconds. Their parent
  job leases were healthy, but the separate assessment lease expired at five
  minutes.
- Alabama's search tasks were complete. Its unresolved candidate reviews
  incorrectly prevented the nationwide display from counting that search plan.
- California's separate refusal was a DeepSeek HTTP 400 during business
  classification. It is not classified as a search-service outage.

## Change

Search throttling and temporary search transport/access failures now defer
the same job without consuming its failure allowance. The worker shares an
engine cooldown of 15 minutes, doubling on consecutive failures to a maximum
of six hours, honoring a longer Retry-After. A successful response resets the
cooldown. The queued job's next attempt time persists across process restarts.

Recovered state campaigns wait their turn before the scheduler opens new
states. One automatic campaign stays active across its search waits. Manual
state requests can resume a waiting plan without discarding its checkpoints.
Persistent search problems produce at most one grouped notification per UTC
day, after a wait of at least 15 minutes, instead of per-state failure notices.

Website assessments renew their lease every minute while their own unexpired
claim and parent job are still owned. A stale worker cannot renew or overwrite
a successor's claim.

Sources reports real completed search tasks (excluding the internal plan-ready
marker), independently of candidate reviews. It displays the current state's
progress, running/waiting status and retry time. State coverage uses a wider
dialog on desktop and stacked rows on mobile. Automatically waiting scouts
appear under Waiting rather than Needs you.

## Verification

- Required repository check: 1,570 passed, zero failed, two ignored.
- Integrated affected database suites: 61 tests passed, including six steps.
- Final coverage and scheduler suites after UI/read-model review: 12 passed.
- Chromium desktop 1440px and mobile 390px: Sources, coverage and Operations
  checked. State names and all four desktop columns are visible; mobile cells
  stack without horizontal overflow. Retry times include the time of day.
- The separate local demo-guide changes and accounting work were excluded.

Deployed through heavy-ops `79eb1489` after GitHub Check `35544458513`
and Publish images `35545137757` succeeded. Both deployments became ready,
and the public `/healthz` endpoint returned `{"ok":true}`.

Production recovery completed on September 20, 2026:

- 48 exact legacy search failures moved into the automatic recovery queue;
  37 old notifications were acknowledged without deleting history.
- All three exact legacy assessment claim failures resumed and succeeded.
- No legacy failures or pending assessments remain.
- Alaska is the only queued/running automatic campaign; the other 47 recovered
  states wait their turn. Its next search was blocked by the external engine,
  so the worker scheduled a retry without increasing its existing failure count.
- Nationwide coverage reports Alabama complete at 664/664 real searches.
- Tasks, costs, budgets and attempts were preserved. Other failures were not
  silently cleared; California's separate content-refusal fix is being released.

Immutable image digests for revision `845a67c`:

- Web: `sha256:cbfda0df79d2656955a966c0ff30c573f38db637b2bd134273a437973ad3ca51`
- Outreach: `sha256:35408446e5ef721ed3a85264cdfeeb95aec87c1c8427b05261db9caf941d536a`
