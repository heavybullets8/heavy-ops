import hashlib
import json
from pathlib import Path
import re

from cluster import NAMESPACE, PYTHON
from common import digest, require, wait_for


def manifest(state, site, operation):
    snapshot = state["snapshots"][site]
    identifier = state["id"].lower()
    name = "postgres-" + operation + "-" + identifier
    old_major = int(state["old"]["postgres"].split(".")[0])
    new_major = int(state["target"]["postgres"].split(".")[0])
    request = {"id": identifier, "operation": operation, "old_major": old_major,
               "new_major": new_major, "stanza": snapshot["stanza"], "old_system_id": snapshot["system_id"]}
    claim = name if operation == "rehearse" else "patroni"
    labels = {"app.kubernetes.io/name": "postgres-upgrade", "ops.home.arpa/run": identifier}
    mounts = [{"name": "data", "mountPath": "/ha-data"}, {"name": "old", "mountPath": "/old"},
              {"name": "script", "mountPath": "/upgrade", "readOnly": True},
              {"name": "backup", "mountPath": "/etc/pgbackrest", "readOnly": True},
              {"name": "tmp", "mountPath": "/tmp"}]
    old_image = snapshot["image"]
    copying = (f"set -eu; mkdir -p /old/usr/lib/postgresql /old/usr/share/postgresql; "
               f"cp -a /usr/lib/postgresql/{old_major} /old/usr/lib/postgresql/; "
               f"cp -a /usr/share/postgresql/{old_major} /old/usr/share/postgresql/; "
               "chown 999:999 /ha-data")
    initializers = [{"name": "old-binaries", "image": old_image, "command": ["/bin/bash", "-c", copying],
                     "securityContext": {"runAsUser": 0, "runAsNonRoot": False, "allowPrivilegeEscalation": False},
                     "volumeMounts": mounts}]
    if operation == "rehearse":
        initializers.append({"name": "restore", "image": old_image,
                             "command": ["/bin/bash", "-c",
                                 "set -eu; if [ ! -f /ha-data/.restore-complete ]; then "
                                 "pgbackrest --stanza=\"$1\" --pg1-path=/ha-data/postgres --type=immediate "
                                 "--target-action=promote --archive-mode=off --delta restore; "
                                 "touch /ha-data/.restore-complete; fi", "--", snapshot["stanza"]],
                             "securityContext": {"runAsUser": 999, "runAsGroup": 999, "runAsNonRoot": True},
                             "volumeMounts": mounts})
    pod = {"restartPolicy": "Never", "automountServiceAccountToken": False,
           "nodeSelector": {"kubernetes.io/hostname": snapshot["node_hostname"]},
           "securityContext": {"fsGroup": 999, "fsGroupChangePolicy": "OnRootMismatch", "seccompProfile": {"type": "RuntimeDefault"}},
           "imagePullSecrets": snapshot["pod"]["spec"].get("imagePullSecrets", []),
           "initContainers": initializers,
           "containers": [{"name": "upgrade", "image": state["target_image"],
                           "command": [PYTHON, "/upgrade/upgrade.py", json.dumps(request, sort_keys=True)],
                           "securityContext": {"runAsUser": 999, "runAsGroup": 999, "runAsNonRoot": True,
                                               "allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}},
                           "resources": {"requests": {"cpu": "250m", "memory": "256Mi"},
                                         "limits": {"cpu": "2", "memory": "2Gi"}},
                           "volumeMounts": mounts}],
           "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": claim}},
                       {"name": "old", "emptyDir": {}}, {"name": "tmp", "emptyDir": {}},
                       {"name": "script", "configMap": {"name": name}},
                       {"name": "backup", "secret": {"secretName": "patroni-backup-secret", "defaultMode": 0o440}}]}
    script = Path(__file__).with_name("upgrade.py").read_text()
    fingerprint = digest({"request": request, "script": script, "pod": pod})
    metadata = {"name": name, "namespace": NAMESPACE, "labels": labels,
                "annotations": {"ops.home.arpa/spec": fingerprint}}
    resources = [{"apiVersion": "v1", "kind": "ConfigMap", "metadata": metadata,
                  "immutable": True, "data": {"upgrade.py": script}}]
    if operation == "rehearse":
        size = snapshot["pvc"]["spec"]["resources"]["requests"]["storage"]
        match = re.fullmatch(r"([0-9]+)(Gi|Mi)", size)
        require(match is not None, "Rehearsal storage must use Gi or Mi quantities.")
        resources.append({"apiVersion": "v1", "kind": "PersistentVolumeClaim", "metadata": metadata,
                          "spec": {"accessModes": ["ReadWriteOnce"],
                                   "storageClassName": snapshot["pvc"]["spec"]["storageClassName"],
                                   "resources": {"requests": {"storage": str(int(match[1]) * 3) + match[2]}}}})
    job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": metadata,
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": state["config"]["timeout"],
                    "template": {"metadata": {"labels": labels}, "spec": pod}}}
    resources.append(job)
    return resources, request


def execute(cluster, store, state, operation):
    resources, request = manifest(state, cluster.site, operation)
    name = resources[-1]["metadata"]["name"]
    existing = cluster.kubectl("-n", NAMESPACE, "get", "job", name, "--ignore-not-found", "-o", "json").stdout
    if existing:
        job = json.loads(existing)
        require(job["metadata"]["annotations"].get("ops.home.arpa/spec") == resources[-1]["metadata"]["annotations"]["ops.home.arpa/spec"],
                "The upgrade Job differs from the saved plan.")
        if job.get("status", {}).get("failed"):
            cluster.kubectl("-n", NAMESPACE, "delete", "job", name, "--cascade=foreground", "--wait=true", "--timeout=120s")
    cluster.kubectl("apply", "-f", "-", input=json.dumps({"apiVersion": "v1", "kind": "List", "items": resources}))
    def finished():
        status = cluster.get("job", name).get("status", {})
        require(not status.get("failed"), f"Upgrade Job {NAMESPACE}/{name} failed. Inspect its logs, then resume; maintenance remains in place.")
        return bool(status.get("succeeded"))
    wait_for(finished, name, state["config"]["timeout"] + 30, 5)
    logs = cluster.kubectl("-n", NAMESPACE, "logs", "job/" + name, "-c", "upgrade").stdout
    result = json.loads(logs.strip().splitlines()[-1])
    require(result["phase"] == "complete" and result["signature"] == hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest(),
            "The upgrade Job did not return a valid completion record.")
    state[operation + "_result"] = result
    store.save(state["id"], state)
    return result
