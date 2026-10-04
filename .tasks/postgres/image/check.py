import json
import os
from pathlib import Path
import re
import subprocess
import sys


def execute(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def source_version():
    source = Path(__file__).with_name("Dockerfile").read_text()
    match = re.search(r"^FROM postgres:([1-9][0-9]*\.[0-9]+)-trixie@sha256:[a-f0-9]{64}$", source, re.M)
    if not match:
        raise ValueError("Pin a stable PostgreSQL major.minor-trixie image and its digest.")
    return match[1]


def verify(image):
    postgres = source_version()
    patroni = Path(__file__).with_name("requirements.txt").read_text().strip().split("==")[1]
    script = """
import json,os,subprocess
import importlib.metadata
import patroni,psycopg2,patroni.dcs.etcd3
print(json.dumps({'postgres':subprocess.check_output(['postgres','--version'],text=True).strip(),
 'patroni':importlib.metadata.version('patroni'),'uid':os.getuid(),
 'pgbackrest':subprocess.check_output(['pgbackrest','version'],text=True).strip()}))
"""
    info = json.loads(execute("docker", "run", "--rm", "--network=none", "--read-only",
                             "--cap-drop=ALL", "--security-opt=no-new-privileges",
                             "--entrypoint=/opt/patroni/bin/python", image, "-c", script))
    assert info["postgres"].split()[2] == postgres, info
    assert info["patroni"] == patroni and info["uid"] == 999, info
    assert info["pgbackrest"].startswith("pgBackRest "), info
    script = """
set -eu
initdb -D /tmp/database --auth=trust >/dev/null
pg_ctl -D /tmp/database -l /tmp/postgres.log -o '-k /tmp -c listen_addresses=' -w start >/dev/null
trap 'pg_ctl -D /tmp/database -m fast -w stop >/dev/null' EXIT
createdb -h /tmp first_app
createdb -h /tmp second_app
psql -h /tmp -d first_app -v ON_ERROR_STOP=1 -c 'CREATE TABLE proof (id integer PRIMARY KEY); INSERT INTO proof VALUES (42)' >/dev/null
test "$(psql -h /tmp -d first_app -Atc 'SELECT id FROM proof')" = 42
test "$(psql -h /tmp -d second_app -Atc \"SELECT count(*) FROM pg_tables WHERE tablename = 'proof'\")" = 0
"""
    execute("docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--tmpfs=/tmp:rw,size=256m,mode=1777",
            "--entrypoint=/bin/bash", image, "-c", script)
    print(json.dumps(info, sort_keys=True))


if __name__ == "__main__":
    if sys.argv[1:] == ["--version"]:
        print(source_version())
    else:
        verify(sys.argv[1])
