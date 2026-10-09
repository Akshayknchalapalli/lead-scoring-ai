"""The objects passed between our familiar application layers."""
from dataclasses import asdict, dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

class AskOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Demo-only customer selection. A real application derives this from authentication.
    customer_id: Literal["demo-a", "demo-b"] = "demo-a"
    order_id: int = Field(default=104, gt=0)
    question: str = Field(default="Has my order shipped? What is my tracking number?", min_length=1, max_length=500)

@dataclass(frozen=True)
class Order:
    order_id: int
    status: str
    tracking_number: str | None
    estimated_delivery: str | None

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass(frozen=True)
class ModelInput:
    instructions: str
    question: str
    order: Order

    def to_dict(self) -> dict:
        return {"instructions": self.instructions, "question": self.question, "order": self.order.to_dict()}
