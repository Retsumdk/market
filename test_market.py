from order_book import OrderBook


def test_crossing_orders_match_at_best_price():
    book = OrderBook()
    book.place("b1", "buy", price=100, qty=5)
    book.place("s1", "sell", price=95, qty=3)
    result = book.match()
    assert len(result["trades"]) == 1
    assert result["trades"][0]["price"] == 95
    assert result["trades"][0]["qty"] == 3


def test_partial_fill_leaves_resting_quantity():
    book = OrderBook()
    book.place("b1", "buy", price=100, qty=5)
    book.place("s1", "sell", price=90, qty=2)
    book.match()
    # buy order should have 3 remaining
    bids = book.snapshot()["bids"]
    assert sum(o["qty"] for o in bids) == 3


def test_no_cross_no_trade():
    book = OrderBook()
    book.place("b1", "buy", price=80, qty=5)
    book.place("s1", "sell", price=90, qty=5)
    assert book.match()["trades"] == []
    assert len(book.snapshot()["bids"]) == 1
    assert len(book.snapshot()["asks"]) == 1


def test_cancel_removes_order():
    book = OrderBook()
    book.place("b1", "buy", price=100, qty=5)
    assert book.cancel("b1") is True
    assert book.snapshot()["bids"] == []
