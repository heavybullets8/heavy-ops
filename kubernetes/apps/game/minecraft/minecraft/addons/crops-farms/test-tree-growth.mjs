import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// Exercise the actual addon class. Its proprietary source is supplied from the
// installed pack rather than copied into this repository.
const sourcePath = process.argv[2];
if (!sourcePath) {
  throw new Error("Usage: node test-tree-growth.mjs /path/to/sgs_farm_treemanager.js");
}
const source = readFileSync(sourcePath, "utf8")
  .replace(/^import .*;\r?\n/gm, "")
  .replace("export class treeManager", "class treeManager");

function run({ getBlock, hasStructureBlock = true }) {
  let placements = 0;
  let lookups = 0;
  const structure = {
    size: { x: 1, y: 2, z: 1 },
    getBlockPermutation: () => hasStructureBlock
      ? { getState: () => undefined }
      : undefined,
  };
  const treeManager = vm.runInNewContext(`${source}\n;treeManager;`, {
    mc: {
      world: {
        structureManager: {
          get: () => structure,
          place: () => placements++,
        },
      },
    },
  });
  const block = {
    location: { x: 0, y: 64, z: 0 },
    dimension: {
      getBlock(location) {
        lookups++;
        return getBlock(location);
      },
    },
  };
  const result = treeManager.placeStructureCentered("test:tree", block);
  return { result, placements, lookups };
}

assert.deepEqual(run({ getBlock: () => undefined }), {
  result: false, placements: 0, lookups: 1,
});
assert.deepEqual(run({ getBlock: () => ({ isAir: true }) }), {
  result: true, placements: 1, lookups: 1,
});
assert.deepEqual(run({ getBlock: () => ({ isAir: false }) }), {
  result: false, placements: 0, lookups: 1,
});
assert.deepEqual(run({
  getBlock: () => { throw new Error("Void structure cells must not be queried"); },
  hasStructureBlock: false,
}), { result: true, placements: 1, lookups: 0 });

const unexpected = new Error("Unexpected API failure");
assert.throws(() => run({ getBlock: () => { throw unexpected; } }),
  (error) => error === unexpected);
console.log("PASS: missing block defers growth; clear space grows; solid blocks prevent growth; void cells are skipped; unrelated errors remain visible");
