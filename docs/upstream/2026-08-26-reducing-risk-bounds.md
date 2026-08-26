# Reducing-risk bounds provenance

Date: 2026-08-26

Upstream signal: `nautechsystems/nautilus_trader` commit `8aa30f9acad6c623eca9a1489e3a4cd4c955f66f` (2026-08-26T09:41:40Z), LGPL-3.0. The upstream change prevents verified whole-position exits from being denied by bounds that are meaningful only for creation or enlargement of exposure, while retaining ordinary validation. No upstream source code was copied; only the behavior was independently adapted.

Local gap: the deterministic risk engine identified exposure reductions for REDUCING mode, but drawdown, realized-loss, per-order notional, symbol/gross exposure, and cash-style entry bounds could still deny a strict non-reversing reduction.

Local invariant: a reduction is verified only from fresh account state when an existing non-zero position projects to a strictly smaller absolute quantity without crossing through zero. Such a reduction may bypass only new-risk bounds. HALTED state, stale market/account state, symbol allowlisting, positive quantity, positive reference price, and reversal rejection remain fail-closed.

RED: `bfa54a568b3bb30d00e62b8499fc912bd1d85225`; CI #580 reproduced two intended failures with 264 passing tests: drawdown lockout blocked a full reduction, and order-notional lockout blocked a full reduction.

GREEN: `022de44c2507cac08c7f083177c48f01f5d902a8`; CI #582 completed successfully across Python 3.12/3.13, Ruff, full pytest, compileall, engineering-skill verification, and container build.

Rollback is a normal revert. No dependency, schema, credential, broker-account, or paid-service change was introduced.
