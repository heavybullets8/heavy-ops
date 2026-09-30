# Business agent runner

This stages the subscription-based Claude Code and Codex runner in `business`, using the existing app-template, Envoy, 1Password, GHCR and OpenEBS patterns.

Implementation and owner instructions: [heavy-ops-agent-runner PR 1](https://github.com/heavybullets8/heavy-ops-agent-runner/pull/1). See its `docs/setup.md`, `docs/acceptance.md` and `docs/operations.md` before enabling this app.

The Flux Kustomization is suspended, the controller has zero replicas and both providers are disabled. Merging this staged configuration does not start the application. Owner review and setup are required before enabling it.

## Enable after owner setup

1. Apply the additive `agent-runner-containerd-2.2.7.json` Talos seccomp profile through the normal reviewed Talos workflow. This keeps the existing browser profile unchanged and adds only `mount`, `umount2` and `pivot_root` for nested CLI sandboxes. Worker pods use nonroot user namespaces and container-local `procMount: Unmasked`; no capabilities or privileged mode are added. Verify this on the actual runtime before launch.
2. Grant the existing `business-ghcr` pull identity read access to both private runner images. The application uses immutable digests from a passing candidate build.
   Before merging the Renovate workflow change, include `heavy-ops-agent-runner` in the existing Renovate GitHub App installation. The workflow requests a token scoped to these two repositories and discovers only those two; no new bot secrets are required. Its repository config takes effect after the implementation is merged into the runner's `main` branch.
3. Supply the `agent-runner` 1Password item, dedicated subscription authorization and read-only Git/package credentials as documented in the implementation repo. No credential values are included here.
4. Register the personal MCP client with the existing Authelia instance using the actual callback and S256 PKCE. Configure the verified owner subject and approved repositories/refs in `app/config/config.json`.
5. Set the controller to one replica and unsuspend the Flux Kustomization, initially leaving providers disabled. Verify HTTPS/OAuth, storage, admission and the worker sandbox on Talos.
6. Enable one provider at a time for read-only acceptance. A dot-discovered tool and a dot-launched job returning a useful result are mandatory. Test cancellation, duplicate submission, restart and native Codex refresh persistence before edits.

## Package installation and limits

Workers can download public HTTP/HTTPS packages to disposable storage. Deno/npm, Python venv/pip, standalone binaries, Playwright, axe, Lighthouse, compilers and PostgreSQL are available. Private npm downloads go through the runner's limited proxy. Nix is not installed in the browser image.

Both Claude and Codex edit jobs get the official Playwright MCP server automatically. It requires no separate account and uses an isolated Chromium session. The final browser checks still exercise Chromium, Firefox and WebKit.

Network policy selects only this app's pods. It permits public web traffic, DNS and the controller callback port while denying private networks, metadata, host services and Kubernetes access from workers. The controller receives only namespace-scoped Jobs permissions. Admission fixes its worker image, commands, mounts, security settings and resource limits. Existing business apps and administrative runners are unchanged.

## Stop or roll back

Disable provider intake, drain/cancel active jobs and wait for worker cleanup before changing credential lineages. Revert image pins and the admission allowlist to a live-verified release; active jobs retain their original image. Keep one controller replica. The 12 GiB PVC is protected from Flux pruning and contains both job records and the latest native Codex credential copy; do not delete it or restore an old auth seed casually.
