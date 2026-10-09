"""A deterministic model simulation. No trained model, network call, or NLP."""
from order_demo.contracts import ModelInput

class DemoModelClient:
    def generate(self, model_input: ModelInput) -> str:
        # These explicit templates stand in for a model response for lesson one.
        # The input question/instructions are visible, but this simulator does not
        # interpret arbitrary language or learn from the instructions.
        order = model_input.order
        status_sentence = {
            "PROCESSING": "Your order is being processed and has not yet shipped.",
            "SHIPPED": "Your order has shipped.",
            "DELIVERED": "Your order is marked as delivered.",
        }.get(order.status, "The supplied order status is not recognized; please request a review.")
        if order.status == "DELIVERED":
            delivery_sentence = ""
        elif order.estimated_delivery:
            delivery_sentence = f" Estimated delivery: {order.estimated_delivery}."
        else:
            delivery_sentence = " An estimated delivery date is currently unavailable."
        tracking_sentence = (f" Tracking number: {order.tracking_number}." if order.tracking_number
                             else " A tracking number is currently unavailable.")
        return status_sentence + tracking_sentence + delivery_sentence
