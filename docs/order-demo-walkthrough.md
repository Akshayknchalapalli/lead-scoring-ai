# Learn the order example through familiar full-stack layers

## What actually runs

This example uses FastAPI controllers, Python services, an SQL repository, and a real SQLite database. After retrieving an order, the service calls a separate model client. That client is a **deterministic simulator** using templates. It has no trained model, language understanding, external model call, autonomous tool selection, or learning. The question and instructions are visible inputs; changing them does not alter the simulator's programmed behavior.

This is lesson one: understand where a model component fits into an ordinary application. A real model adapter can later implement the same `generate(ModelInput)` boundary, but it would need output validation and failure handling.

All order records are synthetic. Customer selection is a demo input, not authentication. The page exposes intermediate payloads specifically for learning; do not use it for real customer information.

## Run the page

From the repository root, use your existing demo environment:

```bash
export PYTHONPATH=backend/src
export DEMO_PROVIDER=offline
.venv-demo/bin/python -m uvicorn interview_demo.api:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000/orders-demo, or click the orders link from the advisor page. Stop an existing server with Ctrl+C before restarting it after pulling changes. No additional package installation is needed if your demo requirements are already installed.

The original POC server also exposes `/orders-demo`; that server needs full backend dependencies. The standalone interview server needs only demo dependencies.

## Step 1 — Controller, equivalent to @RestController

Read `backend/src/order_demo/controller.py` and `contracts.py`.

```python
@router.post("/ask")
def ask_order(request: AskOrderRequest,
              service: OrderSupportService = Depends(get_order_service)):
    return service.answer(request)
```

FastAPI exposes this function at `POST /orders-demo/ask`. Pydantic validates the request before it reaches the function. `Depends` supplies the service, like dependency injection in a Spring controller. The controller delegates to the service rather than containing SQL or response-generation rules.

Request:

```json
{
  "customer_id": "demo-a",
  "order_id": 104,
  "question": "Has my order shipped? What is my tracking number?"
}
```

Inputs are validated: positive order ID, a demo customer value, and a question from 1 to 500 characters. In production, customer identity must be derived from trusted authentication.

Exercise: run the page and compare its request panel with this JSON. Then inspect the same endpoint in `/docs`.

## Step 2 — Service, equivalent to @Service

Read `backend/src/order_demo/service.py`.

```python
order = self.repository.find_by_customer_and_id(
    request.customer_id, request.order_id
)
```

The service asks the repository for facts first. If no scoped order exists, it returns a not-found result and does not call the model client. The API represents this educational workflow outcome with HTTP 200 and `status: not_found`; invalid request fields return HTTP 422.

For a found order:

```python
model_input = ModelInput(
    instructions=INSTRUCTIONS,
    question=request.question,
    order=order,
)
answer = self.model_client.generate(model_input)
```

This is the additional service dependency you wanted to see. The repository fetches facts. The model client receives those facts and produces response text. Neither bypasses the service's orchestration.

Exercise: locate both calls in `answer()`. Explain why database retrieval must happen before creating the model input.

## Step 3 — Repository, equivalent to a JDBC/JPA repository

Read `backend/src/order_demo/repository.py`.

```sql
SELECT order_id, status, tracking_number, estimated_delivery
FROM demo_orders
WHERE customer_id = ? AND order_id = ?
```

The query is parameterized and uses both customer and order identifiers. The repository returns an `Order` object, not a customer-facing sentence.

The database is created on first use at `artifacts/order-demo/orders.db`, relative to where the server starts. `ORDER_DEMO_DB` can override that location. Startup inserts synthetic rows only if they do not already exist. Existing records are not reset, which allows you to practice updating and retrieving real SQLite data.

Fixtures:

| Customer | Order | Status | Tracking | Estimated delivery |
|---|---|---|---|---|
| demo-a | 104 | SHIPPED | Unavailable | Unavailable |
| demo-a | 105 | PROCESSING | Unavailable | Unavailable |
| demo-a | 106 | DELIVERED | DEMO-TRACK-106 | Unavailable |
| demo-a | 107 | SHIPPED | DEMO-TRACK-107 | 2026-10-12 |
| demo-b | 104 | PROCESSING | Unavailable | Unavailable |

Exercise: switch between customers for order 104. The same order ID resolves to different scoped records. Request demo-b/107 and observe the missing-order path.

## Step 4 — Instructions and context

`ModelInput` separates:

- Instructions: how to respond.
- Question: what the customer asked.
- Order: facts retrieved from the database.

The instructions say to use supplied facts and not invent tracking numbers, dates, or email notifications. The simulator does not interpret these instructions: its templates implement the relevant response behavior directly. A real model would process the instructions and context, and could still produce an invalid answer.

Exercise: compare the database-result panel with `model_input.order`. They should match exactly. If they differed, you would investigate the service's input preparation.

## Step 5 — Model client, analogous to an external service adapter

Read `backend/src/order_demo/model.py`.

```python
class DemoModelClient:
    def generate(self, model_input: ModelInput) -> str:
        order = model_input.order
        # Explicit templates produce the demonstration response.
```

For order 104, the output is:

> Your order has shipped. A tracking number is currently unavailable. An estimated delivery date is currently unavailable.

There is no generated tracking number or promise of an email. For order 107, the response includes the actual synthetic tracking number and supplied date. Delivered orders are described as marked delivered and do not receive a future-delivery estimate.

The method name `generate` represents the future model-adapter boundary. In this lesson it executes normal Python rules; do not describe it as real LLM inference or a prompt-quality evaluation.

## Step 6 — Response and debugging

The API returns the final answer and educational execution observations:

- Validated request.
- Repository result.
- Model input.
- Model output.
- Run ID and layer events.

These records let you compare each stage. They are not hidden model reasoning or tamper-proof audit storage. The trace is assembled by the service to show the educational request flow.

If the database result is right but model input is wrong, inspect the service. If model input is right but model output is wrong, inspect the model client. If API output is right but the page is wrong, inspect frontend rendering.

## Step 7 — Tests

Read `backend/tests/test_order_demo.py`.

The tests perform actual SQLite operations and API requests. They check customer scoping, missing orders skipping generation, actual database updates flowing into answers, preservation of known tracking/date facts, absence of invented details in deterministic templates, and input validation.

```bash
export PYTHONPATH=backend/src
.venv-demo/bin/python -m pytest backend/tests/test_order_demo.py -v
```

Then rerun the broader suite:

```bash
.venv-demo/bin/python -m pytest backend/tests -q
```

The original POC integration test may skip in demo-only environments; CI installs the full backend and runs that check too.

## Learning sequence

First understand the controller request and repository response. Next understand how the service constructs `ModelInput`. Then read the simulator. Finally inspect one test and modify one synthetic order to reproduce a change in its answer. We will introduce real-model inference and model-output validation only after this flow is clear.
