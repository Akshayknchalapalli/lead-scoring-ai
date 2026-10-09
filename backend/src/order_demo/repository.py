"""Equivalent to a Spring repository: SQL only, no response-generation logic."""
import sqlite3
from pathlib import Path

from order_demo.contracts import Order

class OrderRepository:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_demo_database()

    def _initialize_demo_database(self) -> None:
        # Synthetic rows only. Existing records are preserved on restart.
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS demo_orders (
                    customer_id TEXT NOT NULL,
                    order_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    tracking_number TEXT,
                    estimated_delivery TEXT,
                    PRIMARY KEY (customer_id, order_id)
                )
            """)
            connection.executemany("INSERT OR IGNORE INTO demo_orders VALUES (?, ?, ?, ?, ?)", [
                ("demo-a", 104, "SHIPPED", None, None),
                ("demo-a", 105, "PROCESSING", None, None),
                ("demo-a", 106, "DELIVERED", "DEMO-TRACK-106", None),
                ("demo-a", 107, "SHIPPED", "DEMO-TRACK-107", "2026-10-12"),
                ("demo-b", 104, "PROCESSING", None, None),
            ])

    def find_by_customer_and_id(self, customer_id: str, order_id: int) -> Order | None:
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("""
                SELECT order_id, status, tracking_number, estimated_delivery
                FROM demo_orders
                WHERE customer_id = ? AND order_id = ?
            """, (customer_id, order_id)).fetchone()
        return Order(**dict(row)) if row is not None else None
