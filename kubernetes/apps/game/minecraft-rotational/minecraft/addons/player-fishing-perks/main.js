import {
  EntityComponentTypes,
  EquipmentSlot,
  Player,
  system,
  world,
} from "@minecraft/server";

/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").ItemStack} ItemStack */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */

/**
 * @typedef {object} HookState
 * @property {Entity} hook
 * @property {string | undefined} ownerId
 * @property {number} castTick
 * @property {boolean} caught
 * @property {string} dimensionId
 * @property {Vector3} spawnLocation
 * @property {Vector3} lastLocation
 * @property {number | undefined} removedTick
 * @property {number | undefined} catchTick
 * @property {Entity | undefined} caughtItem
 * @property {boolean} delivered
 * @property {boolean} hookTagged
 * @property {boolean | undefined} ownerIsTarget
 */

/**
 * @typedef {object} PendingFishingItem
 * @property {Entity} entity
 * @property {number} tick
 * @property {string} dimensionId
 * @property {Vector3} location
 * @property {boolean} claimed
 */

/**
 * @typedef {object} PendingFishingCast
 * @property {Player} player
 * @property {number} tick
 * @property {string} dimensionId
 * @property {Vector3} location
 * @property {boolean} confirmed
 */

/**
 * @typedef {object} CatchCandidate
 * @property {PendingFishingItem} item
 * @property {HookState} state
 * @property {number} distance
 * @property {boolean} reelEvidence
 */

/**
 * @typedef {object} FlowEdge
 * @property {number} to
 * @property {number} reverse
 * @property {number} capacity
 * @property {number} cost
 * @property {CatchCandidate | undefined} candidate
 */

// Match Bedrock Gamertags exactly. Add another name here to grant the same perk.
const TARGET_PLAYER_NAMES = new Set(["SpeedMcCheez"]);

const FISHING_HOOK_TYPE = "minecraft:fishing_hook";
const ITEM_ENTITY_TYPE = "minecraft:item";
const TREASURE_TABLE_PATH = "frenzone/player_fishing_treasure";
const NO_CREATURE_HOOK_TAG = "frenzone:no_creature_fishing";

// These values mirror Bedrock Reimagined 1.0.3036's fishing script so this
// pack identifies the same item entity as the player's successful catch.
const MINIMUM_CATCH_AGE_TICKS = 5;
const MAXIMUM_HOOK_AGE_TICKS = 5_400;
const MATCH_DISTANCE_SQUARED = 1.5 * 1.5;
const AMBIGUOUS_DISTANCE_DELTA = 0.01;
const HOOK_REMOVAL_WINDOW_TICKS = 1;
const REMOVED_HOOK_RETENTION_TICKS = 5;
const PENDING_ITEM_RETENTION_TICKS = 5;
const REEL_EVIDENCE_WINDOW_TICKS = 2;
const OWNER_BIND_DISTANCE_SQUARED = 8 * 8;
const GENERATED_ITEM_IGNORE_TICKS = 5;

const ALLOWED_TREASURE_IDS = new Set([
  "minecraft:enchanted_book",
  "minecraft:bow",
  "minecraft:fishing_rod",
]);

// Other treasure entries in Bedrock Reimagined 1.0.3036. These are included
// here so every possible fishing item can be identified as a catch source.
const OTHER_TREASURE_IDS = new Set([
  "minecraft:nautilus_shell",
  "minecraft:name_tag",
  "minecraft:saddle",
  "5fs_br:rune_of_tides",
  "minecraft:sponge",
  "5fs_br:iron_canteen_empty",
  "minecraft:tide_armor_trim_smithing_template",
  "minecraft:sniffer_egg",
  "minecraft:skeleton_skull",
  "5fs_br:tropical_fish_head",
  "5fs_br:cod_head",
  "5fs_br:pufferfish_head",
  "5fs_br:dolphin_head",
  "5fs_br:salmon_head",
  "5fs_br:skeleton_horse_head",
  "5fs_br:giant_shark_tooth",
  "5fs_br:cooked_shark_fin",
  "5fs_br:shark_fin_soup",
  "5fs_br:giant_shark_fin_soup",
  "5fs_br:ring_band",
  "5fs_br:sky_star_fragment",
  "5fs_br:cape_of_ocean_waves",
  "5fs_br:sea_witch_wand",
]);

