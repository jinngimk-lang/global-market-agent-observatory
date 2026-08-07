"""Deterministic Alpaca Paper API fixtures.

No network access and no credentials are required. These fixtures only model
read-only observer responses.
"""

ACCOUNT = {
    "id": "paper-demo-001",
    "status": "ACTIVE",
    "currency": "USD",
    "equity": "100000",
    "cash": "100000",
    "buying_power": "200000",
}

POSITIONS = [
    {
        "symbol": "AAPL",
        "qty": "10",
        "avg_entry_price": "180",
        "current_price": "185",
        "unrealized_pl": "50",
    }
]

ORDERS = [
    {
        "id": "order-paper-001",
        "symbol": "AAPL",
        "side": "buy",
        "qty": "10",
        "filled_qty": "10",
        "status": "filled",
        "filled_avg_price": "180",
    }
]
