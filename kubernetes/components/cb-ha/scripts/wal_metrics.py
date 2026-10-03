#!/opt/patroni/bin/python

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os

import psycopg2


PORT = int(os.environ.get("HA_WAL_METRICS_PORT", "9188"))
SOCKET = "/var/run/postgresql"


def number(value):
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def metric(name, value, **labels):
    value = number(value)
    if value is None:
        return None
    suffix = ("{" + ",".join(f"{key}={json.dumps(str(label))}"
                             for key, label in sorted(labels.items())) + "}") if labels else ""
    return f"{name}{suffix} {value:g}"


def collect():
    lines = []
    with psycopg2.connect(host=SOCKET, dbname="postgres", user="postgres",
                          connect_timeout=2,
                          options="-c statement_timeout=2000") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_is_in_recovery(), current_setting('max_slot_wal_keep_size')")
            recovery, cap = cursor.fetchone()
            lines.append(metric("ha_pg_primary", 0 if recovery else 1))
            lines.append(metric("ha_pg_max_slot_wal_keep_unlimited", 1 if cap == "-1" else 0))
            if cap != "-1":
                cursor.execute("SELECT pg_size_bytes(%s)", (cap,))
                lines.append(metric("ha_pg_max_slot_wal_keep_bytes", cursor.fetchone()[0]))
            cursor.execute("SELECT archived_count, failed_count, last_archived_time, last_failed_time "
                           "FROM pg_stat_archiver")
            archived, failed, last_archived, last_failed = cursor.fetchone()
            lines.extend((metric("ha_pg_archived_total", archived),
                          metric("ha_pg_archive_failed_total", failed)))
            now = datetime.now(timezone.utc)
            for name, last in (("ha_pg_last_archived_age_seconds", last_archived),
                               ("ha_pg_last_archive_failure_age_seconds", last_failed)):
                if last is not None:
                    lines.append(metric(name, max(0, (now - last).total_seconds())))
            if not recovery:
                cursor.execute("SELECT pg_current_wal_lsn()")
                current_lsn = cursor.fetchone()[0]
                cursor.execute("""SELECT slot_name, active, wal_status, safe_wal_size,
                                  pg_wal_lsn_diff(%s, restart_lsn)
                                  FROM pg_replication_slots
                                  WHERE slot_type='physical' ORDER BY slot_name""",
                               (current_lsn,))
                for slot, active, status, safe_bytes, lag_bytes in cursor.fetchall():
                    labels = {"slot": slot}
                    lines.extend((metric("ha_pg_physical_slot_active", active, **labels),
                                  metric("ha_pg_physical_slot_lag_bytes", lag_bytes, **labels),
                                  metric("ha_pg_physical_slot_safe_wal_bytes", safe_bytes, **labels),
                                  metric("ha_pg_physical_slot_wal_status", 1,
                                         status=status or "unknown", **labels)))
    return "\n".join(line for line in lines if line is not None) + "\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/healthz":
            status, body = 200, b"ok\n"
        elif self.path == "/metrics":
            try:
                body = ("ha_pg_sql_up 1\n" + collect()).encode()
                status = 200
            except (psycopg2.Error, OSError, ValueError) as error:
                print(f"SQL metrics unavailable: {type(error).__name__}", flush=True)
                status, body = 503, b"ha_pg_sql_up 0\n"
        else:
            status, body = 404, b"not found\n"
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