// Only known fishing outputs are allowed to consume a tracked hook. This
// prevents an unrelated item dropped beside a bobber from claiming the cast.
// Alternate modern IDs are included for legacy IDs used by the live tables.
const FISHING_OUTPUT_IDS = new Set([
  ...ALLOWED_TREASURE_IDS,
  ...OTHER_TREASURE_IDS,
  "5fs_br:black_torch",
  "5fs_br:blue_torch",
  "5fs_br:bones",
  "5fs_br:brown_torch",
  "5fs_br:cyan_torch",
  "5fs_br:dead_kelp",
  "5fs_br:dead_seagrass",
  "5fs_br:dried_dead_kelp",
  "5fs_br:giant_shark_fin_soup",
  "5fs_br:goblin_bile",
  "5fs_br:gray_torch",
  "5fs_br:green_torch",
  "5fs_br:light_blue_torch",
  "5fs_br:light_gray_torch",
  "5fs_br:lime_torch",
  "5fs_br:magenta_flowered_lilypad",
  "5fs_br:magenta_torch",
  "5fs_br:moose_hide",
  "5fs_br:orange_torch",
  "5fs_br:pink_flowered_lilypad",
  "5fs_br:pink_torch",
  "5fs_br:purple_torch",
  "5fs_br:raw_shark_fin",
  "5fs_br:red_torch",
  "5fs_br:rope",
  "5fs_br:shark_hide",
  "5fs_br:shark_tooth",
  "5fs_br:waterskin_empty",
  "5fs_br:white_torch",
  "5fs_br:yellow_flowered_lilypad",
  "5fs_br:yellow_torch",
  "minecraft:bamboo",
  "minecraft:black_dye",
  "minecraft:bone",
  "minecraft:book",
  "minecraft:bowl",
  "minecraft:brown_dye",
  "minecraft:clownfish",
  "minecraft:cocoa_beans",
  "minecraft:cod",
  "minecraft:dried_kelp",
  "minecraft:dye",
  "minecraft:fish",
  "minecraft:glow_ink_sac",
  "minecraft:ink_sac",
  "minecraft:kelp",
  "minecraft:leather",
  "minecraft:leather_boots",
  "minecraft:lily_pad",
  "minecraft:oxidised_copper_golem_statue",
  "minecraft:oxidized_copper_golem_statue",
  "minecraft:potion",
  "minecraft:pufferfish",
  "minecraft:resin_clump",
  "minecraft:rotten_flesh",
  "minecraft:salmon",
  "minecraft:stick",
  "minecraft:string",
  "minecraft:tripwire_hook",
  "minecraft:tropical_fish",
  "minecraft:waterlily",
]);

/** @type {Map<string, HookState>} */
const trackedHooks = new Map();
/** @type {Map<string, PendingFishingItem>} */
const pendingFishingItems = new Map();
/** @type {Map<string, number>} */
const recentFishingRodUses = new Map();
/** @type {Map<string, PendingFishingCast>} */
const pendingFishingCasts = new Map();
/** @type {Set<number>} */
const scheduledOwnerBindingTicks = new Set();
/** @type {Map<string, number>} */
const ignoredGeneratedItems = new Map();
/** @type {Set<string>} */
const warnings = new Set();
let spawningGeneratedItem = false;

/**
 * @param {string} key
 * @param {string} message
 * @param {unknown} [error]
 */
function warnOnce(key, message, error) {
  if (warnings.has(key)) return;

  warnings.add(key);
  console.warn(
    "[FrenZone Fishing Perks] " + message,
    error instanceof Error ? error.stack : error ?? "",
  );
}

/**
 * @param {Vector3} first
 * @param {Vector3} second
 */
function distanceSquared(first, second) {
  const x = first.x - second.x;
  const y = first.y - second.y;
  const z = first.z - second.z;
  return x * x + y * y + z * z;
}

/**
 * @param {string} playerId
 * @returns {Player | undefined}
 */
function getPlayerById(playerId) {
  try {
    const entity = world.getEntity(playerId);
    if (entity instanceof Player && entity.isValid) return entity;
  } catch {
    // Fall back to the live player list below.
  }

  try {
    return world.getAllPlayers().find((player) =>
      player.id === playerId && player.isValid
    );
  } catch {
    return undefined;
  }
}

/**
 * @param {HookState} state
 * @returns {Vector3}
 */
function getHookLocation(state) {
  try {
    if (state.hook?.isValid) return state.hook.location;
  } catch {
    // Fall back to the last location recorded while the hook was valid.
  }

  return state.lastLocation;
}

