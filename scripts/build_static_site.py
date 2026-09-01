from __future__ import annotations

import argparse
import shutil
from pathlib import Path

STATIC_CONFIG = """window.OBSERVATORY_CONFIG = Object.freeze({
  mode: 'static',
  apiBase: '',
  market: Object.freeze({
    symbol: 'BTCUSDT',
    interval: '1m',
  }),
});
"""

DEMO_DATA = """window.OBSERVATORY_DEMO_DATA = Object.freeze({
  notice: 'PUBLIC DATA / OBSERVE ONLY',
  portfolio: Object.freeze({
    equity: 0,
    cash: 0,
    gross_exposure: 0,
    realized_pnl_today: 0,
    positions: Object.freeze([]),
  }),
  orders: Object.freeze([]),
  accounts: Object.freeze({accounts: Object.freeze([])}),
  crisisWinners: Object.freeze([]),
  partnerships: Object.freeze([]),
  evidence: Object.freeze([]),
});
"""

STATIC_CSP_META = """  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' https://unpkg.com; style-src 'self'; connect-src https://api.binance.com wss://stream.binance.com:9443; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'">
"""

ASSET_NAMES = (
    "styles.css",
    "advanced-market-chart.css",
    "context-intelligence.css",
    "runtime.js",
    "market-client.js",
    "app.js",
    "symbol-switcher.js",
    "advanced-market-chart.js",
    "native-market-chart.js",
    "context-intelligence.js",
)


def build_static_site(source_root: Path, output_root: Path) -> None:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    web_root = source_root / "app" / "web"

    if output_root == source_root or source_root in output_root.parents and output_root.name == "app":
        raise ValueError("output directory must not replace the application source")

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    index = (web_root / "index.html").read_text(encoding="utf-8")
    index = index.replace(
        '  <meta name="color-scheme" content="dark">\n',
        '  <meta name="color-scheme" content="dark">\n' + STATIC_CSP_META,
    )
    index = index.replace('href="/static/', 'href="./')
    index = index.replace('src="/static/', 'src="./')
    index = index.replace('  <script src="./backend-actions.js"></script>\n', '')
    index = index.replace(
        '  <script src="./runtime.js"></script>',
        '  <script src="./demo-data.js"></script>\n  <script src="./runtime.js"></script>',
    )
    (output_root / "index.html").write_text(index, encoding="utf-8")

    for name in ASSET_NAMES:
        shutil.copyfile(web_root / name, output_root / name)

    (output_root / "config.js").write_text(STATIC_CONFIG, encoding="utf-8")
    (output_root / "demo-data.js").write_text(DEMO_DATA, encoding="utf-8")
    (output_root / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the observe-only static dashboard")
    parser.add_argument("--output", type=Path, default=Path("site"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    build_static_site(root, root / args.output)
    print(f"static-site-built:{(root / args.output).resolve()}")


if __name__ == "__main__":
    main()
