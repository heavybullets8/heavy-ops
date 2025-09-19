# Minecraft Bedrock Server - Addon Management

This document explains how to manage addons/mods for the Minecraft Bedrock
server running in Kubernetes.

## Currently Installed Addons

### Resource Packs

| Addon Name            | Version | UUID                                   | Description                                           |
| --------------------- | ------- | -------------------------------------- | ----------------------------------------------------- |
| **Dynamic Lightning** | 3.3.0   | `f94c7e73-0928-4acf-904f-70920c796729` | Torch helmet lighting effects and visual enhancements |
| **Actions and Stuff** | 1.5.1   | `2cf066eb-1254-4b7d-affb-80fe3216b18c` | Custom textures, animations, and visual improvements  |
| **Cave Dweller**      | 1.0.8   | `5ab34fff-ed52-4a92-be6d-0bcbe3a0d678` | Horror creature textures, sounds, and visual effects  |

### Behavior Packs

| Addon Name            | Version | UUID                                   | Description                                           |
| --------------------- | ------- | -------------------------------------- | ----------------------------------------------------- |
| **Dynamic Lightning** | 3.3.0   | `657087d5-3a90-4ea6-b7dc-10ae07e31ce5` | Torch mechanics, offhand placement, and functionality |
| **Cave Dweller**      | 1.0.8   | `efbee398-641d-4fd6-bf36-430d780c4f8f` | Cave dweller entity AI, spawning, and game mechanics  |

## Server File Structure

```
/data/
├── behavior_packs/
│   ├── Dynamic_Lightning_V3.3.0/     # Torch functionality
│   ├── Cave-Dweller-Behavior/        # Cave dweller entity mechanics
│   └── vanilla*/                     # Default Minecraft behavior packs
├── resource_packs/
│   ├── Dynamic_Lightning_V3.3.0/     # Torch visual effects
│   ├── Actions-And-Stuff-1.5.1/      # Custom textures/animations
│   ├── Cave-Dweller-Resource/        # Cave dweller visuals/sounds
│   └── vanilla*/                     # Default Minecraft resource packs
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
3. Restart the server

### Updating an Addon

1. Replace the pack folder with the new version
2. Update version numbers in configuration files
3. Restart the server

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

_Last Updated: September 19, 2025 - Server Version: 1.21.102.1_

