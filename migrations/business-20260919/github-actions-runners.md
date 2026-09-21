# Business GitHub Actions runners

The runner definitions live in
`kubernetes/apps/actions-runner-system/actions-runner-controller/runners/business/`.
They share the existing ARC controller and GitHub App registration, while each
pool is bound to a single repository. The administrative `heavy-ops-runner` pool
is unchanged.

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

All business pools scale to zero when idle. Bighorn Byte, deno-kit and MK/JM
allow three concurrent runners each; the other pools allow one each. MK/JM has
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