/**
 * @param {Entity} hook
 * @returns {Player | undefined}
 */
function getHookOwner(hook) {
  try {
    const owner = hook.getComponent(EntityComponentTypes.Projectile)?.owner;
    if (!owner) return undefined;
    if (owner instanceof Player && owner.isValid) return owner;
    return getPlayerById(owner.id);
  } catch {
    return undefined;
  }
}

/**
 * @param {Entity} hook
 * @param {Player | undefined} owner
 * @returns {boolean}
 */
function tagTargetHook(hook, owner) {
  if (!owner || !TARGET_PLAYER_NAMES.has(owner.name)) return false;

  try {
    if (!hook.hasTag(NO_CREATURE_HOOK_TAG)) {
      hook.addTag(NO_CREATURE_HOOK_TAG);
    }
    return true;
  } catch (error) {
    warnOnce(
      "hook-tag-failed",
      "Could not disable creature catches on a target player's hook.",
      error,
    );
    return false;
  }
}

/**
 * @param {string} playerId
 */
function hasActiveHookForPlayer(playerId) {
  for (const state of trackedHooks.values()) {
    if (state.ownerId === playerId && state.removedTick === undefined) {
      return true;
    }
  }

  return false;
}

/**
 * @param {HookState} state
 * @param {Player} owner
 * @param {string} source
 */
function setHookOwner(state, owner, source) {
  const newlyResolved = state.ownerId !== owner.id;
  state.ownerId = owner.id;
  state.ownerIsTarget = TARGET_PLAYER_NAMES.has(owner.name);
  pendingFishingCasts.delete(owner.id);

  if (state.ownerIsTarget && !state.hookTagged) {
    state.hookTagged = tagTargetHook(state.hook, owner);
  } else if (!state.ownerIsTarget && state.hookTagged) {
    try {
      if (state.hook?.isValid && state.hook.hasTag(NO_CREATURE_HOOK_TAG)) {
        state.hook.removeTag(NO_CREATURE_HOOK_TAG);
      }
      state.hookTagged = false;
    } catch (error) {
      warnOnce(
        "hook-untag-failed",
        "Could not restore creature catches after correcting a hook owner.",
        error,
      );
    }
  }

  if (newlyResolved && state.ownerIsTarget) {
    console.log(
      "[FrenZone Fishing Perks] Bound target hook for " + owner.name +
        " using " + source + ".",
    );
  }
}

/**
 * Binds only mutually unique, successful rod uses and hook spawns from the
 * closed tick. This refuses ambiguous simultaneous casts instead of assigning
 * another player's hook to the target.
 *
 * @param {number} castTick
 */
function reconcilePendingCastOwners(castTick) {
  const casts = [...pendingFishingCasts.values()].filter((cast) =>
    cast.tick === castTick && cast.confirmed && cast.player?.isValid
  );
  const states = [...trackedHooks.values()].filter((state) =>
    state.castTick === castTick &&
    !state.ownerId &&
    state.removedTick === undefined &&
    state.hook?.isValid
  );

  /** @type {Map<HookState, PendingFishingCast[]>} */
  const castsByState = new Map();
  /** @type {Map<PendingFishingCast, HookState[]>} */
  const statesByCast = new Map();

  for (const state of states) {
    for (const cast of casts) {
      if (
        cast.dimensionId !== state.dimensionId ||
        distanceSquared(cast.location, state.spawnLocation) >
          OWNER_BIND_DISTANCE_SQUARED
      ) {
        continue;
      }

      const stateCasts = castsByState.get(state) ?? [];
      stateCasts.push(cast);
      castsByState.set(state, stateCasts);

      const castStates = statesByCast.get(cast) ?? [];
      castStates.push(state);
      statesByCast.set(cast, castStates);
    }
  }

  for (const [state, stateCasts] of castsByState) {
    if (stateCasts.length !== 1) continue;
    const cast = stateCasts[0];
    if (statesByCast.get(cast)?.length !== 1) continue;
    setHookOwner(state, cast.player, "confirmed rod cast");
  }
}

/**
 * Defers ownership until every rod use and hook spawn from this tick is known.
 * Eager binding can mistake a reel for a later player's cast in the same tick.
 *
 * @param {number} castTick
 */
