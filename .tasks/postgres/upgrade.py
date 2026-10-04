import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import psycopg2
from psycopg2 import sql


def run(*args):
    return subprocess.check_output([str(a) for a in args], text=True, stderr=subprocess.STDOUT).strip()


def save(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        json.dump(value, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(descriptor)
    os.close(descriptor)


def inventory():
    result = {}
    with psycopg2.connect(host="/tmp", port=50432, user="postgres", dbname="postgres") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datallowconn ORDER BY datname")
            databases = [row[0] for row in cursor]
            cursor.execute("SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls FROM pg_roles WHERE left(rolname,3) <> 'pg_' ORDER BY rolname")
            result["roles"] = cursor.fetchall()
            cursor.execute("SELECT to_jsonb(d) FROM pg_database d WHERE datname='template1'")
            locale = cursor.fetchone()[0]
            cursor.execute("SELECT pg_encoding_to_char(%s)", (locale["encoding"],))
            locale["encoding_name"] = cursor.fetchone()[0]
    result["databases"] = {}
    for database in databases:
        with psycopg2.connect(host="/tmp", port=50432, user="postgres", dbname=database) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','m') AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' ORDER BY 1,2")
                tables = cursor.fetchall()
                counts = []
                for schema, table in tables:
                    cursor.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table)))
                    counts.append([schema, table, cursor.fetchone()[0]])
                cursor.execute("SELECT count(*) FROM pg_largeobject_metadata")
                result["databases"][database] = {"tables": counts, "large_objects": cursor.fetchone()[0]}
    return result, locale


def move(source, target):
    assert not target.exists()
    source.rename(target)
    descriptor = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(descriptor)
    os.close(descriptor)


