#!/usr/bin/env python3
"""Stage a home-server build for the trial branch workflow, or collect its result."""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

NAMESPACE = "mkjm-hosting-build"
REPOSITORY = "ghcr.io/heavybullets8/mkjm-hosting-trial"
HERE = Path(__file__).resolve().parent


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(args):
    return run(args, capture_output=True, text=True).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", default="main")
    parser.add_argument("--expected-server", default="https://192.168.200.16:6443")
    parser.add_argument("--npmrc", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "deploy/hosting-trial/Dockerfile").is_file():
        parser.error("source must contain deploy/hosting-trial/Dockerfile")
    base_commit = output(["git", "-C", str(source), "rev-parse", "HEAD"])
    kube = ["kubectl", "--kubeconfig", str(args.kubeconfig), "--context", args.context]
    actual_server = output([*kube, "config", "view", "--minify", "-o", "jsonpath={.clusters[0].cluster.server}"])
    if actual_server != args.expected_server:
        parser.error("kubeconfig server does not match --expected-server")

    names = output(["git", "-C", str(source), "ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    files = []
    for name in sorted(set(names.split("\0"))):
        if not name:
            continue
        path = Path(name)
        if any(part.startswith(".") for part in path.parts):
            continue
        if any(part in {"node_modules", "_fresh", "tmp", "generated"} for part in path.parts):
            continue
        if path.suffix in {".key", ".pem", ".p12", ".zip", ".log"}:
            continue
        full = source / path
        if not full.is_file() or full.is_symlink() or not full.resolve().is_relative_to(source):
            continue
        files.append(path)
    with tempfile.TemporaryDirectory(prefix="mkjm-build-context-") as temp:
        archive = Path(temp) / "source.tar"
        digest = hashlib.sha256()
        with tarfile.open(archive, "w") as tar:
            for path in files:
                data = (source / path).read_bytes()
                digest.update(str(path).encode() + b"\0" + hashlib.sha256(data).digest())
                info = tarfile.TarInfo(str(path))
                info.size = len(data)
                info.mode = 0o755 if os.access(source / path, os.X_OK) else 0o644
                tar.addfile(info, io.BytesIO(data))
        source_hash = digest.hexdigest()
        version = f"trial-{base_commit[:12]}-{source_hash[:12]}"
        image_tag = f"{REPOSITORY}:{version}"
        request = {"schemaVersion": 1, "sourceBaseCommit": base_commit,
                   "sourceTreeSha256": source_hash, "imageTag": image_tag,
                   "platform": "linux/amd64"}
        print(json.dumps({"server": actual_server, "namespace": NAMESPACE,
                          "baseCommit": base_commit, "sourceSha256": source_hash,
                          "sourceFiles": len(files), "contextBytes": archive.stat().st_size,
                          "imageTag": image_tag, "apply": args.apply}), flush=True)
        if not args.apply:
            return

        exec_cmd = [*kube, "exec", "-n", NAMESPACE, "builder", "-c", "buildkit"]
        if args.collect:
            staged = json.loads(output([*exec_cmd, "--", "cat", "/work/build-request.json"]))
            if staged != request:
                raise SystemExit("Source changed since staging; refusing to misattribute build result")
            metadata = json.loads(output([*exec_cmd, "--", "cat", "/work/build-result.json"]))
            image_digest = metadata.get("containerimage.digest", "")
            if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_digest):
                raise SystemExit("Build returned no immutable image digest")
            manifest = {"version": version, "sourceBaseCommit": base_commit,
                        "sourceTreeSha256": source_hash, "imageTag": image_tag,
                        "image": f"{REPOSITORY}@{image_digest}", "platform": "linux/amd64",
                        "components": ["mk", "jm"], "environment": "isolated-hosting-trial"}
            args.result.parent.mkdir(parents=True, exist_ok=True)
            args.result.write_text(json.dumps(manifest, indent=2) + "\n")
            print(json.dumps(manifest), flush=True)
            run([*kube, "delete", "pod", "builder", "-n", NAMESPACE, "--wait=true", "--timeout=60s"])
            run([*kube, "delete", "secret", "build-credentials", "-n", NAMESPACE])
            return

        # Never replace another build or adopt an unowned namespace.
        ns = run([*kube, "get", "namespace", NAMESPACE, "--ignore-not-found", "-o", "json"],
                 capture_output=True, text=True).stdout
        if ns and json.loads(ns)["metadata"].get("labels", {}).get("app.kubernetes.io/part-of") != "mkjm-hosting-trial":
            raise SystemExit("Refusing an unowned build namespace")
        existing = output([*kube, "get", "pod", "builder", "-n", NAMESPACE, "--ignore-not-found", "-o", "name"])
        if existing:
            raise SystemExit("Builder already exists; inspect it before a new build")
        # Prepare only the namespace/policy first, before storing scoped secrets.
        documents = HERE.joinpath("builder.yaml").read_text().split("\n---\n")
        run([*kube, "apply", "-f", "-"], input="\n---\n".join(documents[:2]), text=True)
        npmrc = args.npmrc.read_text()
        if "//npm.pkg.github.com/:_authToken=" not in npmrc:
            raise SystemExit("npmrc must contain the private package registry credential")
        # Credentials travel only over the authenticated Kubernetes connection.
        secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {
            "name": "build-credentials", "namespace": NAMESPACE,
            "labels": {"app.kubernetes.io/part-of": "mkjm-hosting-trial"}},
            "type": "Opaque", "data": {
                "npmrc": base64.b64encode(npmrc.encode()).decode()}}
        run([*kube, "create", "-f", "-"], input=json.dumps(secret), text=True)
        run([*kube, "apply", "-f", str(HERE / "builder.yaml")])
        run([*kube, "wait", "pod/builder", "-n", NAMESPACE, "--for=condition=Ready", "--timeout=180s"])
        with archive.open("rb") as stream:
            run([*exec_cmd, "-i", "--", "tar", "-xf", "-", "-C", "/work/source"], stdin=stream)
        request_text = json.dumps(request, indent=2) + "\n"
        run([*exec_cmd, "-i", "--", "sh", "-c", "umask 077; cat > /work/build-request.json"],
            input=request_text, text=True)
        HERE.joinpath("build-request.json").write_text(request_text)
        print("Source staged on home server. Push the exact trial branch request to run the publishing workflow.", flush=True)


if __name__ == "__main__":
    main()