function scheduleOwnerBinding(castTick) {
  if (scheduledOwnerBindingTicks.has(castTick)) return;
  scheduledOwnerBindingTicks.add(castTick);

  function finalizeOwnerBinding() {
    // system.run normally advances a tick; guard the boundary explicitly in
    // case this callback is scheduled while the current tick still has work.
    if (system.currentTick <= castTick) {
      system.run(finalizeOwnerBinding);
      return;
    }

    try {
      try {
        reconcilePendingCastOwners(castTick);
      } catch (error) {
        warnOnce(
          "owner-reconciliation-failed",
          "Could not reconcile fishing-hook ownership.",
          error,
        );
      }

      for (const [playerId, cast] of pendingFishingCasts) {
        if (cast.tick !== castTick) continue;
        if (
          cast.confirmed &&
          cast.player?.isValid &&
          TARGET_PLAYER_NAMES.has(cast.player.name)
        ) {
          console.warn(
            "[FrenZone Fishing Perks] Could not uniquely bind a rod use for " +
              cast.player.name + " to a newly spawned hook.",
          );
        }
        pendingFishingCasts.delete(playerId);
      }
    } finally {
      scheduledOwnerBindingTicks.delete(castTick);
    }
  }

  system.run(finalizeOwnerBinding);
}

/**
 * @param {Player} player
 */
function recordFishingRodUseBefore(player) {
  recentFishingRodUses.set(player.id, system.currentTick);
  if (hasActiveHookForPlayer(player.id)) {
    pendingFishingCasts.delete(player.id);
    return;
  }

  pendingFishingCasts.set(player.id, {
    player,
    tick: system.currentTick,
    dimensionId: player.dimension.id,
    location: { ...player.location },
    confirmed: false,
  });
  scheduleOwnerBinding(system.currentTick);
}

/**
 * @param {Player} player
 */
function recordFishingRodUseAfter(player) {
  recentFishingRodUses.set(player.id, system.currentTick);
  const cast = pendingFishingCasts.get(player.id);
  if (!cast) return;

  cast.confirmed = true;
  scheduleOwnerBinding(cast.tick);
}

/**
 * @param {Entity} hook
 */
function trackHook(hook) {
  if (!hook?.isValid || trackedHooks.has(hook.id)) return;
  const projectileOwner = getHookOwner(hook);
  /** @type {HookState} */
  const state = {
    hook,
    ownerId: undefined,
    castTick: system.currentTick,
    caught: false,
    dimensionId: hook.dimension.id,
    spawnLocation: { ...hook.location },
    lastLocation: { ...hook.location },
    removedTick: undefined,
    catchTick: undefined,
    caughtItem: undefined,
    delivered: false,
    hookTagged: false,
    ownerIsTarget: undefined,
  };
  trackedHooks.set(hook.id, state);

  if (projectileOwner) {
    setHookOwner(
      state,
      projectileOwner,
      "projectile owner",
    );
  } else {
    scheduleOwnerBinding(state.castTick);
  }
}

/**
 * @param {PendingFishingItem} item
 * @param {number} now
 */
function hasUnresolvedHookContender(item, now) {
  if (now - item.tick > HOOK_REMOVAL_WINDOW_TICKS) return false;

  for (const state of trackedHooks.values()) {
    if (
      state.caught ||
      state.removedTick !== undefined ||
      item.tick - state.castTick < MINIMUM_CATCH_AGE_TICKS ||
      state.dimensionId !== item.dimensionId
    ) {
      continue;
    }

    if (
      distanceSquared(item.location, getHookLocation(state)) <=
        MATCH_DISTANCE_SQUARED
    ) {
      return true;
    }
  }

  return false;
}

/**
 * Finds a maximum-cardinality, minimum-distance one-to-one assignment. The
 * residual graph lets a later match move an earlier one instead of stranding
 * a catch through greedy nearest-edge selection.
 *
 * @param {CatchCandidate[]} candidates
 * @param {CatchCandidate} [excludedCandidate]
 */
