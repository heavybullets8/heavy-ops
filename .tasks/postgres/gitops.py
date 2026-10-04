import json
from pathlib import Path

from common import image_ref, output, require, run, wait_for, yaml_edit, yaml_read
from validate import image as deployment_image


ROOTS = {"home": "kubernetes/apps", "cloud": "kubernetes/cloud/apps"}


def files(state):
    result = []
    for root in ROOTS.values():
        result += [root + "/database/patroni/ks.yaml", root + "/database/patroni/app/helmrelease.yaml"]
        if state["kind"] == "major":
            result += [root + "/" + app["path"] + "/ks.yaml" for app in state["config"]["apps"]]
    return result


def change(worktree, state, held):
    repository, tag, checksum = image_ref(state["target_image"])
    for root in ROOTS.values():
        directory = worktree / root / "database/patroni"
        yaml_edit(directory / "ks.yaml", ".spec.suspend", held)
        expression = ".spec.values.controllers.patroni.containers.db.image"
        yaml_edit(directory / "app/helmrelease.yaml", expression + ".repository", repository)
        yaml_edit(directory / "app/helmrelease.yaml", expression + ".tag", tag + "@" + checksum)
        if state["kind"] == "major":
            for app in state["config"]["apps"]:
                path = worktree / root / app["path"] / "ks.yaml"
                require(yaml_read(path)["metadata"]["name"] == app["release"], "Expected one application Kustomization per file.")
                yaml_edit(path, ".spec.suspend", held)


def merge_phase(store, state, phase):
    root = Path(state["config"]["repository"])
    repository = state["config"]["github_repository"]
    held = phase == "stage"
    key = phase + "_pr"
    branch = "ops/postgres-" + state["id"].lower() + "-" + phase
    worktree = store.path / branch.replace("/", "-")
    if key not in state:
        run(["git", "fetch", "origin", "main"], cwd=root)
        if not worktree.exists():
            run(["git", "worktree", "add", "-b", branch, worktree, "origin/main"], cwd=root)
        require(output(["git", "branch", "--show-current"], cwd=worktree) == branch, "Unexpected maintenance branch.")
        change(worktree, state, held)
        run(["git", "add", "--", *files(state)], cwd=worktree)
        if output(["git", "diff", "--cached", "--name-only"], cwd=worktree):
            run(["git", "diff", "--cached", "--check"], cwd=worktree)
            run(["git", "commit", "-m", f"chore(postgres): {phase} {state['target']['postgres']} upgrade"], cwd=worktree)
        run(["git", "push", "-u", "origin", branch], cwd=worktree)
        existing = json.loads(output(["gh", "pr", "list", "--repo", repository, "--head", branch,
                                      "--state", "all", "--json", "number,url,headRefOid"]))
        if not existing:
            body = store.path / (state["id"] + "-" + phase + ".md")
            body.write_text(
                f"## Summary\n\n```text\nBoth sites → PostgreSQL {state['target']['postgres']}\n"
                f"Flux reconciliation → {'held for maintenance' if held else 'resumed'}\n```\n\n"
                f"Image: `{state['target_image']}`.\n\n## Evidence\n\n"
                + ("- **Before:** both sites passed role, identity, replication, and image preflight checks.\n"
                   "  **After:** this staged image will be applied by `ops postgres` in a coordinated upgrade.\n"
                   if held else "- **Before:** maintenance held Flux reconciliation.\n"
                   "  **After:** both sites passed version and replication checks, and a new full backup completed.\n")
                + "\n## Merge Danger\n\n**Door:** two-way\n\n**Blast Radius:** database\n\n"
                + ("Merging holds reconciliation. Database conversion, when needed, is a separate maintenance step.\n"
                   if held else "Merging restores reconciliation for the verified database release.\n")
            )
            output(["gh", "pr", "create", "--repo", repository, "--head", branch, "--base", "main",
                    "--title", f"chore(postgres): {phase} upgrade to {state['target']['postgres']}",
                    "--body-file", body])
            existing = json.loads(output(["gh", "pr", "list", "--repo", repository, "--head", branch,
                                          "--state", "all", "--json", "number,url,headRefOid"]))
        require(len(existing) == 1, "Expected one maintenance pull request.")
        state[key] = existing[0]
        store.save(state["id"], state)
    pr = state[key]
    print(pr["url"], flush=True)
    current = json.loads(output(["gh", "pr", "view", str(pr["number"]), "--repo", repository,
                                 "--json", "state,headRefOid,mergeCommit,statusCheckRollup"]))
    require(current["headRefOid"] == pr["headRefOid"], "The maintenance pull request changed; review it before resuming.")
    require(current["state"] != "CLOSED", "The maintenance pull request was closed without merging.")
    if current["state"] != "MERGED":
        checks = run(["gh", "pr", "checks", str(pr["number"]), "--repo", repository,
                      "--watch", "--interval", "10"], timeout=1800, check=False)
        require(checks.returncode == 0 or "no checks reported" in (checks.stdout + checks.stderr).lower(),
                "Maintenance pull request checks have not passed. Resume after resolving the checks.")
        run(["gh", "pr", "merge", str(pr["number"]), "--repo", repository, "--squash",
             "--match-head-commit", pr["headRefOid"]], timeout=120)
    merged = json.loads(output(["gh", "pr", "view", str(pr["number"]), "--repo", repository,
                                "--json", "state,mergeCommit"]))
    require(merged["state"] == "MERGED", "Merge is awaiting repository approval; resume after it is approved.")
    state[phase + "_commit"] = merged["mergeCommit"]["oid"]
    store.save(state["id"], state)


def reconcile(clusters, state, held):
    root = Path(state["config"]["repository"])
    run(["git", "fetch", "origin", "main"], cwd=root)
    commit = state[("stage" if held else "finish") + "_commit"]
    for site, cluster in clusters.items():
        cluster.flux("reconcile", "source", "git", "flux-system", "-n", "flux-system")
        source = cluster.get("gitrepository", "flux-system", "flux-system")
        revision = source["status"]["artifact"]["revision"].rsplit(":", 1)[-1]
        require(run(["git", "merge-base", "--is-ancestor", commit, revision], cwd=root, check=False).returncode == 0,
                site + ": Flux has not fetched the maintenance commit.")
        for prefix in ROOTS.values():
            path = prefix + "/database/patroni/"
            deployed = output(["git", "show", revision + ":" + path + "app/helmrelease.yaml"], cwd=root)
            require(deployment_image(deployed)[0] == state["target_image"], "Git now requests another database image; review the concurrent change before resuming.")
            document = output(["git", "show", revision + ":" + path + "ks.yaml"], cwd=root)
            value = json.loads(output(["yq", "-o=json", ".spec.suspend // false"], input=document))
            require(value == held, "Git no longer requests the expected maintenance state.")
        cluster.flux("reconcile", "kustomization", cluster.config["root_kustomization"], "-n", "flux-system", timeout=900)
        wait_for(lambda: bool(cluster.get("kustomization", "patroni")["spec"].get("suspend")) == held,
                 site + " reconciliation hold", 300)
        if state["kind"] == "major":
            for app in state["config"]["apps"]:
                wait_for(lambda: bool(cluster.get("kustomization", app["release"], app["namespace"])["spec"].get("suspend")) == held,
                         site + " application reconciliation hold", 300)
        if not held:
            cluster.flux("reconcile", "kustomization", "patroni", "-n", "database", timeout=900)
