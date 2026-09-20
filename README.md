# market

> Order-book marketplace with limit orders, a crossing-price matching engine, and a full trade history.

### What it is

A real, working order book / listing marketplace for the Retsumdk ecosystem.

Real, working Python for the Retsumdk ecosystem with an executable test suite.

## Getting started

```bash
pip install -r requirements.txt
pytest -q
```

## Features

- **Limit orders on both sides** — `place()` rests a buy or sell order in the book and validates
  price, quantity and side before touching state.
- **Crossing-price matching** — `match()` repeatedly pairs the best bid with the best ask and
  executes every trade where the bid is at or above the ask.
- **Price-time priority** — inside a price level, the older order is matched first; ordering
  uses a microsecond-resolution arrival timestamp.
- **Partial fills** — when quantities differ, the residual quantity is re-rested under the same
  `order_id` and keeps its original arrival timestamp.
- **Cancellation** — `cancel()` removes a resting order and returns a boolean instead of raising.
- **Public market snapshot** — `snapshot()` exposes live bids and asks; `recent_trades()` returns
  the full trade history as a copy.
- **Integer prices and quantities** — no floating point anywhere, because a matching engine that
  cannot compare two prices exactly is not a matching engine.
- **Zero runtime dependencies** — standard library only (`dataclasses`, `time`, `uuid`, `typing`).
  `pytest` is required only to run the test suite.

## Architecture

```
market/
├── order_book.py            # Order dataclass + OrderBook matching engine
├── test_order_book.py       # 4 executable tests
├── pyproject.toml           # package metadata (name, version, MIT license)
├── requirements.txt         # pytest>=7 (test-only)
├── LICENSE                  # MIT © Retsumdk
└── .github/workflows/ci.yml # CI
```

Inside `order_book.py`:

```
OrderBook
├── _buys / _sells   resting-order lists, re-sorted on every insert
│                    buys:  price descending, then oldest first
│                    sells: price ascending,  then oldest first
├── _by_id           order_id -> Order, for O(1) lookup on cancel
├── _trade_log       append-only list of executed trades
├── place()          validate and rest an order
├── match()          execute every crossing, return {"trades": [...]}
├── cancel()         remove a resting order, report whether it existed
├── snapshot()       {"bids": [{"price", "qty"}], "asks": [...]}
└── recent_trades()  full trade history (a copy)
```

Every mutation goes through one of three paths — insert, fill, or cancel — so the book cannot
drift out of sync with `_by_id` and `_trade_log`.

## Usage

Crossing orders execute at the ask price, so the incoming buyer gets any price improvement:

```python
from order_book import OrderBook

book = OrderBook()
book.place("bid-1", "buy",  price=100, qty=5)
book.place("ask-1", "sell", price=95,  qty=3)

result = book.match()
print(result["trades"])
# [{'price': 95, 'qty': 3, 'buy_order': 'bid-1', 'sell_order': 'ask-1'}]

print(book.snapshot())
# {'bids': [{'price': 100, 'qty': 2}], 'asks': []}
```

The two remaining units of `bid-1` stay resting at 100. Orders that do not cross are left
exactly where they are:

```python
book = OrderBook()
book.place("b1", "buy",  price=80, qty=5)
book.place("s1", "sell", price=90, qty=5)

print(book.match())             # {'trades': []}
print(book.snapshot()["bids"])  # [{'price': 80, 'qty': 5}]
print(book.snapshot()["asks"])  # [{'price': 90, 'qty': 5}]
```

Cancellation reports rather than raises, so a double cancel is safe to handle:

```python
print(book.cancel("b1"))  # True  -> removed
print(book.cancel("b1"))  # False -> already gone
print(book.snapshot())
# {'bids': [], 'asks': [{'price': 90, 'qty': 5}]}
```

Every snippet in this README was executed against the current commit, and the comments are the
exact program output.

## API reference

| Member | Signature | Returns | Notes |
| --- | --- | --- | --- |
| `OrderBook.place` | `place(order_id: str, side: str, price: int, qty: int) -> None` | `None` | Raises `ValueError` when `price <= 0`, `qty <= 0`, or `side` is not `"buy"` / `"sell"`. |
| `OrderBook.match` | `match() -> dict` | `{"trades": [trade, ...]}` | Executes crossings until the best bid is below the best ask. |
| `OrderBook.cancel` | `cancel(order_id: str) -> bool` | `True` if removed, `False` if unknown | Never raises for a missing id. |
| `OrderBook.snapshot` | `snapshot() -> dict` | `{"bids": [...], "asks": [...]}` | Reads the live book; no side effects. |
| `OrderBook.recent_trades` | `recent_trades() -> list[dict]` | copy of the trade history | Mutating the returned list does not touch the internal log. |
| `Order.maker` | property | `str` | The order id of the resting maker. |

A trade record is:

```python
{"price": 95, "qty": 3, "buy_order": "bid-1", "sell_order": "ask-1"}
```

Prices are integers in the smallest currency unit (for example cents) and quantities are integers
too. `snapshot()` returns resting orders in match order — bids descending by price, asks ascending —
so `snapshot()["bids"][0]` is always the best bid.

## Matching semantics

1. Take the highest-priced buy and the lowest-priced sell.
2. If `best_buy.price < best_sell.price`, stop — the book is not crossed.
3. Execute `qty = min(buy.qty, sell.qty)` at `price = min(buy.price, sell.price)`, i.e. the resting
   ask, which passes any price improvement to the incoming buyer.
4. Remove both orders, re-rest any residual quantity, and append the trade to the log.
5. Repeat until no crossing pair remains.

Because step 4 re-rests the residual under the *original* `order_id` and the original
`created_micros`, a partially filled order keeps both its identity and its place at the front of
its price level. Trades execute as a batch inside a single `match()` call, so the caller decides
when matching happens rather than having it happen implicitly on `place()`.

## Real-world use case

An agent-to-agent marketplace needs a settlement layer both sides can verify after the fact.
`OrderBook` provides one with no infrastructure: run it in-process to price compute, tokens, or
task slots between agents, then persist `recent_trades()` as the audit trail. Because the module
is pure and deterministic, a test harness can replay an entire session's worth of crossings and
assert the exact trade list.

## Testing

```bash
pip install -r requirements.txt
pytest -q
# 4 passed
```

| Test | What it pins down |
| --- | --- |
| `test_crossing_orders_match_at_best_price` | A crossing pair trades at the ask price with the correct quantity. |
| `test_partial_fill_leaves_resting_quantity` | The unfilled remainder is re-rested, not dropped. |
| `test_no_cross_no_trade` | A non-crossing book produces no trades and keeps both orders. |
| `test_cancel_removes_order` | Cancellation removes the order and reports `True`. |

## License

[MIT](LICENSE) © Retsumdk