function findBestAssignment(candidates, excludedCandidate) {
  const items = [...new Set(candidates.map(({ item }) => item))];
  const states = [...new Set(candidates.map(({ state }) => state))];
  const source = 0;
  const firstItem = 1;
  const firstState = firstItem + items.length;
  const sink = firstState + states.length;
  const nodeCount = sink + 1;

  /** @type {FlowEdge[][]} */
  const graph = Array.from({ length: nodeCount }, () => []);
  /** @type {{ candidate: CatchCandidate, edge: FlowEdge }[]} */
  const candidateEdges = [];

  /**
   * @param {number} from
   * @param {number} to
   * @param {number} cost
   * @param {CatchCandidate} [candidate]
   */
  function addEdge(from, to, cost, candidate) {
    /** @type {FlowEdge} */
    const forward = {
      to,
      reverse: graph[to].length,
      capacity: 1,
      cost,
      candidate,
    };
    /** @type {FlowEdge} */
    const reverse = {
      to: from,
      reverse: graph[from].length,
      capacity: 0,
      cost: -cost,
      candidate: undefined,
    };
    graph[from].push(forward);
    graph[to].push(reverse);
    if (candidate) candidateEdges.push({ candidate, edge: forward });
  }

  const itemNodes = new Map(
    items.map((item, index) => [item, firstItem + index]),
  );
  const stateNodes = new Map(
    states.map((state, index) => [state, firstState + index]),
  );

  for (const item of items) {
    const itemNode = itemNodes.get(item);
    if (itemNode !== undefined) addEdge(source, itemNode, 0);
  }
  for (const state of states) {
    const stateNode = stateNodes.get(state);
    if (stateNode !== undefined) addEdge(stateNode, sink, 0);
  }
  for (const candidate of candidates) {
    if (candidate === excludedCandidate) continue;
    const itemNode = itemNodes.get(candidate.item);
    const stateNode = stateNodes.get(candidate.state);
    if (itemNode === undefined || stateNode === undefined) continue;
    addEdge(
      itemNode,
      stateNode,
      candidate.distance,
      candidate,
    );
  }

  let flow = 0;
  let cost = 0;
  while (true) {
    const distances = Array(nodeCount).fill(Number.POSITIVE_INFINITY);
    const previousNodes = Array(nodeCount).fill(-1);
    const previousEdges = Array(nodeCount).fill(-1);
    distances[source] = 0;

    for (let iteration = 0; iteration < nodeCount - 1; iteration++) {
      let changed = false;
      for (let from = 0; from < nodeCount; from++) {
        if (!Number.isFinite(distances[from])) continue;

        for (let edgeIndex = 0; edgeIndex < graph[from].length; edgeIndex++) {
          const edge = graph[from][edgeIndex];
          if (edge.capacity <= 0) continue;

          const nextDistance = distances[from] + edge.cost;
          if (nextDistance >= distances[edge.to] - Number.EPSILON) continue;

          distances[edge.to] = nextDistance;
          previousNodes[edge.to] = from;
          previousEdges[edge.to] = edgeIndex;
          changed = true;
        }
      }
      if (!changed) break;
    }

    if (previousNodes[sink] < 0) break;

    for (let node = sink; node !== source;) {
      const from = previousNodes[node];
      const edge = graph[from][previousEdges[node]];
      edge.capacity -= 1;
      graph[node][edge.reverse].capacity += 1;
      node = from;
    }
    flow += 1;
    cost += distances[sink];
  }

  return {
    flow,
    cost,
    selected: candidateEdges
      .filter(({ edge }) => edge.capacity === 0)
      .map(({ candidate }) => candidate),
  };
}

/**
 * @param {CatchCandidate[]} candidates
 * @returns {CatchCandidate[][]}
 */
function getCandidateComponents(candidates) {
  /** @type {Map<PendingFishingItem, CatchCandidate[]>} */
  const byItem = new Map();
  /** @type {Map<HookState, CatchCandidate[]>} */
  const byState = new Map();

  for (const candidate of candidates) {
    const itemCandidates = byItem.get(candidate.item) ?? [];
    itemCandidates.push(candidate);
    byItem.set(candidate.item, itemCandidates);

    const stateCandidates = byState.get(candidate.state) ?? [];
    stateCandidates.push(candidate);
    byState.set(candidate.state, stateCandidates);
  }

  const visited = new Set();
  /** @type {CatchCandidate[][]} */
  const components = [];
  for (const seed of candidates) {
    if (visited.has(seed)) continue;

    /** @type {CatchCandidate[]} */
    const component = [];
    const queue = [seed];
    while (queue.length > 0) {
      const candidate = queue.pop();
      if (!candidate || visited.has(candidate)) continue;

      visited.add(candidate);
      component.push(candidate);
      queue.push(
        ...(byItem.get(candidate.item) ?? []),
        ...(byState.get(candidate.state) ?? []),
      );
    }
    components.push(component);
  }

  return components;
}

