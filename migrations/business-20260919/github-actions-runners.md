# Business GitHub Actions runners

The runner definitions live in
`kubernetes/apps/actions-runner-system/actions-runner-controller/runners/business/`.
They share the existing ARC controller and GitHub App registration, while each
pool is bound to a single repository. The administrative `heavy-ops-runner` pool
is unchanged.

This document records the initial self-hosted rollout. The current security
profiles, unprivileged cutovers, image contracts, and remaining builder work are
recorded in [GitHub Actions runner hardening](github-actions-runner-hardening.md).

## Scope

The account audit found 50 repositories: 36 active owned repositories, 20 with
Actions workflows. The 15 private workflow repositories have business pools:

- bighorn-byte, deno-kit, nix-config, fcc-spam-reporter, scale-tv
- mk-jm, mk_rentals, connelybrothers, connelyslandscaping
- cloudpeakinsulation, anytimesteel
- site-fallback-worker, email-guard-worker, image-resize-worker, b7-leather

The label is `<repository>-runner`, except `mk_rentals` uses
`mk-rentals-runner`. The user authorized the existing GitHub App installation
for all repositories. Adding a future repository still requires its own pool and
a matching workflow label.

Five public repositories retain GitHub-hosted jobs: heavy-ops, containers,
new-plex-dubs, zfs-scrubber, and 1d-nesting. Their standard hosted compute is
free, and public pull requests must not execute arbitrary code on these
production-network runners. The existing heavy-ops administrative runner job
remains as configured. The containers repository also needs native ARM builds.
Archived repositories, forks, and repositories with no workflows were excluded.

## Runtime

Bighorn Byte keeps two runners ready when idle and allows three concurrent
runners. The other business pools scale to zero; deno-kit and MK/JM allow three
concurrent runners each, and the remaining pools allow one each. MK/JM has
two application check/smoke lanes, so its pool was expanded after the first run
showed them waiting serially despite ample server capacity. Each job gets a
fresh runner and Docker daemon. No Talos secrets, cluster-admin service account,
or Kubernetes API token are mounted.

The explicit ARC Docker-in-Docker template bounds both processes:

| Process       | CPU request / limit | Memory request / limit |
| ------------- | ------------------- | ---------------------- |
| Runner        | 0.5 / 4 cores       | 1 / 4 GiB              |
| Docker daemon | 0.5 / 4 cores       | 2 / 6 GiB              |

The work volume is an emptyDir capped at 20 GiB. Runner and daemon ephemeral
storage limits are 10 GiB and 40 GiB. Images are pinned by digest. Docker uses
GID 123, verified against the actual runner image. The daemon is privileged as
required by this ARC mode; it is not a hardened boundary for untrusted code.

Application credentials stay in GitHub's existing job/repository secrets. Node,
Deno and Python requirements are declared in the workflows. In particular,
Deno-kit's package build and Cloudflare deployment actions need Node/npm; the
minimal runner image does not supply it implicitly.

## Shared workflows

Deno-kit's active reusable workflows accept an optional `runner` input with an
`ubuntu-latest` default for existing consumers. Every migrated caller passes its
repository label. The database migration workflow forwards it into the nested
backup workflow. The unused legacy `db-push.yml` has no active caller and was
not changed.

Customer database backup schedules remain in place where those databases still
run off-server. The already removed Bighorn Byte and Scale TV database backup
schedules were not restored.

## Rollout evidence

Infrastructure commit `3aa7dc51` installed all 15 pools successfully. GitHub App
registration and all listeners were verified healthy with no restarts.

- FCC Docker build and GHCR push: run `35546110503`, passed.
- Deno-kit Node setup correction: PR #287, run `35546383010`, passed; merged
  main run `35546525545` passed, including 3,366 tests and package build.
- Bighorn Byte check: run `35546153217`, passed on its own runners, including
  unit checks, app smoke, PostgreSQL services and the Poppler database lane.
- Bighorn Byte four-image publish: run `35546610104`, passed on its own runners.

During the Bighorn build/database checks, the server used about 23% CPU and 19%
memory. The observed runner peak was about 2.06 CPU cores and 2.83 GiB memory.

