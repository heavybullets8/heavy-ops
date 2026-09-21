# GitHub Actions runner hardening addendum

This addendum records the security profiles introduced after the original
self-hosted runner rollout. Twelve private repositories now run on isolated
`*-ci` ARC scale sets, and their superseded privileged scale sets have been
removed. Three parallel rootless BuildKit pools are installed and Ready for the
image-building repositories. Their workflow PRs remain open, and the original
Docker in Docker pools remain in service pending publication approval.

## Security model

Each scale set remains bound to one GitHub repository. Jobs receive application
credentials from GitHub at runtime; runner images and Kubernetes manifests do
not contain them. The runner pods do not mount a service-account token, a host
path, a Docker socket, Talos credentials, or the administrative `heavy-ops`
service account.

The ordinary runner profile uses pod user namespaces (`hostUsers: false`), pod
`RuntimeDefault` seccomp, and `fsGroup: 1001`. Its runner container is
non-root UID/GID 1001, is not privileged, cannot gain privileges, and drops all
Linux capabilities. Work is a disposable `emptyDir` capped at 20 GiB. The
runner requests 0.5 CPU, 1 GiB memory, and 2 GiB ephemeral storage; its limits
are 4 CPU, 4 GiB memory, and 10 GiB ephemeral storage. Deno-kit and MK/JM allow
three concurrent ephemeral runners; the other ten pools allow one. All twelve
scale to zero when idle.

The deployed pools and their current contracts are:

| Profile | Labels | Capacity | Runner image |
| --- | --- | --- | --- |
| Plain | `deno-kit-ci`, `site-fallback-worker-ci`, `email-guard-worker-ci`, `image-resize-worker-ci`, `b7-leather-ci` | Deno-kit 0–3; others 0–1 | `ghcr.io/home-operations/actions-runner:2.337.0@sha256:8b8e8326b5a08e658a0a41cfd2867afab69ca4194a152f986aa6fcd5430d09e7` |
| PostgreSQL | `anytimesteel-ci`, `cloudpeakinsulation-ci`, `connelybrothers-ci`, `connelyslandscaping-ci`, `mk-rentals-ci`, `mk-jm-ci` | MK/JM 0–3; others 0–1 | `ghcr.io/heavybullets8/business-runner:2.337.0@sha256:099bcb3a8228d3636feea706f36347b1244cc4368878de40ee3ecb06f9f17a98` |
| Nix | `nix-config-ci` | 0–1 | `ghcr.io/heavybullets8/business-nix-runner:2.337.0@sha256:03fcb7ce24edf6496e7493222cea81c719eb2bb72328635bf179240133a65327` |

All runner containers request 0.5 CPU, 1 GiB memory, and 2 GiB ephemeral
storage. Their limits are 4 CPU, 4 GiB memory, and 10 GiB ephemeral storage.
Each receives a fresh 20 GiB capped work `emptyDir`. Database sidecars request
0.1 CPU and 256 MiB memory, with limits of 2 CPU and 3 GiB memory. Their 2 GiB
data and 256 MiB shared-memory volumes are memory-backed and disposable.

Five container-free pools use the digest-pinned home-operations runner image.
Nix uses the digest-pinned `business-nix-runner`, with Nix 2.35.2 installed in
single-user mode during image construction. The image contract and a full
flake check passed without runtime `sudo` or a Docker daemon.

The six database pools use the digest-pinned `business-runner` image, which
contains PostgreSQL 17.11 client tools, AWS CLI 2.36.49, age 1.1.1, and Poppler
24.02. Their sidecar is
`postgres:17-alpine@sha256:f02121de6f74d30d8a94cd1d9584125e2178d7e6c377d8130112d4e52d867995`.
It runs as UID/GID 70 with the same non-privileged, no-escalation,
drop-all-capabilities policy. It listens only on pod loopback and stores
disposable data in a 2 GiB memory-backed `emptyDir`, with 256 MiB of
memory-backed shared memory. Each pool retains its application's established
database name, user, and port.

This fixed PostgreSQL sidecar and the baked backup tools replace the only
service/job containers used by these workflows. They preserve host-style jobs
without granting ARC's Kubernetes container hooks permission to create,
execute in, read logs from, or manage Secrets for workload pods. That is
material because the existing ARC namespace also contains GitHub App
credentials and the separate administrative runner. No testcontainers use was
found in the migrated repositories.