/**
 * Correlates buffered fishing items with hooks that disappeared at catch
 * time. A fishing-rod use by the hook owner wins over distance, which keeps
 * simultaneous nearby fishers scoped correctly. Irreducibly equal mappings
 * are skipped rather than guessing another player's catch.
 */
function processPendingCatches() {
  const now = system.currentTick;
  /** @type {CatchCandidate[]} */
  const candidates = [];

  for (const item of pendingFishingItems.values()) {
    if (item.claimed || !item.entity?.isValid) continue;

    for (const state of trackedHooks.values()) {
      const removedTick = state.removedTick;
      if (
        state.caught ||
        removedTick === undefined ||
        item.tick - state.castTick < MINIMUM_CATCH_AGE_TICKS ||
        Math.abs(removedTick - item.tick) > HOOK_REMOVAL_WINDOW_TICKS ||
        state.dimensionId !== item.dimensionId
      ) {
        continue;
      }

      const distance = distanceSquared(item.location, getHookLocation(state));
      if (distance > MATCH_DISTANCE_SQUARED) continue;

      const ownerRodUseTick = state.ownerId
        ? recentFishingRodUses.get(state.ownerId)
        : undefined;
      candidates.push({
        item,
        state,
        distance,
        reelEvidence: ownerRodUseTick !== undefined &&
          Math.abs(ownerRodUseTick - item.tick) <=
            REEL_EVIDENCE_WINDOW_TICKS,
      });
    }
  }

  for (const component of getCandidateComponents(candidates)) {
    const candidateItems = [
      ...new Set(component.map(({ item }) => item)),
    ];
    if (candidateItems.some((item) => hasUnresolvedHookContender(item, now))) {
      continue;
    }

    // Rod-use evidence is corroborating but decisive when only one nearby
    // hook owner used a rod in the catch window.
    const evidencePreferred = component.filter((candidate) => {
      if (candidate.reelEvidence) return true;
      const itemHasEvidence = component.some((other) =>
        other.item === candidate.item && other.reelEvidence
      );
      const hookHasEvidence = component.some((other) =>
        other.state === candidate.state && other.reelEvidence
      );
      return !itemHasEvidence && !hookHasEvidence;
    });

    const itemDegrees = new Map();
    const hookDegrees = new Map();
    for (const candidate of evidencePreferred) {
      itemDegrees.set(
        candidate.item,
        (itemDegrees.get(candidate.item) ?? 0) + 1,
      );
      hookDegrees.set(
        candidate.state,
        (hookDegrees.get(candidate.state) ?? 0) + 1,
      );
    }
    const contested = [...itemDegrees.values(), ...hookDegrees.values()].some(
      (degree) => degree > 1,
    );
    const changedThisTick = evidencePreferred.some((candidate) =>
      candidate.item.tick === now || candidate.state.removedTick === now
    );
    if (contested && changedThisTick) continue;

    const best = findBestAssignment(evidencePreferred);
    const ambiguous = new Set();
    for (const candidate of best.selected) {
      const alternative = findBestAssignment(evidencePreferred, candidate);
      if (
        alternative.flow === best.flow &&
        alternative.cost <= best.cost + AMBIGUOUS_DISTANCE_DELTA
      ) {
        ambiguous.add(candidate);
      }
    }

    for (const candidate of best.selected) {
      if (
        ambiguous.has(candidate) ||
        candidate.item.claimed ||
        candidate.state.caught
      ) {
        continue;
      }

      const owner = resolveHookOwner(candidate.state);
      if (!owner) continue;

      candidate.item.claimed = true;
      candidate.state.caught = true;
      candidate.state.catchTick = candidate.item.tick;
      candidate.state.caughtItem = candidate.item.entity;
      pendingFishingItems.delete(candidate.item.entity.id);

      if (!TARGET_PLAYER_NAMES.has(owner.name)) continue;

      candidate.state.ownerId = owner.id;
      candidate.state.ownerIsTarget = true;
      resolveConfirmedCatch(candidate.state);
    }
  }
}

/**
 * @param {HookState} state
 * @returns {Player | undefined}
 */
function resolveHookOwner(state) {
  if (state.ownerId) {
    const storedOwner = getPlayerById(state.ownerId);
    if (storedOwner) return storedOwner;
  }

  const projectileOwner = getHookOwner(state.hook);
  if (projectileOwner) {
    setHookOwner(state, projectileOwner, "late projectile owner");
    return projectileOwner;
  }

  // Never guess an owner: strict player scoping is safer than granting the
  // perk when Bedrock exposes neither a stored nor a live projectile owner.
  return undefined;
}

