"""Equivalent to a Spring REST controller: validate input, delegate, return JSON."""
import os
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from order_demo.contracts import AskOrderRequest
from order_demo.model import DemoModelClient
from order_demo.repository import OrderRepository
from order_demo.service import OrderSupportService

router = APIRouter(prefix="/orders-demo", tags=["order learning demo"])

@lru_cache(maxsize=1)
def get_order_service() -> OrderSupportService:
    database_path = Path(os.getenv("ORDER_DEMO_DB", "artifacts/order-demo/orders.db"))
    return OrderSupportService(OrderRepository(database_path), DemoModelClient())

@router.post("/ask")
def ask_order(request: AskOrderRequest, service: OrderSupportService = Depends(get_order_service)):
    return service.answer(request)

@router.get("", response_class=HTMLResponse)
def home():
    return Path(__file__).with_name("index.html").read_text(encoding="utf-8")
