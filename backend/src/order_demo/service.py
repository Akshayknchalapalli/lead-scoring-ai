"""Equivalent to a Spring service: orchestrates repository then model client."""
from uuid import uuid4

from order_demo.contracts import AskOrderRequest, ModelInput
from order_demo.model import DemoModelClient
from order_demo.repository import OrderRepository

INSTRUCTIONS = (
    "Explain the order status using only the supplied order information. "
    "Do not invent a tracking number, delivery date, or email notification. "
    "Say when information is unavailable."
)

class OrderSupportService:
    def __init__(self, repository: OrderRepository, model_client: DemoModelClient):
        # Constructor injection, like dependencies injected into a Spring service.
        self.repository = repository
        self.model_client = model_client

    def answer(self, request: AskOrderRequest) -> dict:
        trace = [
            {"layer": "controller", "event": "request_validated"},
            {"layer": "service", "event": "lookup_requested"},
        ]
        order = self.repository.find_by_customer_and_id(request.customer_id, request.order_id)
        trace.append({"layer": "repository", "event": "row_found" if order else "row_not_found"})
        common = {"run_id": str(uuid4()), "provider": "deterministic-simulation", "request": request.model_dump()}
        if order is None:
            # No facts means no model call. A missing/out-of-scope order has one response.
            trace.append({"layer": "service", "event": "model_skipped"})
            return {**common, "status": "not_found", "database_result": None,
                    "model_input": None, "model_output": None,
                    "answer": "No order was found in this demo customer scope.", "trace": trace}
        model_input = ModelInput(instructions=INSTRUCTIONS, question=request.question, order=order)
        trace.append({"layer": "service", "event": "model_input_prepared"})
        answer = self.model_client.generate(model_input)
        trace.append({"layer": "model_client", "event": "simulated_response_generated"})
        trace.append({"layer": "service", "event": "answer_returned"})
        return {**common, "status": "completed", "database_result": order.to_dict(),
                "model_input": model_input.to_dict(), "model_output": answer,
                "answer": answer, "trace": trace}