/**
 * @param {Player} player
 * @returns {ItemStack | undefined}
 */
function getMainhandItem(player) {
  try {
    return player
      .getComponent(EntityComponentTypes.Equippable)
      ?.getEquipment(EquipmentSlot.Mainhand);
  } catch {
    return undefined;
  }
}

/**
 * @param {ItemStack | undefined} tool
 * @returns {ItemStack | undefined}
 */
function generateAllowedTreasure(tool) {
  try {
    const manager = world.getLootTableManager();
    const treasureTable = manager.getLootTable(TREASURE_TABLE_PATH);
    if (!treasureTable) {
      warnOnce(
        "missing-table",
        "Could not find loot table " + TREASURE_TABLE_PATH + ".",
      );
      return undefined;
    }

    const generated = manager.generateLootFromTable(treasureTable, tool) ?? [];
    const replacement = generated[0];
    if (replacement && ALLOWED_TREASURE_IDS.has(replacement.typeId)) {
      return replacement;
    }

    warnOnce(
      "invalid-loot",
      "The player fishing table returned no valid item.",
    );
  } catch (error) {
    warnOnce(
      "generation-failed",
      "Could not generate fishing treasure.",
      error,
    );
  }

  return undefined;
}

/**
 * @param {Vector3} location
 * @param {string} dimensionId
 */
function isAwayFromTrackedHooks(location, dimensionId) {
  const now = system.currentTick;

  for (const state of trackedHooks.values()) {
    if (
      state.dimensionId !== dimensionId ||
      (state.removedTick !== undefined &&
        now - state.removedTick > REMOVED_HOOK_RETENTION_TICKS)
    ) {
      continue;
    }

    if (
      distanceSquared(location, getHookLocation(state)) <=
        MATCH_DISTANCE_SQUARED
    ) {
      return false;
    }
  }

  return true;
}

/**
 * @param {Player} owner
 * @returns {Vector3}
 */
function getSafeDropLocation(owner) {
  const { x, y, z } = owner.location;
  const candidates = [
    { x, y: y + 0.5, z },
    { x: x + 2, y: y + 0.5, z },
    { x: x - 2, y: y + 0.5, z },
    { x, y: y + 0.5, z: z + 2 },
    { x, y: y + 0.5, z: z - 2 },
    { x, y: y + 2.5, z },
  ];

  return candidates.find((location) =>
    isAwayFromTrackedHooks(location, owner.dimension.id)
  ) ?? { x, y: y + 3.5, z };
}

/**
 * @param {Player} owner
 * @param {ItemStack} replacement
 * @returns {boolean}
 */
function deliverReplacement(owner, replacement) {
  const inventory = owner
    .getComponent(EntityComponentTypes.Inventory)
    ?.container;
  const overflow = inventory ? inventory.addItem(replacement) : replacement;
  if (!overflow) return true;

  spawningGeneratedItem = true;
  try {
    const rewardEntity = owner.dimension.spawnItem(
      overflow,
      getSafeDropLocation(owner),
    );
    ignoredGeneratedItems.set(
      rewardEntity.id,
      system.currentTick + GENERATED_ITEM_IGNORE_TICKS,
    );
  } finally {
    spawningGeneratedItem = false;
  }

  return true;
}

/**
 * @param {HookState} state
 */
function resolveConfirmedCatch(state) {
  if (state.delivered || !state.caughtItem?.isValid) return;

  try {
    const itemStack = state.caughtItem
      .getComponent(EntityComponentTypes.Item)
      ?.itemStack;
    if (!itemStack || !FISHING_OUTPUT_IDS.has(itemStack.typeId)) return;

    const owner = state.ownerId ? getPlayerById(state.ownerId) : undefined;
    if (
      !owner ||
      !TARGET_PLAYER_NAMES.has(owner.name)
    ) {
      return;
    }

    const replacement = generateAllowedTreasure(getMainhandItem(owner));
    if (!replacement) {
      // Fail closed: an excluded fish/junk catch must not reach the target
      // player even when the dedicated loot table cannot generate a reward.
      state.caughtItem.remove();
      state.delivered = true;
      return;
    }

    // Remove the original before delivery. This prevents a partial failure
    // from leaving both the excluded catch and its replacement in the world.
    state.caughtItem.remove();
    state.delivered = true;
    deliverReplacement(owner, replacement);
    console.log(
      "[FrenZone Fishing Perks] Replaced a fishing catch for " + owner.name +
        " with " + replacement.typeId + ".",
    );
  } catch (error) {
    warnOnce(
      "replacement-failed",
      "Could not replace a confirmed fishing catch.",
      error,
    );
  }
}

