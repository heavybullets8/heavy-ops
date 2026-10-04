import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
import time

from cluster import Cluster, controller_hold, lsn, maintenance_values, ready, updated_values, validate_pair
from common import Refused, Store, change_kind, checkpoint, confirm, image_ref, new_id, output, require, wait_for
import gitops
import images
import jobs
from validate import image as deployment_image


def clusters(config):
    return {site: Cluster(site, config[site]) for site in ("home", "cloud")}


def pair(sites, primary="home", paused=False):
    snapshots = {site: cluster.snapshot() for site, cluster in sites.items()}
    validate_pair(snapshots, primary=primary, paused=paused)
    return snapshots


def configure(args, store):
    root = Path(__file__).resolve().parents[2]
    config = {"repository": str(root), "github_repository": "heavybullets8/heavy-ops", "timeout": args.timeout,
              "controller_ssh": args.controller_ssh, "controller_hold": args.controller_hold,
              "controller_state": args.controller_state,
              "apps": [{"namespace": "business", "release": "connelybrothers-web", "path": "business/connelybrothers"}]}
    if args.controller_identity:
        identity = Path(args.controller_identity).resolve()
        require(identity.is_file(), "Missing controller SSH identity file.")
        config["controller_identity"] = str(identity)
    if args.controller_known_hosts:
        known_hosts = Path(args.controller_known_hosts).resolve()
        require(known_hosts.is_file(), "Missing controller SSH known-hosts file.")
        config["controller_known_hosts"] = str(known_hosts)
    for site in ("home", "cloud"):
        value = getattr(args, site + "_kubeconfig")
        require(Path(value).is_file(), f"Missing {site} kubeconfig: {value}")
        config[site] = {"kubeconfig": str(Path(value).resolve()), "context": getattr(args, site + "_context"),
                        "root_kustomization": "cluster-apps" if site == "home" else "flux-system"}
    sites = clusters(config)
    snapshots = pair(sites)
    require(snapshots["home"]["cluster_uid"] != snapshots["cloud"]["cluster_uid"], "The two kubeconfigs point at the same cluster.")
    for site in sites:
        config[site]["cluster_uid"] = snapshots[site]["cluster_uid"]
    store.save("config", config)
    print("Saved PostgreSQL configuration to " + str(store.path / "config.json"))


def status(config):
    for site, cluster in clusters(config).items():
        snapshot = cluster.snapshot()
        role = "replica" if snapshot["recovery"] else "primary"
        print(f"Patroni {site}: PostgreSQL {snapshot['postgres']}, {role}, Patroni {snapshot['patroni']}")
        print("  Running: " + snapshot["image"])
        print("  Desired: " + snapshot["desired_image"])
    cnpg = clusters(config)["home"].get("cluster.postgresql.cnpg.io", "postgres16")
    print("CNPG: " + cnpg["spec"]["imageName"] + ", " + cnpg.get("status", {}).get("phase", "unknown"))


def updates(config):
    prs = json.loads(output(["gh", "pr", "list", "--repo", config["github_repository"], "--state", "open",
                             "--limit", "1000", "--json", "number,title,url,files,author"]))
    relevant = (".tasks/postgres/image/", "kubernetes/apps/database/cloudnative-pg/",
                "kubernetes/apps/database/patroni/", "kubernetes/cloud/apps/database/patroni/")
    for pr in prs:
        if any(file["path"].startswith(relevant) for file in pr["files"]):
            print(f"#{pr['number']} {pr['title']}\n  {pr['url']}")


