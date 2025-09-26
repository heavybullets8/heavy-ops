# Minecraft Bedrock Server - Addon Management

This document explains how to manage addons/mods for the Minecraft Bedrock
server running in Kubernetes.

## Currently Installed Addons

**Loading Order (last loaded = highest priority):**

### Resource Packs

| Load Order | Addon Name              | Version | UUID                                   | Description                                           |
| ---------- | ----------------------- | ------- | -------------------------------------- | ----------------------------------------------------- |
| 1          | **Actions and Stuff**   | 1.1.13  | `2cf066eb-1254-4b7d-affb-80fe3216b18c` | Custom textures, animations, and visual improvements |
| 2          | **Dynamic Lightning**   | 3.4.0   | `f94c7e73-0928-4acf-904f-70920c796729` | Torch helmet lighting effects and visual enhancements |
| 3          | **Structure Generation** | 1.1.5   | `68ac942e-3470-4d14-a430-d12ceb49e93f` | Enhanced structure generation and world features     |
| 4          | **Cave Biomes**         | 1.0.7   | `67d777ab-847c-45ca-8ba8-91a9fd92171f` | New cave biome types and underground environments    |
| 5          | **Essentials**          | 1.0.24  | `24188c69-3fc5-47a7-b41b-23847c67adf5` | Core gameplay enhancements and utility features      |
| 6          | **Crops & Farms**       | 1.1.4   | `d916218f-5397-4435-b2e7-6f573cbd2cbf` | Enhanced farming, crops, and agricultural features   |
| 7          | **Villagers++**         | 1.0.12  | `364d3ae0-4b45-426a-9054-9441fa662903` | Advanced villager types, trading, and village systems |
| 8          | **Cave Dweller**        | 1.0.21  | `5ab34fff-ed52-4a92-be6d-0bcbe3a0d678` | Horror creature textures, sounds, and visual effects |
| 9          | **Backpacks Plus**      | 1.0.16  | `386318e6-9996-471e-ae9e-7fc0bb228521` | Backpack inventory expansion and storage system |

### Behavior Packs

| Load Order | Addon Name              | Version | UUID                                   | Description                                           |
| ---------- | ----------------------- | ------- | -------------------------------------- | ----------------------------------------------------- |
| 1          | **Dynamic Lightning**   | 3.4.0   | `657087d5-3a90-4ea6-b7dc-10ae07e31ce5` | Torch mechanics, offhand placement, and functionality |
| 2          | **Structure Generation** | 1.1.5   | `50ce70da-8091-4ef9-8c71-539c3d7d8654` | Custom structure spawning and world generation logic |
| 3          | **Cave Biomes**         | 1.0.7   | `72924636-47ee-43f0-a36b-03efa792756f` | Cave biome generation and underground mechanics      |
| 4          | **Essentials**          | 1.0.24  | `47a58c9a-1d18-4761-9323-35a01254ef67` | Core gameplay mechanics and utility functions        |
| 5          | **Crops & Farms**       | 1.1.4   | `d5de6bb3-8857-47a1-9375-b239c0f95ad3` | Enhanced farming mechanics and crop behaviors        |
| 6          | **Villagers++**         | 1.0.12  | `82b5aab3-53d9-41f5-a077-27649f6b3425` | Advanced villager AI, jobs, and interaction systems |
| 7          | **Cave Dweller**        | 1.0.21  | `efbee398-641d-4fd6-bf36-430d780c4f8f` | Cave dweller entity AI, spawning, and game mechanics |
| 8          | **Backpacks Plus**      | 1.0.16  | `41309d1b-ba75-4d67-b4cb-1514d285a29c` | Backpack functionality, inventory management |

## Server File Structure