world.afterEvents.entitySpawn.subscribe(({ entity }) => {
  if (!entity?.isValid) return;

  if (entity.typeId === FISHING_HOOK_TYPE) {
    trackHook(entity);
    return;
  }

  if (entity.typeId !== ITEM_ENTITY_TYPE) return;
  if (
    spawningGeneratedItem ||
    ignoredGeneratedItems.has(entity.id)
  ) {
    return;
  }

  let itemStack;
  try {
    itemStack = entity.getComponent(EntityComponentTypes.Item)?.itemStack;
  } catch {
    return;
  }
  if (!itemStack || !FISHING_OUTPUT_IDS.has(itemStack.typeId)) return;

  pendingFishingItems.set(entity.id, {
    entity,
    tick: system.currentTick,
    dimensionId: entity.dimension.id,
    location: { ...entity.location },
    claimed: false,
  });
  processPendingCatches();
});

world.afterEvents.entityRemove.subscribe(({ removedEntityId, typeId }) => {
  if (typeId !== FISHING_HOOK_TYPE) return;

  const state = trackedHooks.get(removedEntityId);
  if (!state) return;

  state.removedTick = system.currentTick;
  processPendingCatches();
});

world.beforeEvents.entityRemove.subscribe(({ removedEntity }) => {
  if (removedEntity.typeId !== FISHING_HOOK_TYPE) return;

  const state = trackedHooks.get(removedEntity.id);
  if (!state) return;

  try {
    state.lastLocation = { ...removedEntity.location };
    const owner = getHookOwner(removedEntity);
    if (owner) {
      state.ownerId = owner.id;
      state.ownerIsTarget = TARGET_PLAYER_NAMES.has(owner.name);
      pendingFishingCasts.delete(owner.id);
    }
  } catch {
    // The after-remove handler can still use the last per-tick snapshot.
  }
});

world.beforeEvents.itemUse.subscribe(({ itemStack, source }) => {
  if (itemStack.typeId !== "minecraft:fishing_rod") return;
  recordFishingRodUseBefore(source);
});

world.afterEvents.itemUse.subscribe(({ itemStack, source }) => {
  if (itemStack.typeId !== "minecraft:fishing_rod") return;
  recordFishingRodUseAfter(source);
  processPendingCatches();
});

system.runInterval(() => {
  for (const state of trackedHooks.values()) {
    try {
      if (state.hook?.isValid) {
        state.lastLocation = { ...state.hook.location };
        const owner = getHookOwner(state.hook);
        if (owner) {
          setHookOwner(state, owner, "projectile owner refresh");
        }
      }
    } catch {
      // Cleanup below removes stale hook state even if location reads fail.
    }
  }

  processPendingCatches();

  const now = system.currentTick;
  for (const [itemId, item] of pendingFishingItems) {
    if (
      item.claimed ||
      !item.entity?.isValid ||
      now - item.tick > PENDING_ITEM_RETENTION_TICKS
    ) {
      pendingFishingItems.delete(itemId);
    }
  }
}, 1);

system.runInterval(() => {
  const now = system.currentTick;
  for (const [hookId, state] of trackedHooks) {
    if (
      now - state.castTick > MAXIMUM_HOOK_AGE_TICKS ||
      (state.removedTick !== undefined &&
        now - state.removedTick > REMOVED_HOOK_RETENTION_TICKS)
    ) {
      trackedHooks.delete(hookId);
    }
  }

  for (const [itemId, expiresAt] of ignoredGeneratedItems) {
    if (now > expiresAt) ignoredGeneratedItems.delete(itemId);
  }

  for (const [playerId, useTick] of recentFishingRodUses) {
    if (now - useTick > REEL_EVIDENCE_WINDOW_TICKS) {
      recentFishingRodUses.delete(playerId);
    }
  }
}, 20);

world.afterEvents.worldLoad.subscribe(() => {
  console.log(
    "[FrenZone Fishing Perks] Exclusive rewards enabled for " +
      [...TARGET_PLAYER_NAMES].join(", ") +
      ".",
  );
});
