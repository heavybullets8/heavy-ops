import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid


class Refused(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def run(argv, *, input=None, cwd=None, timeout=120, check=True):
    result = subprocess.run(
        [str(arg) for arg in argv], input=input, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, timeout=timeout,
    )
    if check and result.returncode:
        raise Refused(f"{argv[0]} failed ({result.returncode}): {result.stderr.strip()[-2000:]}")
    return result


def output(argv, **kwargs):
    return run(argv, **kwargs).stdout.strip()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def version(value):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*\.(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))?", value),
            f"Expected a stable version, got {value!r}")
    return tuple(int(part) for part in value.split("."))


def postgres_version(value):
    parts = version(value)
    require(len(parts) == 2 and parts[0] >= 17, "This workflow supports PostgreSQL 17 and later, using major.minor versions.")
    return parts


def image_ref(value):
    match = re.fullmatch(r"(ghcr\.io/[a-z0-9][a-z0-9._/-]*):([0-9]+\.[0-9]+\.[0-9]+)@(sha256:[a-f0-9]{64})", value or "")
    require(match is not None, "Use a published GHCR image with a stable release tag and sha256 digest.")
    return match.groups()


def change_kind(old, new):
    previous = postgres_version(old["postgres"])
    target = postgres_version(new["postgres"])
    require(target >= previous, "PostgreSQL downgrades are not supported.")
    require(version(new["patroni"]) >= version(old["patroni"]), "Patroni downgrades are not supported.")
    require(old["os"] == new["os"], "Keep the operating system distribution unchanged during a database upgrade.")
    require(new["uid"] == old["uid"] == 999, "The database images must retain PostgreSQL UID 999.")
    return "major" if previous[0] != target[0] else "minor"


def yaml_read(path):
    return json.loads(output(["yq", "-o=json", "-I=0", ".", path]))


def yaml_edit(path, expression, value):
    data = json.dumps(value)
    run(["yq", "-i", f"{expression} = {data}", path])


def private_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(not path.is_symlink(), "Refusing a symlink for operational state.")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".ops-")
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("OPS_POSTGRES_STATE_DIR") or
                         Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "ops/postgres")

    def load(self, name):
        require(re.fullmatch(r"[a-zA-Z0-9_-]+", name) is not None, "Invalid state name.")
        path = self.path / (name + ".json")
        require(path.is_file() and not path.is_symlink(), f"Missing state: {path}")
        require(path.stat().st_mode & 0o077 == 0, f"State file must be private (chmod 600): {path}")
        return json.loads(path.read_text())

    def save(self, name, value):
        require(re.fullmatch(r"[a-zA-Z0-9_-]+", name) is not None, "Invalid state name.")
        private_write(self.path / (name + ".json"), value)

    @contextlib.contextmanager
    def lock(self):
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(not self.path.is_symlink() and self.path.stat().st_mode & 0o077 == 0,
                f"State directory must be private (chmod 700): {self.path}")
        descriptor = os.open(self.path / "operation.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Refused("Another PostgreSQL operation is running.") from error
            yield
        finally:
            os.close(descriptor)


def new_id():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]


def confirm(message, *, approved=False, phrase=None):
    if approved and phrase is None:
        return
    require(os.isatty(0), "Interactive confirmation required; run this command in a terminal.")
    if phrase is not None:
        print(message)
        answer = subprocess.check_output(["gum", "input", "--header", f"Type {phrase} to continue"], text=True, timeout=3600).strip()
        require(answer == phrase, "Cancelled.")
    else:
        result = subprocess.run(["gum", "confirm", message], timeout=3600)
        require(result.returncode == 0, "Cancelled.")


def wait_for(predicate, description, timeout=600, interval=3):
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return
        require(time.monotonic() < deadline, f"Timed out waiting for {description}.")
        time.sleep(interval)


def checkpoint(store, state, name, action):
    if name in state["completed"]:
        return
    state["active"] = name
    state.pop("failure", None)
    store.save(state["id"], state)
    print(name.replace("_", " ") + "…", flush=True)
    try:
        result = action()
    except BaseException as error:
        state["failure"] = type(error).__name__
        store.save(state["id"], state)
        raise
    state["completed"].append(name)
    state["active"] = None
    store.save(state["id"], state)
    return result
