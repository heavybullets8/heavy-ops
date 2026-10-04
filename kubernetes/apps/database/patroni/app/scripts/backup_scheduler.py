#!/usr/bin/env python3
"""Run and export status for primary-only scheduled pgBackRest full backups.

Runs inside each site's database Pod with the PostgreSQL data and separate
forensic PVC mounted. Only the current primary runs a backup. Durable state
and the singleton lock live on the forensic PVC; no secrets enter this file.
"""

import argparse
import fcntl
import http.server
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import threading
import time
import urllib.error
import urllib.request


IDENT = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
STOP = False


def on_stop(_signum, _frame):
    global STOP
    STOP = True


def primary(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def load(path):
    if not path.exists():
        return {"last_success": 0, "last_attempt": 0, "last_exit_code": -1,
                "primary": 0, "running": 0}
    value = json.loads(path.read_text())
    for field in ("last_success", "last_attempt", "last_exit_code", "primary", "running"):
        if (isinstance(value.get(field), bool)
                or not isinstance(value.get(field), (int, float))
                or not math.isfinite(value[field])):
            raise ValueError("Invalid backup state field " + field)
    value["running"] = 0
    return value


def persist(path, value):
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, sort_keys=True)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temp, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def filesystem_free_bytes(path):
    info = os.statvfs(path)
    return info.f_bavail * info.f_frsize


def wal_allocated_bytes(path):
    total = 0
    with os.scandir(path) as entries:
        for entry in entries:
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):
                total += info.st_blocks * 512
    return total


def metric_text(args, value):
    labels = f'{{site="{args.site}",stanza="{args.stanza}"}}'
    values = {
        "ha_pgbackrest_last_success_timestamp_seconds": value["last_success"],
        "ha_pgbackrest_last_attempt_timestamp_seconds": value["last_attempt"],
        "ha_pgbackrest_last_exit_code": value["last_exit_code"],
        "ha_pgbackrest_local_primary": value["primary"],
        "ha_pgbackrest_backup_running": value["running"],
        "ha_pgbackrest_forensic_free_bytes": filesystem_free_bytes(args.state_dir),
        "ha_pgbackrest_data_pvc_free_bytes": filesystem_free_bytes(args.data_dir),
        "ha_pgbackrest_pg_wal_allocated_bytes": wal_allocated_bytes(args.data_dir / "pg_wal"),
    }
    return "".join(f"# TYPE {name} gauge\n{name}{labels} {number}\n"
                   for name, number in values.items())


def serve_metrics(args, value, lock):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/healthz":
                body = b"ok\n"
            elif self.path == "/metrics":
                with lock:
                    body = metric_text(args, value).encode()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    server = http.server.ThreadingHTTPServer((args.metrics_bind, args.metrics_port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def command(args, phase, log):
    argv = [args.pgbackrest, f"--stanza={args.stanza}"]
    if phase == "backup":
        argv.append("--type=full")
    argv.append(phase)
    try:
        process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    except OSError:
        return 127
    try:
        return process.wait(timeout=args.command_timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        return 124


def attempt(args, value, lock):
    now = time.time()
    with lock:
        value.update(last_attempt=now, last_exit_code=-1, running=1)
        persist(args.state_dir / "state.json", value)
    log_name = time.strftime("pgbackrest-%Y%m%dT%H%M%SZ", time.gmtime(now))
    log_name += f"-{os.getpid()}.log"
    fd = os.open(args.state_dir / log_name,
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    result = 1
    with os.fdopen(fd, "wb") as log:
        if primary(args.primary_url):
            result = command(args, "check", log)
            if result == 0:
                result = command(args, "backup", log) if primary(args.primary_url) else 2
        else:
            result = 2
        log.flush()
        os.fsync(log.fileno())
    with lock:
        value["last_exit_code"] = result
        value["running"] = 0
        if result == 0:
            value["last_success"] = time.time()
        persist(args.state_dir / "state.json", value)
    print(json.dumps({"event": "backup_attempt", "site": args.site,
                      "stanza": args.stanza, "exit_code": result,
                      "log": str(args.state_dir / log_name)}, sort_keys=True), flush=True)
    return result


def backup_due(active, force, now, value, full_interval, retry_interval):
    return active and (force or (
        now - value["last_success"] >= full_interval
        and now - value["last_attempt"] >= retry_interval
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, choices=("home", "cloud"))
    parser.add_argument("--stanza", required=True)
    parser.add_argument("--state-dir", type=Path, default=Path("/ha-forensics/backup-scheduler"))
    parser.add_argument("--data-dir", type=Path, default=Path("/ha-data/postgres"))
    parser.add_argument("--primary-url", default="http://127.0.0.1:8008/primary")
    parser.add_argument("--pgbackrest", default="/usr/bin/pgbackrest")
    parser.add_argument("--check-every-seconds", type=int, default=30)
    parser.add_argument("--full-every-seconds", type=int, default=86400)
    parser.add_argument("--retry-every-seconds", type=int, default=900)
    parser.add_argument("--command-timeout", type=int, default=14400)
    parser.add_argument("--metrics-bind", default="0.0.0.0")
    parser.add_argument("--metrics-port", type=int, default=9187)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="with --once, run a backup even if a recent success exists")
    args = parser.parse_args()
    if not IDENT.fullmatch(args.stanza):
        parser.error("invalid stanza")
    if min(args.check_every_seconds, args.full_every_seconds,
           args.retry_every_seconds, args.command_timeout) <= 0:
        parser.error("all timeouts must be positive")
    if args.force and not args.once:
        parser.error("--force requires --once")
    args.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if args.state_dir.is_symlink() or args.state_dir.stat().st_mode & 0o077:
        raise RuntimeError("Unsafe backup state directory")
    fd = os.open(args.state_dir / "scheduler.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    value = load(args.state_dir / "state.json")
    lock = threading.RLock()
    signal.signal(signal.SIGTERM, on_stop)
    signal.signal(signal.SIGINT, on_stop)
    server = None if args.once else serve_metrics(args, value, lock)
    try:
        while not STOP:
            active = primary(args.primary_url)
            with lock:
                value["primary"] = int(active)
                persist(args.state_dir / "state.json", value)
            due = backup_due(active, args.force, time.time(), value,
                             args.full_every_seconds, args.retry_every_seconds)
            if due:
                result = attempt(args, value, lock)
                if args.once:
                    return result
            elif args.once:
                return 3 if not active else 0
            deadline = time.monotonic() + args.check_every_seconds
            while not STOP and time.monotonic() < deadline:
                time.sleep(max(0, min(1, deadline - time.monotonic())))
        return 0
    finally:
        if server is not None:
            server.shutdown()
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
