from fastapi.testclient import TestClient

from app.api.main import create_app
from app.settings import Settings


def test_dashboard_ships_local_market_chart_fallback(tmp_path) -> None:
    app = create_app(
        Settings(
            database_path=str(tmp_path / "chart.db"),
            replay_delay_seconds=0.05,
        )
    )

    with TestClient(app) as client:
        index = client.get("/")
        fallback = client.get("/static/native-market-chart.js")

    assert index.status_code == 200
    assert fallback.status_code == 200
    assert 'src="/static/native-market-chart.js"' in index.text

    source = fallback.text
    assert "if (global.LightweightCharts) return;" in source
    assert "renderNativeChart" in source
    assert "movingAverage" in source
    assert "localLevels" in source
    assert "loadMarketHistory" in source
    assert "1Min" in source
    assert "1Day" in source
    assert "1Week" in source
    assert "1Month" in source
    assert "data-market-period" in source
    assert "实时图表本地渲染" in source