The customer sites already verified on their new runners include Anytime Steel
(Check `35546353565`) and Cloud Peak Insulation (Check `35546497666`); both
production Deno deployments passed. Connely's Landscaping moved through reviewed
PR #83 and Connely Brothers through reviewed PR #127. MK Rentals moved through
PR #79 (main Check `35547494085` passed), and MK/JM through PR #165 (main Check
`35547902614` passed, including both application smoke lanes). Every customer
production Deno deployment passed, including both MK/JM applications. Newer
customer commits were preserved while rebasing the workflow-only changes.

The final audit read all 15 actual default branches: 57 workflow files
inspected, 56 active files after excluding the unused legacy db-push definition,
and 66 active job definitions. All 30 direct jobs and 36 reusable workflow calls
select or propagate the intended runner. Bighorn Byte and Scale TV each have
zero legacy backup workflow files and zero backup workflow calls.

The additional rollout group completed as follows:

| Repository           | Workflow run                                | Result                                                                                                                                                                                         |
| -------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| nix-config           | `35546323704`                               | Renovate dry-run passed on runner label `nix-config-runner`, proving scale-from-zero scheduling without repository writes. The workflow-only push correctly matched no path-filtered push job. |
| scale-tv             | `35546344350`, `35546344007`                | Check, smoke, PostgreSQL tests, Docker build and GHCR publication passed.                                                                                                                      |
| site-fallback-worker | `35546536473`                               | Tests and Cloudflare deployment passed.                                                                                                                                                        |
| email-guard-worker   | `35546553327`                               | Mail and portal tests, D1 migration, mail deployment, schema health check and portal deployment passed.                                                                                        |
| b7-leather           | `35546398464`                               | Theme checks, Python schema-limit check and development-store theme push passed.                                                                                                               |
| image-resize-worker  | `35546562616`, `35546562606`, `35546562662` | Deno check and both Cloudflare deployments passed.                                                                                                                                             |

