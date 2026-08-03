# Minecraft Bedrock Servers - Addon Management

This document covers addon management for both Minecraft Bedrock servers in
the `game` namespace:

- `minecraft`: the persistent, non-rotational FrenZone server
- `minecraft-rotational`: the seasonal server, currently running Bedrock
  Reimagined

The world pack lists are Git-managed ConfigMaps. Pack directories themselves
live on each server's PVC and must be replaced separately. Loading order is
listed from lowest to highest priority.

## Persistent Server Addons

### Resource Packs

| Order | Addon | Version | Header UUID |
| ----- | ----- | ------- | ----------- |
| 1 | Actions & Stuff | 1.1.39 | `2cf066eb-1254-4b7d-affb-80fe3216b18c` |
| 2 | Dynamic Lightning | 3.5.0 | `f94c7e73-0928-4acf-904f-70920c796729` |
| 3 | Structure Generation | 1.1.7 | `68ac942e-3470-4d14-a430-d12ceb49e93f` |
| 4 | Fire & Ice | 1.0.27 | `67d777ab-847c-45ca-8ba8-91a9fd92171f` |
| 5 | Essentials | 1.0.28 | `24188c69-3fc5-47a7-b41b-23847c67adf5` |
| 6 | Crops & Farms | 1.1.19 | `d916218f-5397-4435-b2e7-6f573cbd2cbf` |
| 7 | Villagers++ | 1.0.14 | `364d3ae0-4b45-426a-9054-9441fa662903` |
| 8 | AutoMiner | 1.0.2 | `368af99b-0257-4d18-86ba-056ddbaf52d1` |
| 9 | Cave Dweller | 1.0.25 | `5ab34fff-ed52-4a92-be6d-0bcbe3a0d678` |
| 10 | Backpacks++ | 1.0.23 | `386318e6-9996-471e-ae9e-7fc0bb228521` |

### Behavior Packs

| Order | Addon | Version | Header UUID |
| ----- | ----- | ------- | ----------- |
| 1 | Dynamic Lightning | 3.5.0 | `657087d5-3a90-4ea6-b7dc-10ae07e31ce5` |
| 2 | Structure Generation | 1.1.7 | `50ce70da-8091-4ef9-8c71-539c3d7d8654` |
| 3 | Fire & Ice | 1.0.27 | `72924636-47ee-43f0-a36b-03efa792756f` |
| 4 | Essentials | 1.0.28 | `47a58c9a-1d18-4761-9323-35a01254ef67` |
| 5 | Crops & Farms | 1.1.19 | `d5de6bb3-8857-47a1-9375-b239c0f95ad3` |
| 6 | Villagers++ | 1.0.14 | `82b5aab3-53d9-41f5-a077-27649f6b3425` |
| 7 | AutoMiner | 1.0.1 | `2e839411-4a0e-4cee-b106-33d5bde91193` |
| 8 | Cave Dweller | 1.0.25 | `efbee398-641d-4fd6-bf36-430d780c4f8f` |
| 9 | Backpacks++ | 1.0.23 | `41309d1b-ba75-4d67-b4cb-1514d285a29c` |

AutoMiner's behavior-pack header is `1.0.1`; its modules are `1.0.2`. The
world list must use the header version.

Structure Generation `1.1.7` requires a compatibility correction in
`scripts/pu/sg/items/structure_placer.js`: import only `world` from
`@minecraft/server` and use the literal `"IgnoreWaterlogging"` for the
`liquidSettings` option. The Bedrock `1.26.33.2` runtime does not expose the
pack's `LiquidSettings` import, which otherwise aborts its script at startup.

## Rotational Server Addons

### Resource Packs

| Order | Addon | Version | Header UUID |
| ----- | ----- | ------- | ----------- |
| 1 | Actions & Stuff | 1.1.39 | `2cf066eb-1254-4b7d-affb-80fe3216b18c` |
| 2 | Bedrock Reimagined addon resources | 1.0.3036 | `badcc305-8f0d-48bf-acea-9b3a903d06e0` |
| 3 | Create Bedrock | 1.0.1 | `1f819372-f7a9-4bdf-bf8b-ff2ae6c6ad15` |
| 4 | Gravestone | 1.0.6 | `33530fcd-9d09-b79e-ee8a-7d850cfd52ed` |

### Behavior Packs

