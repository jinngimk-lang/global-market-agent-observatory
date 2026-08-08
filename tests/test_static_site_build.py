from pathlib import Path

from scripts.build_static_site import build_static_site

ROOT = Path(__file__).resolve().parents[1]


def test_static_site_build_is_relative_observe_only_and_secret_free(tmp_path) -> None:
    output = tmp_path / "site"

    build_static_site(ROOT, output)

    expected = {
        "index.html",
        "styles.css",
        "runtime.js",
        "market-client.js",
        "app.js",
        "lifecycle-recovery.js",
        "config.js",
        "demo-data.js",
        ".nojekyll",
    }
    assert expected <= {path.name for path in output.iterdir()}

    index = (output / "index.html").read_text(encoding="utf-8")
    config = (output / "config.js").read_text(encoding="utf-8")
    demo = (output / "demo-data.js").read_text(encoding="utf-8")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in output.glob("*.js"))

    assert 'href="./styles.css"' in index
    assert 'src="./config.js"' in index
    assert 'src="./demo-data.js"' in index
    assert 'src="./app.js"' in index
    assert 'src="./lifecycle-recovery.js"' in index
    assert "Content-Security-Policy" in index
    assert "https://api.binance.com" in index
    assert "wss://stream.binance.com:9443" in index
    assert "mode: 'static'" in config
    assert "apiBase: ''" in config
    assert "PUBLIC DATA / OBSERVE ONLY" in demo
    assert "ALPACA_API_SECRET" not in combined
    assert "PRIVATE KEY" not in combined
    assert "api/orders" not in combined
    assert "research/refresh" not in combined
    assert "method: 'POST'" not in combined
    assert not (output / "backend-actions.js").exists()