def control(binaries, data):
    result = {}
    for line in run(binaries / "pg_controldata", data).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def main(request):
    operation = request["operation"]
    assert operation in ("upgrade", "rehearse", "quarantine")
    identifier = request["id"]
    assert re.fullmatch(r"[a-zA-Z0-9-]+", identifier)
    root = Path(request.get("root", "/ha-data"))
    assert root.is_dir() and not root.is_symlink()
    source = root / "postgres"
    target = root / ("postgres-upgrade-" + identifier)
    retained = root / ("postgres-before-" + identifier)
    marker = root / ("ops-upgrade-" + identifier + ".json")
    signature = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    if not marker.exists():
        assert not target.exists() and not retained.exists(), "Upgrade directories exist without an ownership record"
    state = json.loads(marker.read_text()) if marker.exists() else {"signature": signature, "phase": "start"}
    assert state["signature"] == signature, "Upgrade parameters changed"
    old_major, new_major = int(request["old_major"]), int(request["new_major"])
    old_bin = Path("/old/usr/lib/postgresql") / str(old_major) / "bin"
    new_bin = Path("/usr/lib/postgresql") / str(new_major) / "bin"
    if state["phase"] == "complete":
        print(json.dumps(state))
        return
    if operation == "quarantine":
        save(marker, state)
        if source.exists():
            assert (source / "PG_VERSION").read_text().strip() == str(old_major)
            assert not retained.exists(), "The retained replica directory already exists"
            if request.get("old_system_id"):
                assert control(old_bin, source)["Database system identifier"] == request["old_system_id"]
            move(source, retained)
        assert retained.is_dir()
        state["phase"] = "complete"
        save(marker, state)
        print(json.dumps(state))
        return
    assert new_major > old_major >= 17
    hba = root / ("ops-upgrade-" + identifier + ".hba")
    hba.write_text("local all all trust\n")
    options = (f"-k /tmp -c listen_addresses='' -c archive_mode=off "
               f"-c archive_command='' -c hba_file={hba} -c shared_preload_libraries='' "
               "-c unix_socket_permissions=0700")
    if state["phase"] == "start":
        assert (source / "PG_VERSION").read_text().strip() == str(old_major)
        assert not retained.exists(), "The retained primary directory already exists"
        if request.get("old_system_id"):
            assert control(old_bin, source)["Database system identifier"] == request["old_system_id"]
        save(marker, state)
        run(old_bin / "pg_ctl", "-D", source, "-l", root / "ops-old-postgres.log", "-o", options + " -p 50432", "-w", "start")
        try:
            with psycopg2.connect(host="/tmp", port=50432, user="postgres", dbname="postgres") as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_is_in_recovery()")
                    assert cursor.fetchone()[0] is False, "Restore must finish before the upgrade"
                    cursor.execute("SELECT count(*) FROM pg_tablespace WHERE oid NOT IN (1663,1664)")
                    assert cursor.fetchone()[0] == 0, "Custom tablespaces are not supported"
            before, locale = inventory()
        finally:
            run(old_bin / "pg_ctl", "-D", source, "-m", "fast", "-w", "stop")
        if target.exists():
            assert target.is_dir() and not target.is_symlink()
            shutil.rmtree(target)
        provider = {"c": "libc", "i": "icu", "b": "builtin"}[locale["datlocprovider"]]
        flags = ["--encoding=" + locale["encoding_name"], "--locale-provider=" + provider,
                 "--lc-collate=" + locale["datcollate"], "--lc-ctype=" + locale["datctype"]]
        if provider in ("icu", "builtin"):
            value = locale.get("datlocale") or locale.get("daticulocale")
            assert value
            flags.append(("--icu-locale=" if provider == "icu" else "--builtin-locale=") + value)
        checksums = control(old_bin, source)["Data page checksum version"] != "0"
        if checksums:
            flags.append("--data-checksums")
        elif new_major >= 18:
            flags.append("--no-data-checksums")
        run(new_bin / "initdb", "-D", target, "--auth=trust", *flags)
        work = root / ("ops-upgrade-work-" + identifier)
        work.mkdir(exist_ok=True)
        os.chdir(work)
        args = [new_bin / "pg_upgrade", "--old-bindir=" + str(old_bin), "--new-bindir=" + str(new_bin),
                "--old-datadir=" + str(source), "--new-datadir=" + str(target),
                "--old-options=" + options, "--new-options=" + options,
                "--old-port=50432", "--new-port=50433", "--socketdir=/tmp", "--username=postgres"]
        run(*args, "--check")
        run(*args, "--copy")
        (work / "delete_old_cluster.sh").unlink(missing_ok=True)
        run(new_bin / "pg_ctl", "-D", target, "-l", root / "ops-new-postgres.log", "-o", options + " -p 50432", "-w", "start")
        try:
            after, _ = inventory()
            assert before == after, "Database, role, table, or large-object counts changed"
        finally:
            run(new_bin / "pg_ctl", "-D", target, "-m", "fast", "-w", "stop")
        state.update(phase="verified", inventory=hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
                     databases=sorted(before["databases"]), old_system_id=control(old_bin, source)["Database system identifier"],
                     new_system_id=control(new_bin, target)["Database system identifier"])
        save(marker, state)
    if state["phase"] == "verified":
        if source.exists() and (source / "PG_VERSION").read_text().strip() == str(old_major):
            assert not retained.exists()
            move(source, retained)
        assert retained.is_dir()
        if not source.exists():
            move(target, source)
        assert (source / "PG_VERSION").read_text().strip() == str(new_major)
        assert control(new_bin, source)["Database system identifier"] == state["new_system_id"]
        state["phase"] = "installed"
        save(marker, state)
    if operation == "upgrade":
        assert re.fullmatch(r"[a-zA-Z0-9_-]+", request["stanza"])
        run("pgbackrest", "--stanza=" + request["stanza"], "--no-online", "stanza-upgrade")
    state["phase"] = "complete"
    save(marker, state)
    print(json.dumps(state))


if __name__ == "__main__":
    try:
        main(json.loads(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.output[-8000:], file=sys.stderr)
        raise
