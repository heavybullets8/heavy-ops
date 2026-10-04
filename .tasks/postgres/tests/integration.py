import json
from pathlib import Path
import subprocess
import sys
import uuid


def run(*argv, check=True):
    result = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(result.stdout)
    return result


def main(image):
    directory = Path(__file__).resolve().parent
    old = (directory / "Dockerfile").read_text().strip().split()[1]
    new_major = int(run("docker", "run", "--rm", "--network=none", "--entrypoint=postgres", image, "--version").stdout.split()[2].split(".")[0])
    assert new_major > 17
    identity = "ops-upgrade-test-" + uuid.uuid4().hex[:10]
    volumes = [identity + "-data", identity + "-binaries"]
    for volume in volumes:
        run("docker", "volume", "create", volume)
    mounts = ["-v", volumes[0] + ":/ha-data", "-v", volumes[1] + ":/old",
              "-v", str(directory.parent) + ":/upgrade:ro"]
    try:
        run("docker", "run", "--rm", "--network=none", "--user=0", *mounts, "--entrypoint=/bin/bash", old, "-c",
            "set -eu; mkdir -p /old/usr/lib/postgresql /old/usr/share/postgresql; "
            "cp -a /usr/lib/postgresql/17 /old/usr/lib/postgresql/; "
            "cp -a /usr/share/postgresql/17 /old/usr/share/postgresql/; chown 999:999 /ha-data")
        run("docker", "run", "--rm", "--network=none", "--user=999:999", *mounts, "--entrypoint=/bin/bash", old, "-c", """
set -eu
initdb -D /ha-data/postgres --auth=trust --data-checksums >/dev/null
pg_ctl -D /ha-data/postgres -l /tmp/postgres.log -o '-k /tmp -c listen_addresses=' -w start >/dev/null
trap 'pg_ctl -D /ha-data/postgres -m fast -w stop >/dev/null' EXIT
psql -h /tmp -d postgres -v ON_ERROR_STOP=1 -c 'CREATE ROLE first_app LOGIN' >/dev/null
createdb -h /tmp -O first_app first_app
createdb -h /tmp second_app
psql -h /tmp -d first_app -v ON_ERROR_STOP=1 -c "CREATE TABLE proof(id bigserial PRIMARY KEY, payload text); INSERT INTO proof(payload) VALUES ('preserve first database'); CREATE MATERIALIZED VIEW materialized AS SELECT * FROM proof;" >/dev/null
psql -h /tmp -d second_app -v ON_ERROR_STOP=1 -c "CREATE TABLE proof(payload text); INSERT INTO proof VALUES ('preserve second database');" >/dev/null
""")
        request = {"id": "integration", "operation": "rehearse", "old_major": 17, "new_major": new_major, "stanza": "test"}
        command = ["docker", "run", "--rm", "--network=none", "--user=999:999", *mounts,
                   "--entrypoint=/opt/patroni/bin/python", image]
        interrupted = run(*command, "-c", """
import json,sys
sys.path.insert(0,'/upgrade')
import upgrade
save=upgrade.save
def interrupted(path,value):
    save(path,value)
    if value['phase']=='verified': raise SystemExit(42)
upgrade.save=interrupted
upgrade.main(json.loads(sys.argv[1]))
""", json.dumps(request), check=False)
        assert interrupted.returncode == 42, interrupted.stdout
        interrupted_move = run(*command, "-c", """
import json,sys
sys.path.insert(0,'/upgrade')
import upgrade
move=upgrade.move
def interrupted(source,target):
    move(source,target)
    if target.name.startswith('postgres-before-'): raise SystemExit(43)
upgrade.move=interrupted
upgrade.main(json.loads(sys.argv[1]))
""", json.dumps(request), check=False)
        assert interrupted_move.returncode == 43, interrupted_move.stdout
        resumed = run(*command, "/upgrade/upgrade.py", json.dumps(request))
        proof = json.loads(resumed.stdout.strip().splitlines()[-1])
        assert proof["phase"] == "complete" and proof["databases"] == ["first_app", "postgres", "second_app"], proof
        repeated = run(*command, "/upgrade/upgrade.py", json.dumps(request))
        assert json.loads(repeated.stdout.strip().splitlines()[-1]) == proof
        changed = run(*command, "/upgrade/upgrade.py", json.dumps(dict(request, new_major=new_major + 1)), check=False)
        assert changed.returncode != 0 and "Upgrade parameters changed" in changed.stdout
        result = run("docker", "run", "--rm", "--network=none", "--user=999:999", *mounts,
                     "--entrypoint=/bin/bash", image, "-c", """
set -eu
test "$(cat /ha-data/postgres-before-integration/PG_VERSION)" = 17
test "$(cat /ha-data/postgres/PG_VERSION)" = "$1"
test ! -e /ha-data/ops-upgrade-work-integration/delete_old_cluster.sh
pg_ctl -D /ha-data/postgres -l /tmp/postgres.log -o '-k /tmp -c listen_addresses=' -w start >/dev/null
trap 'pg_ctl -D /ha-data/postgres -m fast -w stop >/dev/null' EXIT
test "$(psql -h /tmp -d first_app -Atc 'SELECT payload FROM proof')" = 'preserve first database'
test "$(psql -h /tmp -d second_app -Atc 'SELECT payload FROM proof')" = 'preserve second database'
test "$(psql -h /tmp -d first_app -Atc \"INSERT INTO proof(payload) VALUES ('sequence survived') RETURNING id\" | head -1)" = 2
""", "--", str(new_major))
        print(f"PASS: PostgreSQL 17 → {new_major}; two application databases, roles, sequences, retained old data, interruption/resume, and parameter mismatch rejection.")
    finally:
        for volume in volumes:
            run("docker", "volume", "rm", volume, check=False)


if __name__ == "__main__":
    main(sys.argv[1])
