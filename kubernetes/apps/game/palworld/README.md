# Palworld

| Platform         | Direct address | Community browser |
| ---------------- | -------------- | ----------------- |
| Steam            | yes            | yes               |
| Xbox / Game Pass | no             | yes               |
| PS5              | no             | yes               |

Steam: **Join Multiplayer Game** → address box → `static.${SECRET_DOMAIN}:8211`.

Console: **Join Multiplayer Game** → **Community Servers** → search `FrenZone`.

## Ports

| Proto | Port  | For                                  |
| ----- | ----- | ------------------------------------ |
| UDP   | 8211  | Gameplay                             |
| UDP   | 27015 | Query; community-list visibility     |

## Game settings

`DISABLE_GENERATE_SETTINGS=false`, so `PalWorldSettings.ini` is rewritten from
env vars every boot. Editing the file directly does not survive a restart — add
the env var to `helmrelease.yaml` instead (`DIFFICULTY`, `EXP_RATE`,
`DEATH_PENALTY`, …). Naming: INI key in caps, underscores between words, drop a
leading `b`.
[Full list](https://palworld-server-docker.loef.dev/getting-started/configuration/game-settings).

Crossplay is `CrossplayPlatforms=(Steam,Xbox,PS5,Mac)` (default).

`WORKER_THREADS_SERVER` is intentionally unset; the deprecated
`MULTITHREADING=true` would set it to the host's 64 CPUs.

Do not set `ALLOW_CONNECT_PLATFORM`. It is absent from the image's ini template
so it does nothing here, and the legacy Xbox-only mode it selected locks Steam
players out.

## Admin

RCON is off (deprecated upstream). Use `rest-cli`:

```bash
kubectl exec -n game deploy/palworld -- rest-cli info
kubectl exec -n game deploy/palworld -- rest-cli players
kubectl exec -n game deploy/palworld -- rest-cli announce "Restarting in 5"
kubectl exec -n game deploy/palworld -- rest-cli save
```

## Updates

Automatic, at 04:30-07:30 `${TIMEZONE}` — the same maintenance window tuppr
uses. supercronic compares the local Steam manifest against `api.steamcmd.net`.
On a new build it broadcasts a 10-minute warning (skipped instantly if the
server is empty), takes a backup, saves over the REST API, and shuts the server
down. The container exits 0, Kubernetes restarts it, and `UPDATE_ON_BOOT=true`
pulls the new build through SteamCMD.

Four hourly slots so a Steam API outage still gets retried the same night. They
sit on the half hour because `update.sh` runs `backup` inline, and a check at
05:00 would race `BACKUP_CRON_EXPRESSION` for the same second-resolution
archive name.

Tradeoff: a patch released mid-day is not picked up until the next morning, and
Steam clients that already auto-updated cannot join a stale server. To take it
immediately, delete the pod — `UPDATE_ON_BOOT` does the rest.

Auto-update needs `UPDATE_ON_BOOT` **and** `REST_API_ENABLED`. Upstream docs
still claim `RCON_ENABLED` is required — that is stale; `scripts/update.sh`
checks the REST API.

If the Steam API is unreachable the check reports failure and nothing restarts,
so a flaky API cannot bounce the server.

Pin the game version with `TARGET_MANIFEST_ID` if a patch ever needs skipping.

Container image bumps (`v2.7.x`) come through Renovate, separately from the
game build.

## Backups

- Container: 05:00 daily into `/palworld/backups`, pruned at 7 days.
- VolSync: 09:00 daily, whole 40Gi PVC, local + remote.

## Wiping

```bash
kubectl scale deploy/palworld -n game --replicas=0
# RWO PVC — mount it from a throwaway root pod, then:
#   rm -rf /palworld/Pal/Saved/SaveGames/0/<WorldGUID>
kubectl scale deploy/palworld -n game --replicas=1
```

## First boot

Startup probe allows ~30m. A fresh PVC downloads ~10G via SteamCMD before
`PalServer-Linux` exists. The same probe covers the post-update restart, where
only the delta is fetched.