def plan(config, store, image=None, pr_number=None):
    if pr_number is not None:
        require(image is None, "Choose either --image or --pr.")
        pr = json.loads(output(["gh", "pr", "view", str(pr_number), "--repo", config["github_repository"],
                                "--json", "headRefOid,baseRefName,state,url,files"]))
        require(pr["baseRefName"] == "main" and pr["state"] == "OPEN", "Choose an open update pull request targeting main.")
        targets = []
        paths = [root + "/database/patroni/app/helmrelease.yaml" for root in gitops.ROOTS.values()]
        require(any(item["path"] in paths for item in pr["files"]), "This PR does not update a deployed Patroni image. Merge a source dependency update and wait for the infrastructure image release first.")
        for path in paths:
            file = json.loads(output(["gh", "api", "repos/" + config["github_repository"] + "/contents/" + path + "?ref=" + pr["headRefOid"]]))
            targets.append(deployment_image(base64.b64decode(file["content"]).decode())[0])
        require(len(set(targets)) == 1, "The pull request must update home and cloud to the same image.")
        image = targets[0]
    sites = clusters(config)
    snapshots = pair(sites)
    for site, snapshot in snapshots.items():
        require(snapshot["cluster_uid"] == config[site]["cluster_uid"], f"{site}: the configured Kubernetes cluster changed.")
        require(ready(snapshot["release"]), f"{site}: database HelmRelease is not ready.")
        require(not sites[site].get("kustomization", "patroni")["spec"].get("suspend"), f"{site}: reconciliation is already suspended.")
    require(snapshots["home"]["image"] == snapshots["cloud"]["image"], "Both sites must start on the same image. Resume an existing upgrade if one is in progress.")
    if image is None:
        require(snapshots["home"]["desired_image"] == snapshots["cloud"]["desired_image"], "Home and cloud request different images.")
        image = snapshots["home"]["desired_image"]
    image_ref(image)
    require(image.startswith("ghcr.io/heavybullets8/postgres-patroni:"), "Select a database infrastructure release from heavy-ops.")
    require(image != snapshots["home"]["image"], "Both sites already run the requested image.")
    old = images.inspect(snapshots["home"]["image"])
    target = images.inspect(image)
    kind = change_kind(old, target)
    for snapshot in snapshots.values():
        require(snapshot["postgres"] == old["postgres"], "The running PostgreSQL version differs from its image.")
        if kind == "major":
            require(snapshot["free_bytes"] > snapshot["data_bytes"] * 2 + 512 * 1024**2,
                    "Allow at least twice the current PostgreSQL data size plus 512 MiB of free disk for a major upgrade.")
    state = {"id": new_id(), "created": time.time(), "config": config, "snapshots": snapshots,
             "old": old, "target": target, "target_image": image, "kind": kind, "completed": [], "active": None,
             "apps": {site: [cluster.app_snapshot(app) for app in config["apps"]] for site, cluster in sites.items()}}
    if pr_number is not None:
        state["source_pr"] = {"number": pr_number, "url": pr["url"], "head": pr["headRefOid"]}
    store.save(state["id"], state)
    print(f"{state['id']}: {kind} upgrade, PostgreSQL {old['postgres']} → {target['postgres']}; Patroni {old['patroni']} → {target['patroni']}")
    print("Target: " + image)
    if kind == "major":
        print("Run ops postgres rehearse " + state["id"] + " before upgrading. All application databases share this maintenance window.")
    else:
        print("Run ops postgres upgrade " + state["id"])
    return state


def identity(sites, state):
    for site, cluster in sites.items():
        cluster.assert_identity(state["snapshots"][site])


def rehearse(store, state):
    require(state["kind"] == "major", "A pg_upgrade rehearsal is only needed for a major version change.")
    require(not state["completed"], "Rehearsal must finish before starting the production upgrade.")
    sites = clusters(state["config"])
    identity(sites, state)
    pair(sites)
    print("Taking a full backup and restoring it to an isolated rehearsal volume.", flush=True)
    state["rehearsal_backup"] = sites["home"].backup(state["snapshots"]["home"]["stanza"], state["config"]["timeout"])
    store.save(state["id"], state)
    jobs.execute(sites["home"], store, state, "rehearse")
    print("Rehearsal passed for every application database. Production PostgreSQL was not changed.")


def switch(sites, primary, timeout):
    other = "cloud" if primary == "home" else "home"
    snapshots = {site: cluster.snapshot() for site, cluster in sites.items()}
    if not snapshots[primary]["recovery"]:
        validate_pair(snapshots, primary=primary)
        return
    validate_pair(snapshots, primary=other)
    sites[primary].catch_up(lsn(snapshots[other]["lsn"]), timeout)
    try:
        sites[other].request("/switchover", "POST", {"leader": other, "candidate": primary})
    except (Refused, subprocess.TimeoutExpired):
        pass
    def switched():
        try:
            pair(sites, primary)
            return True
        except Refused:
            return False
    wait_for(switched, primary + " to become primary", timeout)


