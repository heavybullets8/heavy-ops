import copy
import json
import re
import shlex
import time

from common import Refused, require, run, wait_for


DATABASE = "patroni"
NAMESPACE = "database"
PYTHON = "/opt/patroni/bin/python"

REQUEST = """
import base64,json,os,sys,urllib.request
request=json.load(sys.stdin)
credentials=os.environ['PATRONI_RESTAPI_USERNAME']+':'+os.environ['PATRONI_RESTAPI_PASSWORD']
headers={'Authorization':'Basic '+base64.b64encode(credentials.encode()).decode(),'Content-Type':'application/json'}
body=None if request.get('body') is None else json.dumps(request['body']).encode()
req=urllib.request.Request('http://127.0.0.1:8008'+request['path'],data=body,headers=headers,method=request['method'])
with urllib.request.urlopen(req,timeout=60) as response:
    content=response.read().decode()
    print(json.dumps({'status':response.status,'body':content}))
"""

SNAPSHOT = """
import configparser,json,os,subprocess,urllib.request
import importlib.metadata
import patroni,psycopg2
with urllib.request.urlopen('http://127.0.0.1:8008/patroni',timeout=5) as r: status=json.load(r)
with urllib.request.urlopen('http://127.0.0.1:8008/cluster',timeout=5) as r: cluster=json.load(r)
with psycopg2.connect(dbname='postgres',user='postgres',host='/var/run/postgresql') as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('server_version_num')::int, pg_is_in_recovery(), (pg_control_system()).system_identifier::text, CASE WHEN pg_is_in_recovery() THEN pg_last_wal_replay_lsn() ELSE pg_current_wal_flush_lsn() END::text")
        number,recovery,system_id,lsn=cursor.fetchone()
        cursor.execute("SELECT count(*) FROM pg_tablespace WHERE oid NOT IN (1663,1664)")
        tablespaces=cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()")
        clients=cursor.fetchone()[0]
config=configparser.ConfigParser(interpolation=None)
config.read('/etc/pgbackrest/pgbackrest.conf')
stanzas=[s for s in config.sections() if s!='global' and not s.startswith('global:')]
assert len(stanzas)==1
disk=os.statvfs('/ha-data')
data=json.loads(open('/etc/patroni.yml').read())
print(json.dumps({'postgres':str(number//10000)+'.'+str(number%10000),'patroni':importlib.metadata.version('patroni'),
 'recovery':recovery,'system_id':system_id,'lsn':lsn,'timeline':status.get('timeline'),
 'dcs_last_seen':status.get('dcs_last_seen'),'state':status.get('state'),
 'members':cluster.get('members',[]),'paused':cluster.get('pause',False),'stanza':stanzas[0],
 'data_bytes':int(subprocess.check_output(['du','-sb','/ha-data/postgres'],text=True).split()[0]),
 'free_bytes':disk.f_bavail*disk.f_frsize,'tablespaces':tablespaces,'clients':clients,
 'scope':data['scope'],'dcs_prefix':data.get('namespace','/service/').rstrip('/')+'/'+data['scope']+'/',
 'data_dir':data['postgresql']['data_dir']}))
"""


def lsn(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9A-F]+/[0-9A-F]+", value) is not None,
            "PostgreSQL has not reported a valid WAL position.")
    high, low = value.split("/")
    return int(high, 16) * 2**32 + int(low, 16)


def ready(resource):
    generation = resource["metadata"]["generation"]
    return any(item["type"] == "Ready" and item["status"] == "True" and
               item.get("observedGeneration", resource.get("status", {}).get("observedGeneration")) == generation
               for item in resource.get("status", {}).get("conditions", []))


def validate_pair(snapshots, *, primary="home", paused=False):
    other = "cloud" if primary == "home" else "home"
    for site, snapshot in snapshots.items():
        require(snapshot["state"] == "running", f"{site}: PostgreSQL is not running.")
        require(bool(snapshot["recovery"]) == (site != primary), f"{site}: unexpected database role.")
        require(snapshot["data_dir"] == "/ha-data/postgres", f"{site}: unexpected data directory.")
        require(snapshot["tablespaces"] == 0, "Custom tablespaces need a dedicated upgrade procedure.")
        require(snapshot["paused"] == paused, f"{site}: unexpected Patroni pause state.")
        require(isinstance(snapshot["dcs_last_seen"], (int, float)) and
                -5 <= time.time() - snapshot["dcs_last_seen"] <= 30,
                f"{site}: Patroni's coordination state is stale.")
        names = {member["name"] for member in snapshot["members"]}
        require(names == {"home", "cloud"}, "Expected exactly the home and cloud Patroni members.")
    for field in ("system_id", "timeline", "scope", "dcs_prefix", "stanza"):
        require(snapshots["home"][field] == snapshots["cloud"][field], f"Sites disagree on {field}.")
    require(lsn(snapshots[primary]["lsn"]) - lsn(snapshots[other]["lsn"]) <= 1024 * 1024,
            "Replica lag exceeds 1 MiB.")