The nix-config dry-run proved runner scheduling but did not execute Nix. The
[pinned installer documentation](https://github.com/cachix/install-nix-action/tree/13d8dd58da0234aa297dedd986986ccb8e7f3e24)
explicitly supports self-hosted Linux runners. The live pinned runner image is
Ubuntu 24.04 with bash, curl, sudo and Python 3; it has no systemd. The action's
exact install script detects that condition and selects its single-user path,
while unavailable KVM is non-fatal. A real Nix install and flake evaluation
remain to be proven by the next normal path-filtered or scheduled Nix job.

The first site-fallback, email-guard and image-resize deploy attempts stopped
inside Wrangler Action before any Cloudflare command because npm was absent.
Their follow-up commits install Node in the affected jobs; the successful runs
above performed the deployments. Email guard's first attempt stopped before
executing its D1 migration.

[GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
documents that self-hosted usage is free; artifact/cache storage remains
separate.
[ARC scale-set documentation](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/deploy-runner-scale-sets)
covers the runner-label and Docker template used here.

## Initial timing comparison

The last hosted Bighorn check (`35545497968`, e26dfc9 application code) and
first self-hosted check (`35546153217`, e5f6908, only workflow routing changed)
produced these successful job durations. This is an initial observation, not a
controlled benchmark; startup, caches and network conditions can affect timings.

| Job                           | Hosted      | Self-hosted |
| ----------------------------- | ----------- | ----------- |
| Formatting, types, unit tests | 122 seconds | 76 seconds  |
| Application smoke             | 124 seconds | 85 seconds  |
| Database tests with Poppler   | 455 seconds | 322 seconds |

These jobs used about 29–38% less elapsed time on the server. Image builds had
large cache differences and are not used to claim a hardware speedup. Server
power consumption attributable to CI was not measured.


## Bighorn CI performance tuning

The Bighorn pool uses the public `ghcr.io/heavybullets8/business-runner` image,
built by [containers PR #183](https://github.com/heavybullets8/containers/pull/183).
It extends the same pinned home-operations runner and preinstalls `poppler-utils`.
The amd64 image contract verifies the runner UID/GID, Docker group, runner script,
externals directory, sudo and `pdftotext`; its release also verifies provenance.
Both Bighorn's runner and externals-init images are pinned to the same digest.
Other runner pools and all per-container resource limits retain their previous
configuration. Bighorn keeps two idle runners ready within its existing maximum
of three, reducing the measured 12–18-second cold startup without increasing
peak runner capacity. Commit `e2866784` enables that warm pool; it uses the same Flux webhook.
No registry credential is needed: the published image was checked anonymously.

Infrastructure commit `42837848` was applied by the normal Flux webhook. The
Bighorn HelmRelease reported generation 2, observed generation 2 and Ready=True,
and its AutoscalingRunnerSet selected the new digest before testing the workflow.

[Bighorn PR #71](https://github.com/heavybullets8/bighorn-byte/pull/71) removes the
local database job's dependency on the entire reusable check/smoke call. Each
job has its own runner and Postgres service, so their database names and ports
remain isolated. All jobs still contribute to the Check result that gates image
publication. Smoke still exercises live dev-SSR HTTP routes; the local DB job
owns the single application build and compiled-route assertions.

The disposable Postgres 17 data directory uses a 2 GiB tmpfs and 256 MiB shared
memory. The data mount used 158 MiB during the trial. Those are caps, not upfront
reservations; tmpfs usage counts toward the DinD container's existing 6 GiB limit.
PostgreSQL durability settings are unchanged. Persistent application databases
are outside this workflow.

The disk control confirmed that the runner uses the 960 GB Intel Optane system
drive through Talos's 100 GiB EPHEMERAL partition. Optane was already fast: one
controlled pair measured the DB test command at 167.45 seconds with tmpfs and
174.31 seconds on disk (both 813 tests and 20 steps passed). This modest 3.9%
difference is an observation from one pair, not a general hardware speed claim.

| Configuration | Run | Full workflow | DB test command |
| --- | --- | --- | --- |
| Initial self-hosted, serial job graph | `35546153217` | 8m45s | ~182.7s |
| Concurrent jobs, RAM database, original PDF install/builds | `35548686839` | 4m23s | 167.45s |
| Concurrent jobs, disk control, original PDF install/builds | `35548988744` | 4m25s | 174.31s |
| Final PR: prebuilt tools, one build, deterministic fixtures | `35550161669` | 4m10s | ~167s |
| Merged main with warm runners | `35550427574` | 4m00s | ~167s |

Package installation varied from 71 seconds initially to 8–10 seconds in the
trials. Preinstalling Poppler removes that variable network operation. Omitting
the duplicate smoke build saves about 40 seconds of runner work while retaining
its compiled coverage in the DB job. The main elapsed-time gain is overlapping
independent jobs, not additional CPU or a large RAM cache. Observed runner use
was about two CPU cores and 2.8 GiB, below its unchanged four-core/4 GiB limits.

The first custom-image trial passed unit and smoke checks but exposed existing
nondeterministic DB assertions: pricing expectations depended on the real UTC
clock crossing a DeepSeek rate window, and a credential assertion split a
base64url secret on every underscore. The final workflow PR also makes those
fixtures deterministic. It pins test clocks consistently through enqueue,
claim and model calls, verifies explicit peak/off-peak charges, and checks the
full parsed credential against its stored hash and plaintext-absence assertion.
These are test changes only; production billing/authentication logic is unchanged.


Final verification on merge commit `5decf7784df1208a0806b4e917030032e44f61ca`:
[main Check run 35550427574](https://github.com/heavybullets8/bighorn-byte/actions/runs/35550427574)
passed in exactly four minutes, about 54% less elapsed time than the initial
8m45s self-hosted run. The database job started three seconds after workflow
creation. All 813 database tests and 1,571 unit tests passed (two existing unit
tests remain ignored). All seven HTTP smoke paths returned 200; smoke took
41 seconds versus the original 85 seconds. No tests were removed, and the
compiled-route build remains covered. The retained RAM database again completed
its test step in about 167 seconds. These are observed runs, not guaranteed
future durations; package/network effects contributed to the original baseline.
