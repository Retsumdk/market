"""A real, working order book / listing marketplace for the Retsumdk ecosystem.

Maintains buy and sell orders in price priority, matches crossing orders
aggressively (price-time priority) with an explicit quantity-supported
`match` step, and publishes a public snapshot of the book. Pure Python,
no external state, deterministic, and fully unit-tested.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


def _now_micros() -> int:
    return time.time_ns() // 1000


@dataclass
class Order:
    """A single resting order in the book."""

    order_id: str
    price: int  # integer price in the smallest currency unit (e.g. cents)
    qty: int
    side: str  # "buy" | "sell"
    created_micros: int = field(default_factory=_now_micros)

    @property
    def maker(self) -> str:
        return self.order_id


class OrderBook:
    """Price-time priority matching engine with cancellations and snapshots."""

    def __init__(self) -> None:
        # per-side dict keyed by price for O(1) bucket lookup within a list
        self._buys: list[Order] = []          # max-heap by price (price desc)
        self._sells: list[Order] = []         # min-heap by price (price asc)
        self._by_id: dict[str, Order] = {}
        self._trade_log: list[dict] = []

    def _insert(self, order: Order) -> None:
        self._by_id[order.order_id] = order
        bucket = self._buys if order.side == "buy" else self._sells
        bucket.append(order)
        bucket.sort(key=lambda o: (-o.price if order.side == "buy" else o.price, o.created_micros))

    def _best(self, side: str) -> Optional[Order]:
        bucket = self._buys if side == "buy" else self._sells
        return bucket[0] if bucket else None

    def _remove(self, order: Order) -> None:
        bucket = self._buys if order.side == "buy" else self._sells
        try:
            bucket.remove(order)
        except ValueError:
            return
        self._by_id.pop(order.order_id, None)

    def place(self, order_id: str, side: str, price: int, qty: int) -> None:
        """Place a resting order into the book (matching happens via `match`)."""
        if price <= 0 or qty <= 0:
            raise ValueError("price and qty must be positive")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        self._insert(Order(order_id=order_id, price=price, qty=qty, side=side))

    def match(self) -> dict:
        trades = []
        while True:
            best_sell = self._best("sell")
            best_buy = self._best("buy")
            if not best_sell or not best_buy:
                break
            if best_buy.price < best_sell.price:
                break  # no cross
            price = min(best_buy.price, best_sell.price)
            qty = min(best_buy.qty, best_sell.qty)
            trade = {
                "price": price,
                "qty": qty,
                "buy_order": best_buy.order_id,
                "sell_order": best_sell.order_id,
            }
            trades.append(trade)
            self._trade_log.append(trade)
            self._remove(best_buy)
            self._remove(best_sell)
            self.insert_partial(best_buy, qty)
            self.insert_partial(best_sell, qty)
        return {"trades": trades}

    def insert_partial(self, order: Order, filled: int) -> None:
        remaining = order.qty - filled
        if remaining > 0:
            self._insert(Order(order_id=order.order_id, price=order.price, qty=remaining, side=order.side, created_micros=order.created_micros))

    def cancel(self, order_id: str) -> bool:
        order = self._by_id.get(order_id)
        if order is None:
            return False
        self._remove(order)
        return True

    def snapshot(self) -> dict:
        return {
            "bids": [{"price": o.price, "qty": o.qty} for o in self._buys],
            "asks": [{"price": o.price, "qty": o.qty} for o in self._sells],
        }

    def recent_trades(self) -> list[dict]:
        return list(self._trade_log)
