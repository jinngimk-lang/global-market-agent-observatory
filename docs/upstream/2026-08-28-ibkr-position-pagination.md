# IBKR position pagination completeness — 2026-08-28

## Trigger

- Upstream pattern: `nautechsystems/nautilus_trader` commit `1308d94dfc00ac46de5fd33ffa476d2bed46ef75` (2026-08-27), which fixed reconciliation paths where unavailable/partial bulk position coverage could be misread as affirmative flat-position evidence.
- Upstream license: LGPL-3.0. No NautilusTrader source code was copied or adapted; only the evidence-authority/completeness principle was reused.
- Official provider evidence: IBKR Trading Web API documents `GET /portfolio/{accountId}/positions/{pageId}` as the paginated account-position endpoint. Position rows expose `pageSize`, and the endpoint requires a page identifier.

## Local gap

`IBKRObserver` previously requested only `/portfolio/{accountId}/positions/0` and converted that single page into the authoritative `ExternalAccountSnapshot` used by portfolio/risk reconciliation. If an IBKR account held more positions than the first page, later positions were silently omitted. Downstream deterministic risk could therefore reason over an incomplete portfolio while the account was reported as connected.

This is a correctness/safety defect, not a feature request: an incomplete provider position view must not be represented as complete account truth.

## RED evidence

- RED commit: `eb74cacd0b2263fc1938e2e17b274c12f9df56c4`.
- CI run: `#618`.
- The new contract supplies positions on pages 0 and 1 and an empty terminal page 2, and requires both positions to appear in the snapshot. Python 3.12 full pytest failed while Ruff passed, proving the existing observer stopped after page 0.
- Follow-up test-fixture commit `31f8be0cdca3a2b96320c0b1950661403e1f3a61` makes the pre-existing single-page fixture explicitly terminate with an empty page 1 so the contract models the provider's paginated interface.

## GREEN implementation

- GREEN commit: `2c8057e45bcb9f6dd258e90731be5961ac3c7761`.
- `IBKRObserver` now walks `positions/{pageId}` from page 0 until the provider returns an empty page, validates every page as a list of position objects, and only then constructs the account snapshot.
- Any HTTP failure or malformed page still raises before a reconciled portfolio is produced; the implementation does not reinterpret missing/invalid coverage as a flat account.
- No broker write behavior, order type, capital permission, strategy promotion, credential handling, or deterministic risk threshold changed.

## Local behavior versus upstream

The local implementation does not copy NautilusTrader's per-client bulk-coverage model because the current project has one authoritative IBKR account observer rather than a heterogeneous execution-manager fan-out. The smallest local fix is provider-native pagination completeness at the observation boundary.

## Runtime/dependency cost

- No new package or service dependency.
- One extra empty-page request for accounts whose final non-empty page is page 0; additional requests scale only with actual IBKR position pages.
- No new secret scope or trust boundary.

## Rollback

Revert the GREEN implementation and its pagination contract if IBKR replaces or materially changes the documented paginated endpoint. Do not roll back to first-page-only behavior without an alternative provider-supported way to prove full account-position coverage.