def updated_values(values, image):
    result = copy.deepcopy(values)
    controller = result["controllers"][DATABASE]
    repository, tag = image.split(":", 1)
    for name in ("db", "pgbackrest-scheduler", "wal-metrics"):
        controller["containers"][name]["image"] = {"repository": repository, "tag": tag, "pullPolicy": "IfNotPresent"}
    controller["initContainers"]["prepare-volumes"]["image"] = {
        "repository": repository, "tag": tag, "pullPolicy": "IfNotPresent",
    }
    return result


def maintenance_values(values):
    result = copy.deepcopy(values)
    for name in ("db", "pgbackrest-scheduler", "wal-metrics"):
        container = result["controllers"][DATABASE]["containers"][name]
        container["command"] = [PYTHON, "-c", "import time; time.sleep(2147483647)"]
        container["args"] = []
        container["probes"] = {name: {"enabled": False} for name in ("startup", "liveness", "readiness")}
    return result


class Cluster:
    def __init__(self, site, config):
        self.site = site
        self.config = config
        self.args = ["kubectl", "--kubeconfig", config["kubeconfig"]]
        if config.get("context"):
            self.args += ["--context", config["context"]]

    def kubectl(self, *args, input=None, timeout=120, check=True):
        return run(self.args + list(args), input=input, timeout=timeout, check=check)

    def get(self, kind, name, namespace=NAMESPACE):
        return json.loads(self.kubectl("-n", namespace, "get", kind, name, "-o", "json").stdout)

    def items(self, kind, namespace=NAMESPACE, selector=None):
        args = ["-n", namespace, "get", kind, "-o", "json"]
        if selector:
            args += ["-l", selector]
        return json.loads(self.kubectl(*args).stdout)["items"]

    def exec(self, argv, *, container="db", input=None, timeout=120):
        return self.kubectl("-n", NAMESPACE, "exec", "-i", DATABASE + "-0", "-c", container,
                            "--", *argv, input=input, timeout=timeout).stdout.strip()

    def request(self, path, method="GET", body=None):
        data = json.dumps({"path": path, "method": method, "body": body})
        result = json.loads(self.exec([PYTHON, "-c", REQUEST], input=data))
        try:
            return json.loads(result["body"])
        except json.JSONDecodeError:
            return result["body"]

    def snapshot(self):
        snapshot = json.loads(self.exec([PYTHON, "-c", SNAPSHOT]))
        snapshot["cluster_uid"] = self.get("namespace", "kube-system")["metadata"]["uid"]
        snapshot["pvc_uid"] = self.get("pvc", DATABASE)["metadata"]["uid"]
        snapshot["release"] = self.get("helmrelease", DATABASE)
        snapshot["pod"] = self.get("pod", DATABASE + "-0")
        snapshot["node_hostname"] = self.get("node", snapshot["pod"]["spec"]["nodeName"])["metadata"]["labels"]["kubernetes.io/hostname"]
        snapshot["pvc"] = self.get("pvc", DATABASE)
        image = snapshot["release"]["spec"]["values"]["controllers"][DATABASE]["containers"]["db"]["image"]
        snapshot["desired_image"] = image["repository"] + ":" + image["tag"]
        snapshot["image"] = next(c["image"] for c in snapshot["pod"]["spec"]["containers"] if c["name"] == "db")
        return snapshot

    def assert_identity(self, snapshot):
        require(self.get("namespace", "kube-system")["metadata"]["uid"] == snapshot["cluster_uid"],
                f"{self.site}: kubeconfig now points at a different cluster.")
        require(self.get("pvc", DATABASE)["metadata"]["uid"] == snapshot["pvc_uid"],
                f"{self.site}: database volume identity changed.")
        require(self.get("helmrelease", DATABASE)["metadata"]["uid"] == snapshot["release"]["metadata"]["uid"],
                f"{self.site}: database release identity changed.")

    def patch(self, kind, name, operations, namespace=NAMESPACE):
        current = self.get(kind, name, namespace)
        operations = [{"op": "test", "path": "/metadata/resourceVersion", "value": current["metadata"]["resourceVersion"]}] + operations
        self.kubectl("-n", namespace, "patch", kind, name, "--type=json", "-p", json.dumps(operations))

    def flux(self, *args, timeout=600):
        command = ["flux", "--kubeconfig", self.config["kubeconfig"]]
        if self.config.get("context"):
            command += ["--context", self.config["context"]]
        return run(command + list(args), timeout=timeout)

    def set_release(self, values, timeout):
        require(self.get("kustomization", DATABASE)["spec"].get("suspend") is True,
                f"{self.site}: the database Kustomization must be suspended in Git first.")
        self.patch("helmrelease", DATABASE, [
            {"op": "add", "path": "/spec/suspend", "value": True},
            {"op": "replace", "path": "/spec/values", "value": values},
        ])
        self.flux("resume", "helmrelease", DATABASE, "-n", NAMESPACE)
        self.flux("reconcile", "helmrelease", DATABASE, "-n", NAMESPACE,
                  f"--timeout={timeout}s", timeout=timeout + 30)
        self.roll(timeout)
        require(ready(self.get("helmrelease", DATABASE)), f"{self.site}: database HelmRelease is not ready.")

    def roll(self, timeout):
        controller = self.get("statefulset", DATABASE)
        revision = controller["status"]["updateRevision"]
        pods = self.items("pod", selector="app.kubernetes.io/name=" + DATABASE)
        pod = next((item for item in pods if item["metadata"]["name"] == DATABASE + "-0"), None)
        if pod and pod["metadata"]["labels"].get("controller-revision-hash") != revision:
            self.kubectl("-n", NAMESPACE, "delete", "pod", DATABASE + "-0", "--wait=true",
                         f"--timeout={timeout}s", timeout=timeout + 30)
        def updated():
            try:
                current = self.get("pod", DATABASE + "-0")
                return (current["metadata"]["labels"].get("controller-revision-hash") == revision and
                        any(c["type"] == "Ready" and c["status"] == "True"
                            for c in current.get("status", {}).get("conditions", [])))
            except Refused:
                return False
        wait_for(updated, self.site + " database pod to become ready", timeout)

    def catch_up(self, barrier, timeout):
        def caught_up():
            try:
                result = json.loads(self.exec([PYTHON, "-c", SNAPSHOT]))
                return result["recovery"] and result["lsn"] and lsn(result["lsn"]) >= barrier
            except Refused:
                return False
        wait_for(caught_up, self.site + " to replay the WAL barrier", timeout)

    def backup(self, stanza, timeout):
        require(re.fullmatch(r"[A-Za-z0-9_-]+", stanza) is not None, "Invalid backup stanza.")
        self.exec(["pgbackrest", "--stanza=" + stanza, "check"], timeout=timeout)
        self.exec(["pgbackrest", "--stanza=" + stanza, "--type=full", "backup"], timeout=timeout)
        info = json.loads(self.exec(["pgbackrest", "--stanza=" + stanza, "--output=json", "info"]))
        backups = [backup for entry in info for backup in entry.get("backup", [])
                   if backup.get("type") == "full" and not backup.get("error")]
        require(backups, "pgBackRest did not report a successful full backup.")
        latest = max(backups, key=lambda backup: backup["timestamp"]["stop"])
        require(time.time() - latest["timestamp"]["stop"] < 300, "The full backup is not fresh.")
        return {"label": latest["label"], "timestamp": latest["timestamp"]["stop"]}

    def etcd(self, *args, input=None):
        endpoint = "22379" if self.site == "home" else "32379"
        return self.exec(["/usr/local/bin/etcdctl", "--endpoints=http://127.0.0.1:" + endpoint, *args],
                         container="etcd", input=input)

    def coordination(self, prefix, key):
        import base64
        result = json.loads(self.etcd("get", prefix + key, "-w", "json"))
        values = result.get("kvs", [])
        require(len(values) <= 1, "Ambiguous coordination key.")
        return None if not values else base64.b64decode(values[0]["value"]).decode()

    def prepare_new_identity(self, snapshot):
        prefix = snapshot["dcs_prefix"]
        wait_for(lambda: self.coordination(prefix, "leader") is None, "the old Patroni leader lease to expire", 120)
        initialized = self.coordination(prefix, "initialize")
        require(initialized in (None, snapshot["system_id"]), "Another database has changed the Patroni system identifier.")
        configuration = json.loads(self.coordination(prefix, "config") or "null")
        require(isinstance(configuration, dict), "Missing Patroni dynamic configuration.")
        configuration.pop("pause", None)
        self.etcd("put", prefix + "config", input=json.dumps(configuration))
        if initialized is not None:
            self.etcd("del", prefix + "initialize")

    def app_snapshot(self, app):
        namespace, release = app["namespace"], app["release"]
        deployments = self.items("deployment", namespace, "app.kubernetes.io/instance=" + release)
        require(deployments, f"No deployments found for {namespace}/{release}.")
        return {"namespace": namespace, "release": release,
                "suspended": self.get("helmrelease", release, namespace)["spec"].get("suspend", False),
                "deployments": [{"name": item["metadata"]["name"], "uid": item["metadata"]["uid"],
                                 "replicas": item["spec"].get("replicas", 1)} for item in deployments]}

    def app_scale(self, app, stopped, timeout):
        namespace, release = app["namespace"], app["release"]
        if stopped:
            require(self.get("kustomization", release, namespace)["spec"].get("suspend") is True,
                    "Application reconciliation must be suspended in Git before maintenance.")
            self.patch("helmrelease", release, [{"op": "add", "path": "/spec/suspend", "value": True}], namespace)
        for deployment in app["deployments"]:
            live = self.get("deployment", deployment["name"], namespace)
            require(live["metadata"]["uid"] == deployment["uid"], "Application deployment identity changed.")
            replicas = 0 if stopped else deployment["replicas"]
            self.kubectl("-n", namespace, "scale", "deployment/" + deployment["name"], f"--replicas={replicas}")
            if stopped:
                selector = "app.kubernetes.io/instance=" + release
                wait_for(lambda: not self.items("pod", namespace, selector), release + " pods to stop", timeout)
            else:
                self.kubectl("-n", namespace, "rollout", "status", "deployment/" + deployment["name"],
                             f"--timeout={timeout}s", timeout=timeout + 30)
        if not stopped and not app["suspended"]:
            self.flux("resume", "helmrelease", release, "-n", namespace)


