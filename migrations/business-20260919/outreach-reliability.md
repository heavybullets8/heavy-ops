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

## Pre-release verification

- Required repository check: 1,570 passed, zero failed, two ignored.
- Integrated affected database suites: 61 tests passed, including six steps.
- Final coverage and scheduler suites after UI/read-model review: 12 passed.
- Chromium desktop 1440px and mobile 390px: Sources, coverage and Operations
  checked. State names and all four desktop columns are visible; mobile cells
  stack without horizontal overflow. Retry times include the time of day.
- The separate local demo-guide changes and accounting work were excluded.

The database repair was previewed read-only: 48 search campaigns and three
assessment jobs match the audited failures. Completed tasks, spend receipts,
existing budgets and attempt history will be retained during recovery.