```
/data/
├── behavior_packs/
│   ├── Dynamic-Lightning-Behavior/     # Torch functionality and mechanics
│   ├── Structure-Generation-Behavior/  # Custom structure generation
│   ├── Cave-Biomes-Behavior/          # Cave biome mechanics
│   ├── Essentials-Behavior/           # Core gameplay enhancements
│   ├── Crops-Farms-Behavior/          # Enhanced farming systems
│   ├── Villagers-Plus-Plus-Behavior/  # Advanced villager systems
│   ├── Cave-Dweller-Behavior/         # Cave dweller entity mechanics
│   ├── Backpacks-Plus-Behavior/       # Backpack functionality and inventory management
│   └── vanilla*/                      # Default Minecraft behavior packs
├── resource_packs/
│   ├── Actions-Stuff-Resource/        # Custom textures and animations
│   ├── Dynamic-Lightning-Resource/    # Torch visual effects
│   ├── Structure-Generation-Resource/ # Structure textures and models
│   ├── Cave-Biomes-Resource/          # Cave biome visuals
│   ├── Essentials-Resource/           # Core visual enhancements
│   ├── Crops-Farms-Resource/          # Farming textures and models
│   ├── Villagers-Plus-Plus-Resource/  # Advanced villager visuals
│   ├── Cave-Dweller-Resource/         # Cave dweller visuals and sounds
│   ├── Backpacks-Plus-Resource/       # Backpack textures, models, and UI elements
│   └── vanilla*/                      # Default Minecraft resource packs
├── worlds/
│   └── level/
│       ├── world_behavior_packs.json # Behavior pack configuration
│       └── world_resource_packs.json # Resource pack configuration
├── valid_known_packs.json            # Server pack validation
└── server.properties                 # Server configuration
```

## How to Add New Addons

### Prerequisites

- Access to the Kubernetes cluster with Flux installed
- Basic understanding of Minecraft addon structure

### Step 1: Copy Addon Files to Server

1. Extract your addon files (`.mcpack`, `.mcaddon`, or `.zip`)
2. Get current minecraft pod: `kubectl get pods -n game | grep minecraft`
3. Copy packs to server:
   ```bash
   # Copy resource pack
   kubectl cp extracted_pack game/minecraft-pod-name:/data/resource_packs/Your-Addon-Name

   # Copy behavior pack (if applicable)
   kubectl cp extracted_pack game/minecraft-pod-name:/data/behavior_packs/Your-Addon-Name
   ```

### Step 2: Update Configuration Files

Edit the configuration files in
`kubernetes/apps/game/minecraft/minecraft/config/`:

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

3. **valid_known_packs.json** - Add entries for each pack:
   ```json
   {
     "file_system": "RawPath",
     "from_locked_template": false,
     "from_world_template": false,
     "path": "resource_packs/Your-Addon-Name",
     "uuid": "your-pack-uuid",
     "version": "major.minor.patch"
   }
   ```

### Step 3: Deploy Changes

1. Commit and push your configuration changes to git
2. Flux will automatically reconcile and update the server
3. Server will restart with new pack configurations

## Pack Loading Priority

**IMPORTANT**: Pack loading order matters! Last loaded = highest priority.

- **Foundation packs** (Actions and Stuff, Essentials) load first
- **Environmental packs** (Dynamic Lightning, Structure Generation, Cave Biomes) load in middle
- **Content expansion packs** (Crops & Farms) load after foundation
- **Complex system packs** (Villagers++) load near the end
- **Override/horror packs** (Cave Dweller) load last for highest priority

When adding new addons, consider their dependencies and conflicts with existing packs.

## Configuration Files Explained

### world_resource_packs.json

Tells the world which resource packs to load and their versions.

### world_behavior_packs.json

Tells the world which behavior packs to load and their versions.

### valid_known_packs.json

Tells the server which packs are valid and where to find them. This prevents
"unknown pack" errors.

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
2. Remove entries from all configuration JSON files
3. Update this README to remove the addon from the lists
4. Restart the server

### Updating an Addon

1. Replace the pack folder with the new version
2. Update version numbers in configuration files
3. Update this README with new version information
4. Restart the server

### Cleanup

Always clean up temporary extraction files from the repository root to avoid
bloat.

## Troubleshooting

### Common Issues

- **"Unknown pack" errors**: Check `valid_known_packs.json` has correct UUIDs
  and paths
- **Pack not loading**: Verify UUIDs match between manifest.json and config
  files
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
kubectl exec -n game minecraft-pod-name -- cat /data/valid_known_packs.json
```

## Additional Resources

- [Minecraft Bedrock Addon Documentation](https://docs.microsoft.com/en-us/minecraft/creator/)
- [itzg/minecraft-bedrock Chart Documentation](https://github.com/itzg/minecraft-server-charts)
- [Minecraft Bedrock Server Setup Guide](https://github.com/itzg/docker-minecraft-bedrock-server)

---

_Last Updated: September 25, 2025 - Server Version: 1.21.102.1_
_Total Addons: 8 (9 behavior packs, 9 resource packs)_