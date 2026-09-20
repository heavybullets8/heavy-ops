# Demo inventory entry and optional guides

Application revision: `090d19471f247ebffb8a950f529f456dd8da3d49`.

Public and private demo roots open Inventory. Public trade selection and private
dealer scoping remain intact. The existing dashboard is at `/demo/dashboard`.
Inventory has a floating Demo guide instead of an inline introduction. Mobile
starts with a collapsed launcher above the navigation. The optional price guide
uses the real editor and Save action, then opens the exact updated public listing.
Photos and Incoming remain direct shortcuts. Detailed demo information, contact,
reset, and the full tour are available through More help.

Automatic welcome and tour offers are disabled. Explicit topic guides work even
for visitors who declined the former tour. A guide result is shown only after a
successful guided price save in that browser session. Programmatic full-tour
changes are classified separately from visitors' own saved edits.

Validation before publication:

- Required format, lint, type, Fresh guard, and unit checks: 1,559 passed,
  zero failed, two intentionally ignored.
- Production build succeeded.
- Isolated demo database lane, including compiled private/public route isolation:
  159 passed. Separate preview event/upload lane: seven passed.
- Real browser price edits and public results passed on desktop and mobile.
- A rejected save retained the unsaved edit and did not claim guide completion;
  retry succeeded. A copied result query did not claim an edit occurred.
- Two private demo links retained their respective branding and scoped links in
  one browser; returning to public `/demo` opened the generic trade chooser.
- Existing sample photos reordered through the real API and persisted on reload.
- Desktop/mobile help worked by keyboard. Escape closes help before the guide;
  collapse returns focus and remembers the scoped desktop preference.
- Responsive checks at 320, 390, 768, and 1,440 pixels found no horizontal overflow
  or automatically opened dialog.
- Local private-preview events recorded editor opening, confirmed price/photo
  changes, public-preview clicks, and verified guide completion.

CI release gate: Check `35480442188` passed for the exact application revision,
including production page smoke checks and the full database suite.
Image publication `35480453068` succeeded. The web image is pinned to
`sha256:0bd38841b19e53feda2185538debc83e0811545fc47ebc669e515212043177dc`.
The HelmRelease passed a server dry-run. Warning/critical firing alerts were
empty before rollout.

Production verification after infrastructure `ad8cb783`:

- Check completed with 803 database tests (20 steps) passing and zero failures.
- Web Helm release v14 is Ready and the Deployment rollout completed on the
  pinned image. The outreach worker was not restarted.
- The live public trailer entry returned 200 on Inventory with the generic
  Bighorn Basin branding, the visible guide, and no automatically opened dialog.
- Live mobile guide opening and its price-editor link worked. Browser page
  errors and horizontal overflow were absent in those checks.
- Local desktop/mobile browser checks exercised actual saves and public results;
  production checks were read-only.
- New web logs contained no error or warning entries. Prometheus reported zero
  firing warning or critical alerts after rollout.

Live screenshots are available in the task workspace at
`/tmp/bhb-demo-live-desktop.png`, `/tmp/bhb-demo-live-mobile.png`, and
`/tmp/bhb-demo-live-mobile-open.png`.

This release changes the web application. It requires no schema migration or
outreach worker restart. Scale TV, customer applications, and the unrelated local
accounting changes are outside this release.