| Order | Addon | Version | Header UUID |
| ----- | ----- | ------- | ----------- |
| 1 | Bedrock Reimagined | 1.0.3036 | `de800d74-c768-4926-9ec3-c8c3bb205eee` |
| 2 | Create Bedrock | 1.0.1 | `fcc16ff6-9255-406b-96ce-6af2c90311f3` |
| 3 | Gravestone | 1.0.6 | `d0fe9016-fb59-bb31-421a-fd4c01feac95` |
| 4 | FrenZone Player Fishing Perks | 1.0.0 | `4268c647-1b2b-453c-8b98-a8a651dfc4bc` |

The Bedrock Reimagined archive's marketing filename is `v1.0.95`; the world
pack lists intentionally use the internal manifest versions shown above. Its
standalone `Bedrock_Reimagined_RP.mcpack` (`ac3cfbf4-115d-41bc-9bdf-375eedb33540`)
is intentionally disabled for Actions & Stuff compatibility. The paired
`BR_RP.mcpack` remains required by the behavior pack.

### Player-specific fishing perk

`FrenZone Player Fishing Perks` is a companion behavior pack for Bedrock
Reimagined `1.0.3036`. It currently targets the exact Gamertag
`SpeedMcCheez`. Every confirmed fishing catch for that player is replaced from
a dedicated table containing only an enchanted book, enchanted bow, or
enchanted fishing rod. Fish, junk, and Bedrock Reimagined's surprise creature
catches are therefore disabled for that player. The table mirrors Bedrock
Reimagined's 6:5:5 relative weights, level-30 treasure enchantments, and
bow/rod damage ranges. Outside the overlapping-bobber edge case documented
below, fishing remains unchanged for every other player.

Bedrock does not always expose a fishing hook's projectile owner. The companion
therefore pairs a successful fishing-rod use with a mutually unique hook that
spawned in the same tick, dimension, and vicinity, then retains that ownership
for the catch. Catch attribution also requires the fishing item and its hook to
disappear in the same tick window and location. If simultaneous nearby events
remain indistinguishable, the companion refuses to guess ownership. Players
should separate bobbers for deterministic rewards.

The companion tags that player's fishing hooks. Before Minecraft starts, the
`patch-bedrock-reimagined` init container verifies the exact upstream
`imports.js` SHA-256, writes a minimally patched copy to an `emptyDir`, and
mounts only that file over the original in the server container. The patch
makes Bedrock Reimagined skip its creature roll when its stored hook owner is
`SpeedMcCheez`, with the companion's hook tag as a fallback, so no creature is
spawned. The PVC copy is never modified, making rollback a pod restart after
removing the overlay. An unexpected upstream checksum fails the init container
rather than applying an unsafe patch.

Bedrock Reimagined selects nearby hooks before it knows which player owns a
spawned catch item. To preserve the no-creature guarantee, a catch within its
1.5-block matching radius of a tagged `SpeedMcCheez` bobber also skips the
creature branch. This can suppress only that branch for another player's
simultaneous overlapping catch; their normal fishing item is not rerolled by
the companion.

The source is in
`minecraft-rotational/minecraft/addons/player-fishing-perks/` and is mounted
read-only from the `minecraft-rotational-player-fishing-pack` ConfigMap. Add
another exact Gamertag to `TARGET_PLAYER_NAMES` in `main.js` to grant the same
perk. Re-check `FISHING_OUTPUT_IDS`, the guarded patch checksums, and the
Bedrock Reimagined manifest dependency whenever that addon is upgraded.
Script API content output is enabled in the server console. A successful test
logs the target hook binding and the replacement item; an unresolved owner or
runtime/content error is visible through the normal pod logs.

## Server File Structure

```
/data/
├── behavior_packs/                    # Shared behavior-pack directories
├── resource_packs/                    # Shared resource-pack directories
├── worlds/
│   └── level/
│       ├── world_behavior_packs.json  # ConfigMap mount
│       └── world_resource_packs.json  # ConfigMap mount
└── server.properties
```

The persistent PVC is mounted at `/data` in `minecraft`; the rotational PVC is
mounted at `/data` in `minecraft-rotational`. The addon file browser exposes
them as `/games/minecraft` and `/games/minecraft-rotational`, respectively.
The Git-managed player fishing pack is a read-only ConfigMap mount nested under
the rotational server's `behavior_packs` directory rather than a PVC copy. The
single-file Bedrock Reimagined runtime overlay is generated in an `emptyDir`;
the third-party pack stored on the PVC remains unchanged.

## How to Add New Addons

### Prerequisites

- Access to the Kubernetes cluster with Flux installed
- Basic understanding of Minecraft addon structure

### Step 1: Copy Addon Files to Server

1. Extract your addon files (`.mcpack`, `.mcaddon`, or `.zip`)
2. Get the current target pod:
   `kubectl get pods -n game -l app.kubernetes.io/name=minecraft`
