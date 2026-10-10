# Paper-session beacon restoration, 2026-10-10

The paper-session shortcut was filtered out on the entire paper route, including
setup, and became sticky below the page content on mobile. Restore a fixed
tactical beacon on every route while a paper session is running. Its native link
opens `/training/range#status`, including from `#setup`.

ScannerContext remains the state owner. The beacon reads `isPaperBotActive`,
not the training-route flag; it introduces no polling, session commands or
configuration changes. Existing bot/scan owner-page filtering is retained and
all simultaneous tasks remain directly accessible. The radar uses current theme
tokens, a keyboard focus ring and a reduced-motion override. Shell bottom padding
allows the final page action to scroll clear of one, two or three floating links.

Verification:

- Installed TypeScript compiler, `tsc --noEmit`: passed.
- Actual beacon render tests: 15 passed, covering ten routes, idle/training-only
  states, simultaneous tasks and bot/scan owner routes.
- Existing ScannerContext tests: 17 passed. These include historical mirrored
  derivation checks; the new component tests establish the current route behavior.
- Production frontend build: passed, 4,715 modules.
- Native browser: an existing running paper session displayed the beacon on setup;
  clicking it opened status. Settings showed the same fixed link at 320px and
  1280px. The link measured 230 × 56px, stayed within the viewport with no
  horizontal overflow on these samples, and received a visible keyboard focus ring.
  Paper setup at 390px also had no horizontal overflow.
- Source review: global mounting, existing status owner, theme tokens, safe areas,
  bottom scroll clearance and reduced-motion CSS checked. Runtime reduced-motion,
  simultaneous-task layout, Safari and the full route/state matrix are unverified.
- No session was started, stopped or reset during verification.

This bounded restoration adds no development score. Existing broader audit
limitations remain open.