def verify_target(cluster, state, recovery):
    current = None
    def connected():
        nonlocal current
        try:
            current = cluster.snapshot()
            return True
        except Refused:
            return False
    wait_for(connected, cluster.site + " PostgreSQL to accept connections", state["config"]["timeout"])
    require(current["image"] == state["target_image"] and current["postgres"] == state["target"]["postgres"] and
            current["patroni"] == state["target"]["patroni"] and current["recovery"] == recovery,
            cluster.site + ": the upgraded database does not match the requested version and role.")
    if state["kind"] == "major":
        require(current["system_id"] == state["upgrade_result"]["new_system_id"], "Unexpected PostgreSQL system identifier after the upgrade.")
    else:
        require(current["system_id"] == state["snapshots"][cluster.site]["system_id"], "PostgreSQL identity changed during a minor upgrade.")
    return current


def apply(store, state, approved=False):
    if "release_controller" in state["completed"]:
        print("This upgrade operation is already complete: " + state["id"])
        return
    config = state["config"]
    sites = clusters(config)
    identity(sites, state)
    for site, cluster in sites.items():
        pod = None
        def pod_exists():
            nonlocal pod
            try:
                pod = cluster.get("pod", "patroni-0")
                return True
            except Refused:
                return False
        wait_for(pod_exists, site + " database pod to be recreated", 120)
        image = next(container["image"] for container in pod["spec"]["containers"] if container["name"] == "db")
        require(image in (state["snapshots"][site]["image"], state["target_image"]),
                "Another operation changed the running database image. Do not resume this stale plan.")
    timeout = config["timeout"]
    if not state["completed"]:
        require(time.time() - state["created"] <= 86400, "The plan is older than 24 hours; create a fresh plan.")
        current = pair(sites)
        for site in sites:
            require(current[site]["image"] == state["snapshots"][site]["image"], "The database image changed after planning.")
            require(current[site]["system_id"] == state["snapshots"][site]["system_id"], "The database identity changed after planning.")
        if state["kind"] == "major":
            require(state.get("rehearse_result", {}).get("phase") == "complete", "A successful rehearsal is required before the major upgrade.")
        confirm(f"Upgrade both Patroni sites to PostgreSQL {state['target']['postgres']}? This creates and merges maintenance pull requests.",
                approved=approved, phrase="upgrade " + state["id"] if state["kind"] == "major" else None)
    step = lambda name, action: checkpoint(store, state, name, action)
    step("stage_git", lambda: gitops.merge_phase(store, state, "stage"))
    step("hold_flux", lambda: gitops.reconcile(sites, state, True))
    step("hold_controller", lambda: controller_hold(config, "acquire", state["id"]))
    if "release_controller" not in state["completed"]:
        controller_hold(config, "check", state["id"])
    step("verify_maintenance_start", lambda: pair(sites))
    def backup():
        state["backup"] = sites["home"].backup(state["snapshots"]["home"]["stanza"], timeout)
        store.save(state["id"], state)
    def roll(site):
        sites[site].set_release(updated_values(state["snapshots"][site]["release"]["spec"]["values"], state["target_image"]), timeout)
    if state["kind"] == "minor":
        step("backup", backup)
        step("upgrade_cloud", lambda: roll("cloud"))
        step("verify_cloud", lambda: verify_target(sites["cloud"], state, True))
        step("switch_to_cloud", lambda: switch(sites, "cloud", timeout))
        step("upgrade_home", lambda: roll("home"))
        step("verify_home", lambda: verify_target(sites["home"], state, True))
        step("switch_to_home", lambda: switch(sites, "home", timeout))
    else:
        def stop_apps():
            for site, cluster in sites.items():
                for app in state["apps"][site]:
                    cluster.app_scale(app, True, timeout)
            wait_for(lambda: all(snapshot["clients"] == 0 for snapshot in pair(sites).values()),
                     "all application clients to disconnect; include every application in the maintenance configuration", 60)
        step("stop_applications", stop_apps)
        step("backup", backup)
        step("pause_patroni", lambda: sites["home"].request("/config", "PATCH", {"pause": True}))
        def maintenance(site):
            sites[site].set_release(maintenance_values(state["snapshots"][site]["release"]["spec"]["values"]), timeout)
        step("stop_cloud_postgres", lambda: maintenance("cloud"))
        step("stop_home_postgres", lambda: maintenance("home"))
        step("convert_primary", lambda: jobs.execute(sites["home"], store, state, "upgrade"))
        step("retain_old_replica", lambda: jobs.execute(sites["cloud"], store, state, "quarantine"))
        step("refresh_patroni_identity", lambda: sites["home"].prepare_new_identity(state["snapshots"]["home"]))
        step("start_home", lambda: roll("home"))
        step("verify_home", lambda: verify_target(sites["home"], state, False))
        step("clone_cloud", lambda: roll("cloud"))
        step("verify_cloud", lambda: verify_target(sites["cloud"], state, True))
    def verify_pair():
        current = verify_target(sites["home"], state, False)
        sites["cloud"].catch_up(lsn(current["lsn"]), timeout)
        verify_target(sites["cloud"], state, True)
        pair(sites)
    step("verify_cluster", verify_pair)
    verify_pair()
    step("backup_upgraded_cluster", backup)
    step("finish_git", lambda: gitops.merge_phase(store, state, "finish"))
    step("resume_flux", lambda: gitops.reconcile(sites, state, False))
    def restore_apps():
        if state["kind"] == "major":
            for site, cluster in sites.items():
                for app in state["apps"][site]:
                    cluster.app_scale(app, False, timeout)
    step("resume_applications", restore_apps)
    step("release_controller", lambda: controller_hold(config, "release", state["id"]))
    print("Upgrade complete. Both sites run " + state["target_image"] + "; home is primary.")