3. Copy packs to server:
   ```bash
   # Copy resource pack
   kubectl cp extracted_pack game/minecraft-pod-name:/data/resource_packs/Your-Addon-Name

   # Copy behavior pack (if applicable)
   kubectl cp extracted_pack game/minecraft-pod-name:/data/behavior_packs/Your-Addon-Name
   ```

### Step 2: Update Configuration Files

Edit the configuration files in
`kubernetes/apps/game/minecraft/minecraft/addons/` for the persistent server,
or `kubernetes/apps/game/minecraft-rotational/minecraft/addons/` for the
rotational server:

1. **world_resource_packs.json** - Add your resource pack:
   ```json
   {
       "pack_id": "your-pack-uuid-from-manifest",
       "version": [major, minor, patch]
   }
   ```

2. **world_behavior_packs.json** - Add your behavior pack (if applicable):
   ```json
   {
       "pack_id": "your-pack-uuid-from-manifest",
       "version": [major, minor, patch]
   }
   ```

### Step 3: Deploy Changes

1. Commit and push your configuration changes to git
2. Flux will automatically reconcile and update the server
3. Server will restart with new pack configurations

## Pack Loading Priority

**IMPORTANT**: Pack loading order matters! Last loaded = highest priority.

- **Foundation packs** (Actions and Stuff, Essentials) load first
- **Environmental packs** (Dynamic Lightning, Structure Generation, Fire & Ice)
  load in middle
- **Content expansion packs** (Crops & Farms) load after foundation
- **Complex system packs** (Villagers++, AutoMiner) load near the end
- **Override/horror packs** (Cave Dweller) load last for highest priority

When adding new addons, consider their dependencies and conflicts with existing
packs.

## Configuration Files Explained

### world_resource_packs.json

Tells the world which resource packs to load and their versions.

### world_behavior_packs.json

Tells the world which behavior packs to load and their versions.

### server.properties

- `texturepack-required=true` forces clients to download resource packs

## Player Experience

When players join the server with addons installed:

1. **Download Prompt**: Players see "Download & Join" if resource packs are
   required
2. **Automatic Installation**: Packs download and install automatically
3. **Game Features**: All addon features become available immediately

## Maintenance

### Removing an Addon

1. Delete the pack folder from the server
2. Remove entries from world_resource_packs.json and world_behavior_packs.json
3. Update this README to remove the addon from the lists
4. Restart the server

### Updating an Addon

1. Confirm every resource/behavior dependency declared by the new manifests is
   present at the exact required version
2. Stop the target server and replace its pack directories
3. Update the world pack lists and this README
4. Commit and push the Git changes, allow Flux to reconcile, then restart the
   server

### Resetting the Rotational Server

1. Verify the `minecraft-rotational-local` and
   `minecraft-rotational-remote` VolSync backups succeeded
2. Stop `minecraft-rotational`
3. Clear the worlds and custom pack directories on the existing
   `minecraft-rotational` PVC
4. Install only the new rotation's packs and update both rotational world pack
   lists
5. Start the server and verify a new world was generated with every declared
   pack loaded

Do not delete and recreate the rotational PVC for a reset. Its VolSync
`dataSourceRef` can restore the previous rotation into a new claim.

### Cleanup

Always clean up temporary extraction files from the repository root to avoid
bloat.

## Troubleshooting

### Common Issues

- **Pack not loading**: Verify UUIDs match between manifest.json and world
  config files
- **Version mismatches**: Ensure version arrays match exactly
  `[major, minor, patch]`
- **Missing dependencies**: Some packs require others - check manifest.json
  dependencies
- **Pack conflicts**: Check loading order - higher priority packs may override
  lower priority ones

### Debugging Commands

```bash
# Check server logs
kubectl logs -n game minecraft-pod-name

# Check pack files exist
kubectl exec -n game minecraft-pod-name -- ls -la /data/resource_packs/
kubectl exec -n game minecraft-pod-name -- ls -la /data/behavior_packs/

# Verify configuration files
kubectl exec -n game minecraft-pod-name -- cat /data/worlds/level/world_*.json
```

## Additional Resources

- [Minecraft Creator Documentation](https://learn.microsoft.com/minecraft/creator/)
- [itzg/minecraft-bedrock Chart Documentation](https://github.com/itzg/minecraft-server-charts)
- [Minecraft Bedrock Server Setup Guide](https://github.com/itzg/docker-minecraft-bedrock-server)

---

_Last Updated: August 2, 2026 - Server Version: 1.26.36.1_
