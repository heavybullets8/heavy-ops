import { closeAdminDb } from "@/utils/admin/db.ts";
import { requirePermission } from "@/utils/outreach/access.ts";
import { systemActor } from "@/utils/outreach/system-actor.ts";
import {
  loadOutreachEnvironment,
  outreachSettings,
  saveOutreachSettings,
} from "@/utils/outreach/settings.ts";

const restoreAt = Date.parse("2026-09-20T00:00:00Z");
const expiresAt = Date.parse("2026-09-21T00:00:00Z");
const capKey = "OUTREACH_DAILY_LIMIT_CENTS";
const checkOnly = Deno.args.length === 1 && Deno.args[0] === "--check";
let phase = "startup";

async function readState() {
  phase = "load_settings_environment";
  const env = await loadOutreachEnvironment();
  phase = "owner_permissions";
  const actor = await systemActor({ env });
  requirePermission(actor, "outreach:settings");
  phase = "read_settings";
  const settings = await outreachSettings(actor);
  phase = "validate_cap";
  const field = settings.sections.flatMap((section) => section.fields)
    .find((field) => field.key === capKey);
  const cap = Number(field?.value);
  if (!Number.isSafeInteger(cap) || cap < 1) {
    throw new Error("Daily cap is not valid");
  }
  return { actor, version: settings.version, cap };
}

async function main() {
  if (Deno.args.length && !checkOnly) {
    throw new Error("Only --check is supported");
  }
  const initial = await readState();
  console.log(JSON.stringify({
    event: "preflight_ok",
    checkOnly,
    currentCapCents: initial.cap,
    restoreAt: new Date(restoreAt).toISOString(),
    expectedCapCents: 1000,
    restoredCapCents: 500,
  }));
  await closeAdminDb();
  if (checkOnly) return;
  while (Date.now() < restoreAt) {
    await new Promise((resolve) =>
      setTimeout(resolve, Math.min(60_000, restoreAt - Date.now()))
    );
  }
  for (let attempt = 0; attempt < 5; attempt++) {
    if (Date.now() >= expiresAt) {
      console.log(JSON.stringify({ event: "skipped_expired" }));
      return;
    }
    const current = await readState();
    if (current.cap !== 1000) {
      console.log(JSON.stringify({
        event: "skipped_changed_cap",
        currentCapCents: current.cap,
      }));
      return;
    }
    try {
      phase = "restore_cap";
      await saveOutreachSettings({
        section: "scouting",
        version: current.version,
        values: { [capKey]: "500" },
      }, current.actor);
      console.log(JSON.stringify({ event: "restored", capCents: 500 }));
      return;
    } catch (error) {
      if (
        !(error instanceof Error) || !("code" in error) ||
        error.code !== "stale_settings" || attempt === 4
      ) throw error;
      await closeAdminDb();
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }
}

try {
  await main();
} catch (error) {
  console.error(JSON.stringify({
    event: "restore_failed",
    phase,
    code: error instanceof Error && "code" in error
      ? String(error.code).slice(0, 80)
      : "validation_or_database_error",
  }));
  Deno.exitCode = 1;
} finally {
  await closeAdminDb();
}
