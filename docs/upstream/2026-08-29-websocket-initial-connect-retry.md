# WebSocket initial-connect retry classification — 2026-08-29

## Upstream evidence

- Upstream: `nautechsystems/nautilus_trader`
- Commit: `a5b0f29e1b86d5dbf4ac318a1f362ccf3fbfe72a`
- Upstream PR: `#4867`
- Commit timestamp: 2026-08-28T23:17:55Z
- Signature: GitHub reports the commit as verified.
- License: LGPL-3.0 (NautilusTrader project license).
- Reuse mode: behavior/design evidence only; no upstream source copied.

## Material behavior

The upstream change centralizes WebSocket initial-connect retry and makes retry authority explicit and cancellable. It preserves structured HTTP/proxy rejection status through the transport boundary so transient handshake failures can be distinguished from permanent failures. Its retry policy retries HTTP 408, 425, 429 and 5xx classes, while malformed URL/protocol/configuration failures stop without consuming the retry ladder. Cancellation is selected against rate-limit waits, dial attempts and backoff sleeps. Retry logs also redact the endpoint because WebSocket URLs may contain credentials, tokens or signed query data.

## Local comparison

This repository already has a bounded reconnect supervisor for the Alpaca market feed and treats feed failures separately from capital permission. The current Python feed path does not expose the same generic handler-mode WebSocket builder or proxy handshake transport boundary as NautilusTrader, and this scan did not establish a local failing contract proving that Alpaca initial-connect failures are currently misclassified. Adding a second retry abstraction without such evidence would increase state-machine complexity and could accidentally change fail-closed behavior.

No production code or dependency is changed by this record.

## Durable invariants for future feed work

If the project introduces richer initial-connect retry, proxy support, provider failover, or another WebSocket transport:

1. Retry decisions must be based on structured failure identity/status rather than diagnostic strings.
2. Retryable transient classes and permanent configuration/protocol classes must be explicit and tested.
3. Shutdown/cancellation must interrupt rate-limit waits, connection attempts and backoff sleeps; a retry ladder must not delay ownership shutdown.
4. Endpoint URLs and handshake diagnostics must not leak credentials, tokens, signed query parameters or other secrets into logs.
5. Transport recovery never restores capital permission by itself; freshness, reconciliation, strategy promotion and deterministic risk gates remain independent.
6. A local failure-injection RED must precede production behavior changes.

## Rollback

Documentation-only. Revert this commit if the evidence record is superseded; no runtime behavior changes.