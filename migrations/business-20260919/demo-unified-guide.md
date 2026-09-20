# Unified demo guide

Application revision: `5f44b1274cc28d30d73048bd74033b7ad2d14bca`.

The admin and storefront share one floating Demo guide. It replaces the beaker
menu and duplicate help controls. Inventory opens its desktop card; mobile starts
with an 80 by 44 pixel right-edge tab above the existing navigation. The panel uses
the admin's Radio Canada font, navy actions, pale gray header, and white surface,
including over personalized storefronts.

Mobile opening uses a 180 ms, eight-pixel slide and fade. The closed tab fades
during scrolling and returns after 650 ms idle. Reduced motion disables both
effects. The guide stays beneath the More sheet and notification drawer and
clears the editor's save bar. The wizard tour hides it while running.

Quick price, photo, incoming-stock, contact, and detailed-help actions remain
available. Editor actions target the current editable listing. Exact public
listing links preserve hidden/archive preview access. Storefronts always offer
Open inventory; Exit demo performs full navigation to Bighorn Byte without
clearing saved sandbox changes. Reset remains separate. Private navigation stays
inside its own demo scope, and the optional full tour still works.

Validation before release:

- Required format, lint, type, Fresh guard, and unit lane: 1,564 passed,
  zero failures, two intentionally ignored.
- Production bundle built successfully. The isolated compiled route test passed,
  including marketing without a database and separate private/public demos.
- Browser price edit, save, and exact public result passed on mobile.
- Existing sample photo order changed through the API and persisted on reload.
- The incoming shortcut opened its populated queue.
- Full-tour guide-to-inventory handoff and Escape dismissal of help passed.
- Two private links kept their branding and navigation scope; the public demo
  retained generic branding in the same browser context.
- Exit reached the marketing home and retained sandbox cookies.
- Checks at 320, 390, 768, and 1,440 pixels found no horizontal overflow.
- Scroll opacity measured 0.52 while scrolling and 1 after idle; reduced-motion
  mode retained opacity 1 and disabled the panel entrance animation.
- The storefront loaded the guide font and used the expected navy button color.
- Local browser page-error collection was empty during the completed edit flow.

Image publication `35491322084` passed for the exact application revision. The
web image is pinned to
`sha256:e4d34da94a3476dc055190dd59d9659ea8beae3edd2144f9a96a8fa445af7d79`.
The HelmRelease passed a server dry-run. Prometheus reported zero firing warning
or critical alerts before rollout.

Exact-revision CI `35491310315` passed, including the production page smoke checks
and full database suite. Rollout verification is recorded below after completion.
This release changes only the web image; no schema change or outreach worker
restart is required.