The reusable deno-kit interfaces remain backward compatible. Their
`postgres-sidecar` and `runner-backup-tools` inputs default to the prior GitHub
service/job-container behavior; only the proven private callers opt into the
new mode. This support landed in
[deno-kit PR #288](https://github.com/Heavybullets8/deno-kit/pull/288), whose
main run
[35554502041](https://github.com/Heavybullets8/deno-kit/actions/runs/35554502041)
passed 3,366 checks.

The pool definitions landed through
[heavy-ops PR #3165](https://github.com/Heavybullets8/heavy-ops/pull/3165) and
[PR #3166](https://github.com/Heavybullets8/heavy-ops/pull/3166). The two custom
runner images were built, tested, signed, and attested by
[containers PR #184](https://github.com/Heavybullets8/containers/pull/184),
release run
[35555053012](https://github.com/Heavybullets8/containers/actions/runs/35555053012).

## Completed workflow cutovers

Every row below was checked on its exact PR head and again through the noted
post-merge or final proof run. A fresh default-branch audit found only the new
`*-ci` label in all twelve repositories. The six database callers also set
`postgres-sidecar: true` on their database checks and
`runner-backup-tools: true` on standalone backups and migration safety backups.

| Repository | Change | Verification |
| --- | --- | --- |
| deno-kit | [PR #289](https://github.com/Heavybullets8/deno-kit/pull/289), main `53490ca8c6e5313a568cc48d074c4c44b5dcd7e2` | [run 35555026536](https://github.com/Heavybullets8/deno-kit/actions/runs/35555026536), success |
| site-fallback-worker | [PR #7](https://github.com/Heavybullets8/site-fallback-worker/pull/7), main `180d7222d22aafdf65672dcbd9687b71fe0a0a67` | [run 35555192153](https://github.com/Heavybullets8/site-fallback-worker/actions/runs/35555192153), tests and production deployment succeeded |
| email-guard-worker | [PR #11](https://github.com/Heavybullets8/email-guard-worker/pull/11), main `a47dd62e0c8188fba6618b443bc58e0da5e05ee1` | [run 35555419501](https://github.com/Heavybullets8/email-guard-worker/actions/runs/35555419501), both tests, D1 health check, and both deployments succeeded |
| b7-leather | [PR #22](https://github.com/Heavybullets8/b7-leather/pull/22), main `619f8aed924397aa559fe138d2b92d8048a1bdd8` | [run 35555113910](https://github.com/Heavybullets8/b7-leather/actions/runs/35555113910), success |
| image-resize-worker | [PR #4](https://github.com/Heavybullets8/image-resize-worker/pull/4), main `b3f8917c1e8f702ea211b8581c3bea52f15f43dc` | [check 35555627996](https://github.com/Heavybullets8/image-resize-worker/actions/runs/35555627996), [metadata deployment 35555627951](https://github.com/Heavybullets8/image-resize-worker/actions/runs/35555627951), and [resize deployment 35555628049](https://github.com/Heavybullets8/image-resize-worker/actions/runs/35555628049), all success |
| anytimesteel | [PR #89](https://github.com/Heavybullets8/anytimesteel/pull/89), main `5acf718d1884070746759ef908e870f12d5ebf26` | [run 35555952574](https://github.com/Heavybullets8/anytimesteel/actions/runs/35555952574), success; Deno build `d9njvr17xvnc` succeeded |
| cloudpeakinsulation | [PR #120](https://github.com/Heavybullets8/cloudpeakinsulation/pull/120), main `13bcb1b0ca5a795e5f2495c86e10b8fffa7cfea1` | [run 35555902879](https://github.com/Heavybullets8/cloudpeakinsulation/actions/runs/35555902879), success; Deno build `8kfgkxv8dyej` succeeded |
| connelybrothers | [PR #128](https://github.com/Heavybullets8/connelybrothers/pull/128), main `e11354779cf3718841ece4c7164e435fcd208aae` | [run 35555899285](https://github.com/Heavybullets8/connelybrothers/actions/runs/35555899285), success; Deno build `dtkwm874mqn2` succeeded |
| connelyslandscaping | [PR #84](https://github.com/Heavybullets8/connelyslandscaping/pull/84), main `124d8c2595da1fb1272eb465bdc2eabd4f5a8147` | [run 35555900562](https://github.com/Heavybullets8/connelyslandscaping/actions/runs/35555900562), success; Deno build `nph3ajtfp8gr` succeeded |
| mk_rentals | [PR #80](https://github.com/Heavybullets8/mk_rentals/pull/80), main `0d38fe7ff8a4497aa98c693fae4172539572337d` | [run 35555951760](https://github.com/Heavybullets8/mk_rentals/actions/runs/35555951760), success; Deno build `8kdza5kxqrt3` succeeded |
| mk-jm | [PR #166](https://github.com/Heavybullets8/mk-jm/pull/166), main `d2465aeff0d37b9974477a1c61faee6986f17a3d` | [run 35555999424](https://github.com/Heavybullets8/mk-jm/actions/runs/35555999424), both application lanes succeeded; Deno builds `3xfmehsr1y3t` and `zyxzrxcs8wey` succeeded |
| nix-config | [PR #329](https://github.com/Heavybullets8/nix-config/pull/329), main `0ec202042d053a22029387d8fa34fb1c1a2d1236` | [flake check 35556110794](https://github.com/Heavybullets8/nix-config/actions/runs/35556110794) and read-only [Renovate run 35555759534](https://github.com/Heavybullets8/nix-config/actions/runs/35555759534), success |

Before retirement, a fresh audit found no old label in any of the twelve
default branches. Every old ARC set reported zero current, pending, and running
runners, with no old runner pod or GitHub runner registration. Heavy-ops
[PR #3168](https://github.com/Heavybullets8/heavy-ops/pull/3168), merge
`06ec25cb12de50077a77fdab65dea29a087a00d9`, then removed those twelve
HelmReleases. Flux applied that exact revision and pruned their ARC sets,
listeners, and listener pods. It retained the three builder-dependent pools
and the separate administrative `heavy-ops-runner`.

## Backup-path proof

The host-tools backup path was tested with the exact published
`business-runner` digest. A disposable fixture created two PostgreSQL 17
databases, inserted two rows, ran `pg_dump | gzip` in the runner image as
UID/GID 1001 with all capabilities dropped and `no-new-privileges`, restored
the archive into the second database, and verified both rows. It also verified
PostgreSQL client 17.11, AWS CLI 2.36.49, and age 1.1.1. Cleanup left no fixture
container, network, or dump.

This proof used no production database, secret, or object store. A production
Cloud Peak backup dispatch was deliberately not used because it would export
production data and write the backup destination. The fixture proves the new
runner's dump/restore runtime while leaving the production schedule and
destination untouched.

## Talos capacity

The single control-plane node reached its former 150-pod ceiling while CPU and
memory remained available. [Heavy-ops PR #3167](https://github.com/Heavybullets8/heavy-ops/pull/3167)
raises kubelet `maxPods` to 200, within the existing `/24` pod CIDR. Talos 1.13.9
accepted the exact merge patch in explicit no-reboot mode. The node remained
`Ready`, and Kubernetes reported pod capacity and allocatable capacity of
200/200 afterward. After the twelve obsolete listener pods were pruned, the
final readback was 143 nonterminal cluster pods and 21 pods in
`actions-runner-system`; all 17 remaining runner-system HelmReleases were
Ready.

## Installed builder pools pending workflow cutover

The installed labels are `bighorn-byte-ci`, `scale-tv-ci`, and
`fcc-spam-reporter-ci`. FCC scales from zero to one runner, Scale TV from zero
to one, and Bighorn Byte keeps two ready with a maximum of three. Bighorn and
Scale also receive the same strict PostgreSQL sidecar profile, on their existing
ports 5440 and 5435 respectively. The runner remains UID/GID 1001 under
`RuntimeDefault`, drops all capabilities, and cannot gain privileges. It uses
the same pinned `business-runner` image as the six deployed database pools.

Image building uses one stock upstream RootlessKit/BuildKit daemon per job:

- `moby/buildkit:v0.33.0-rootless@sha256:80b15f0735e87bab7bf59ec4d695dfb4a7cfb25521cf56dc75d6f256285b63ef`
- native snapshotter with `--oci-worker-no-process-sandbox`
- non-root UID/GID 1000, with only `SETUID` and `SETGID` added
- `allowPrivilegeEscalation: true` and `Unconfined` seccomp only on the builder
- 0.5 CPU, 1 GiB memory, and 512 MiB ephemeral-storage requests; 4 CPU and
  2 GiB ephemeral-storage limits
- an 18 GiB memory limit with a fresh 12 GiB memory-backed state `emptyDir` for
  FCC and Bighorn; a private Unix socket `emptyDir` for every builder

These three pods explicitly use `hostUsers: true`: RootlessKit creates the
builder user namespace itself because nesting its stock mapping helpers inside
a Kubernetes pod user namespace could not establish the full ID range. The
builder is not privileged and receives no service-account token, Kubernetes
credential, host mount, device, TCP listener, or cross-job state. Its Unix
socket is mounted only into that job's runner and builder containers.

`--oci-worker-no-process-sandbox` means a build process can signal or trace the
BuildKit daemon inside their shared RootlessKit namespace. The daemon and build
have the same repository-job trust boundary and are deleted together. This is
the explicit builder exception; it is not a process-isolation boundary and does
not grant host-root authority.

The canonical probe used the exact daemon image and a UID/GID 1001 client. It
verified ordinary and high UIDs, `RUN`, `adduser`, `chown`, a non-root build
user, secret-mount non-persistence, and OCI export. Production state and socket
volumes are fresh for each job and disappear with its ephemeral runner pod.

The pools landed through heavy-ops
[PR #3169](https://github.com/Heavybullets8/heavy-ops/pull/3169), merge
`16b8c325885ad8915a82ab08e39758af50bf423d`. Follow-up
[PR #3170](https://github.com/Heavybullets8/heavy-ops/pull/3170), merge
`0b24cfb6b1b67d09e76b0591930c1ffcbe22843e`, preserved the literal Unix socket
path through Flux substitution. [PR #3171](https://github.com/Heavybullets8/heavy-ops/pull/3171),
merge `c70526fbb47c6116bb46bd4a7d0db6d527de3105`, moved the bounded native
snapshotter state into RAM. Flux applied the changes, and all three new
HelmReleases reported Ready. The cluster then had 20 Ready runner-system
HelmReleases: the controller, administrative pool, 15 target pools, and the 3
compatibility pools. The node remained Ready with pod capacity and allocatable
capacity of 200/200.

The open workflow PRs exercised the new labels without making them the default
branch configuration:

| Repository | Workflow PR | Validation |
| --- | --- | --- |
| Bighorn Byte | [PR #72](https://github.com/Heavybullets8/bighorn-byte/pull/72) | [check 35557413476](https://github.com/Heavybullets8/bighorn-byte/actions/runs/35557413476) passed unit, smoke, database, Poppler, and private-package paths; disk-backed [build 35557430131](https://github.com/Heavybullets8/bighorn-byte/actions/runs/35557430131) built all four images |
| Scale TV | [PR #53](https://github.com/Heavybullets8/scale-tv/pull/53) | [check 35557421757](https://github.com/Heavybullets8/scale-tv/actions/runs/35557421757) passed check, database, and smoke paths; disk-backed [build 35557440003](https://github.com/Heavybullets8/scale-tv/actions/runs/35557440003) passed |
| FCC spam reporter | [PR #49](https://github.com/Heavybullets8/fcc-spam-reporter/pull/49) | [build 35557244720](https://github.com/Heavybullets8/fcc-spam-reporter/actions/runs/35557244720) passed on the rootless pool |

These runs used `push: false`, so they proved real Dockerfile builds, GHA cache
access, and private build-secret use without publishing application images.
The final RAM-backed Bighorn
[build 35557699351](https://github.com/Heavybullets8/bighorn-byte/actions/runs/35557699351)
also built all four images successfully, and FCC's successful attempt ran after
the RAM-backed pool update. The first RAM-backed Scale build reached the
application build and then exhausted the 12 GiB state volume. Its isolated fix
raises only Scale's state volume to 24 GiB and builder memory limit to 30 GiB;
that change and its repeated build remain pending. The earlier disk-backed
Scale build remains the successful proof in the meantime.

Automatic approval review rejected application-image publication and also
rejected merging a workflow PR whose default-branch run would publish images.
It requires explicit user approval because those operations write external
artifacts and can trigger deployment reconciliation. Therefore the three
workflow PRs remain open, and `bighorn-byte-runner`, `scale-tv-runner`, and
`fcc-spam-reporter-runner` remain the active compatibility pools.

Before closing this section, record the successful final RAM-backed builds,
explicit publication approval, published image results, exact merged
default-branch labels, and removal of the three compatibility pools.
