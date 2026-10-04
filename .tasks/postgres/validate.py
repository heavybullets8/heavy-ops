from pathlib import Path
import re
import subprocess
import sys


ROOTS = ("kubernetes/apps", "kubernetes/cloud/apps")


def image(text):
    matches = re.findall(r"repository: (ghcr\.io/heavybullets8/(?:cb-ha-db|postgres-patroni))\s+tag: ([^\s]+)", text)
    if len(matches) != 1:
        raise ValueError("Expected one anchored PostgreSQL image in each HelmRelease.")
    repository, tag = matches[0]
    if repository.endswith("/cb-ha-db"):
        if not tag.startswith("0.1.1@sha256:"):
            raise ValueError("Unknown legacy PostgreSQL version; inspect the image before migrating it.")
        major = 18
    else:
        match = re.fullmatch(r"([1-9][0-9]*)\.([0-9]+)\.([0-9]+)@sha256:[a-f0-9]{64}", tag)
        if not match:
            raise ValueError("Pin a PostgreSQL SemVer release and immutable digest.")
        major = int(match[1])
    return repository + ":" + tag, major


def validate(base=None):
    requested = []
    for root in ROOTS:
        path = root + "/database/patroni/app/helmrelease.yaml"
        current = Path(path).read_text()
        target, major = image(current)
        requested.append(target)
        if not re.search(r"^        strategy: OnDelete$", current, re.M):
            raise ValueError("Patroni updates must be coordinated across sites through ops postgres.")
        if base:
            previous = subprocess.check_output(["git", "show", base + ":" + path], text=True)
            _, old_major = image(previous)
            if major < old_major:
                raise ValueError("A PostgreSQL major downgrade is not supported.")
            if major > old_major:
                ks = Path(root + "/database/patroni/ks.yaml").read_text()
                if not re.search(r"^  suspend: true$", ks, re.M):
                    raise ValueError("Major PostgreSQL image changes require the maintenance hold created by ops postgres. Run plan --image with this image, then rehearse and upgrade the saved plan.")
    if len(set(requested)) != 1:
        raise ValueError("Home and cloud must request the same PostgreSQL release.")
    print("PostgreSQL deployment pins and upgrade coordination are valid.")


if __name__ == "__main__":
    validate(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None)
