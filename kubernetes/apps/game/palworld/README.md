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
`PalServer-Linux` exists. `UPDATE_ON_BOOT=true`, so restarts revalidate against
Steam and pick up patches.
