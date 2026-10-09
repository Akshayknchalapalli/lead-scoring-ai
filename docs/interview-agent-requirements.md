# Interview agent requirements

## Scope and inventory

One agent is implemented: `lead-advisor-1`. It is a LangGraph workflow that retrieves a synthetic tenant-scoped lead, obtains a structured action proposal, validates it against policy and evidence, and returns a recommendation. Its tools do not send messages or change scores. The production ML POC is separate; its trained model is not invoked by this demonstration.

| Requirement | Implementation | Acceptance evidence |
|---|---|---|
| Framework-based orchestration | `interview_demo/agent.py`, StateGraph with conditional routing | Trace contains retrieve then advise/unavailable |
| Prompt refinement | `prompts.py`, version and SHA-256 digest | Every run identifies prompt version and exact prompt hash |
| Scoped retrieval | Composite `(tenant_id, lead_id)` lookup | Same ID produces different actions in demo-a/demo-b; absent scoped lead skips model |
| Grounded output | Exact schema, allowed policy action, complete known evidence IDs | Invented/duplicate IDs, extra fields, invalid actions rejected |
| Defect recovery | Maximum two provider attempts | Transient failure recovers; repeated failure recommends human review |
| Evidence trail | UUID, timestamp, input/prompt hashes, provider/model, trace, attempts, output, latency | JSON round-trip test and downloadable UI evidence |
| Regression coverage | Ten named scenarios plus fault-injection and API tests | pytest JUnit and scenario Markdown/JSON reports |
| Quality gate | GitHub Actions fails on test errors | Workflow uploads evidence even when checks fail |

## Policies

- Missing or out-of-scope lead: unavailable. Do not call the model.
- Missing signals: human review. Do not call the model.
- Scheduled meeting: confirm the meeting, even if the score is cold.
- Otherwise: hot → prioritize outreach; warm → follow up; cold → nurture.
- User text cannot change the action policy or tenant lookup.
- Accept no free-form generated explanation. Build displayed prose from approved action labels and verified signal facts.
- Retry invalid output or provider errors once, then request human review.

This deliberately constrains the LLM. It demonstrates orchestration, contracts, and failure handling rather than delegating scoring or policy decisions to a generative model.

## Prompt improvement exercise

Start from the existing POC's category-based action recommendation: a cold category naturally produces nurture advice. The new `meeting-precedence` scenario requires confirming an existing meeting. The graph encodes the policy in code; prompt v2 states the same rule so live model proposals can conform. This is a documented design case, not a measured before/after LLM experiment.

To demonstrate a real defect cycle:

1. Make a temporary local change to `policy()` that returns a category action before checking `meeting`.
2. Run `pytest backend/tests -k scenario`; `meeting-precedence` should fail.
3. Read expected versus actual action and the affected run trace.
4. Restore meeting precedence and rerun the entire suite.
5. For a prompt-only experiment, use live Ollama, change the prompt with a new version, and compare scenario reports. Keep code policy validation active.

A successful offline test does not demonstrate that the model resists injection. It demonstrates that code enforces the boundary even when proposals are malicious or malformed. Run live scenarios separately to assess prompt compliance.

## Evidence limits and next integration

Run artifacts avoid retaining raw user requests; they contain a request hash and approved synthetic facts. These files are local development records, not a tamper-proof audit system. Reports record Git revision, working-tree status, scenario hash, Python and LangGraph versions. Hashes identify inputs but do not encrypt them. Do not submit customer PII to this demo.

Connect the existing POC later through a retrieval adapter returning validated scoring facts and actual model-version metadata. Derive tenant scope from an authenticated session, enforce feature flags, and store audit evidence with retention and access policies. Validate on real held-out data before making accuracy or latency claims. Do not claim the blueprint's AUC or sub-2ms targets as achieved results.