def main():
    parser = argparse.ArgumentParser(prog="ops postgres", description="PostgreSQL versions stay in Git and Renovate; coordinate Patroni upgrades across home and cloud.")
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("configure", help="Save local kubeconfig and preferred-home controller settings")
    for site in ("home", "cloud"):
        setup.add_argument("--" + site + "-kubeconfig", required=True)
        setup.add_argument("--" + site + "-context")
    setup.add_argument("--controller-ssh", required=True)
    setup.add_argument("--controller-identity", help="Optional SSH identity file for the preferred-home controller")
    setup.add_argument("--controller-known-hosts", help="Optional SSH known-hosts file containing the verified controller host key")
    setup.add_argument("--controller-hold", default="/var/lib/ha-prod-controller/hold")
    setup.add_argument("--controller-state", default="/var/lib/ha-prod-controller/state.json")
    setup.add_argument("--timeout", type=int, default=3600)
    commands.add_parser("status", help="Show CNPG and Patroni running and desired versions")
    commands.add_parser("updates", help="List database update pull requests from the existing Renovate workflow")
    planning = commands.add_parser("plan", help="Inspect the requested image and save a checked upgrade plan")
    planning.add_argument("--image", help="Published tag@sha256 image; defaults to the desired HelmRelease image")
    planning.add_argument("--pr", type=int, help="Use the database image proposed by a Renovate pull request")
    rehearsal = commands.add_parser("rehearse", help="Restore a backup and test pg_upgrade on an isolated volume")
    rehearsal.add_argument("id")
    for name in ("upgrade", "resume"):
        applying = commands.add_parser(name, help="Execute or resume a saved upgrade plan")
        applying.add_argument("id", nargs="?" if name == "upgrade" else None)
        if name == "upgrade":
            applying.add_argument("--pr", type=int, help="Plan, rehearse if needed, and upgrade directly from a Renovate PR")
            applying.add_argument("--image", help="Plan and upgrade to a published infrastructure image")
        applying.add_argument("--yes", action="store_true", help="Approve a minor upgrade; major upgrades still require a typed confirmation")
    args = parser.parse_args()
    store = Store()
    with store.lock():
        if args.command == "configure":
            require(args.timeout >= 300, "Allow at least 300 seconds for database operations.")
            configure(args, store)
        elif args.command in ("status", "updates", "plan"):
            config = store.load("config")
            if args.command == "status":
                status(config)
            elif args.command == "updates":
                updates(config)
            else:
                plan(config, store, args.image, args.pr)
        else:
            if args.command == "upgrade" and args.id is None:
                state = plan(store.load("config"), store, args.image, args.pr)
                if state["kind"] == "major":
                    rehearse(store, state)
            else:
                if args.command == "upgrade":
                    require(args.pr is None and args.image is None, "Use a saved plan ID or a new target, not both.")
                state = store.load(args.id)
            if args.command == "rehearse":
                rehearse(store, state)
            else:
                apply(store, state, args.yes)


if __name__ == "__main__":
    try:
        main()
    except (Refused, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        print("An interrupted upgrade keeps its maintenance holds. Use ops postgres resume RUN_ID after resolving the problem.", file=sys.stderr)
        sys.exit(1)
