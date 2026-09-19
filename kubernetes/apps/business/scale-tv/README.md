# Scale TV releases

Scale TV uses an explicit GitOps promotion. The app repository's `Container`
workflow publishes `ghcr.io/heavybullets8/scale-tv:sha-<commit>` on every push
to `main`. The workflow log reports the pushed multi-platform manifest digest.

To release an app revision, update the image in
`app/helmrelease.yaml` to `sha-<full-commit>@sha256:<manifest-digest>`, render
the pinned app-template chart, and commit the pin to heavy-ops. Flux runs the
Prisma migration Job as a `pre-upgrade` Helm hook. The Deployment and scheduled
maintenance Jobs are updated only after that hook succeeds.

Renovate does not promote these releases. Commit-SHA image tags have no
meaningful version order, so selecting the application commit remains a manual
review step. The digest in the manifest keeps the selected artifact immutable.