def controller_hold(config, operation, run_id):
    host = config["controller_ssh"]
    require(re.fullmatch(r"[a-zA-Z0-9_.@-]+", host) is not None and not host.startswith("-"), "Invalid controller SSH destination.")
    payload = json.dumps({"operation": operation, "id": run_id,
                          "hold": config["controller_hold"], "state": config["controller_state"]})
    script = """
import fcntl,json,os,sys,time
from pathlib import Path
request=json.loads(sys.argv[1])
path=Path(request['hold'])
lock=os.open(str(path)+'.ops-lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
try:
    if request['operation']=='acquire':
        if path.exists():
            assert not path.is_symlink() and json.loads(path.read_text())['ops_run']==request['id'], 'Another maintenance hold exists'
        else:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o640)
            with os.fdopen(fd,'w') as handle:
                json.dump({'ops_run':request['id']},handle);handle.flush();os.fsync(handle.fileno())
            owner=Path(request['state']).stat()
            os.chown(path,owner.st_uid,owner.st_gid)
        deadline=time.monotonic()+30
        while Path(request['state']).stat().st_mtime_ns < path.stat().st_mtime_ns:
            assert time.monotonic()<deadline, 'The preferred-home controller did not acknowledge maintenance'
            time.sleep(1)
        time.sleep(5)
    elif request['operation']=='release':
        if path.exists():
            assert not path.is_symlink() and json.loads(path.read_text())['ops_run']==request['id'], 'Another maintenance hold exists'
            path.unlink()
    else:
        assert not path.is_symlink() and json.loads(path.read_text())['ops_run']==request['id'], 'Maintenance hold is missing'
finally:
    os.close(lock)
"""
    command = "sudo -n python3 - " + shlex.quote(payload)
    identity = ["-i", config["controller_identity"], "-o", "IdentitiesOnly=yes"] if config.get("controller_identity") else []
    run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", *identity, host, command], input=script, timeout=60)
