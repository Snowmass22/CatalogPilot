# Project rules
- Read docs/PRD.md and docs/adr/ before any task. Follow them strictly. Do not add features outside PRD scope.
- Python 3.12, FastAPI, SQLModel, SQLite. Type hints everywhere. ruff + mypy must pass.
- Layers: api (thin routers) -> services (use cases) -> domain (pure logic). Services depend on ports (StorePort, LLMPort), never on concrete adapters.
- No business logic in routers.
- LLMs never generate price, SKU or stock values. They only propose; validated code executes (ADR-0004).
- All LLM outputs are Pydantic-validated; reject and retry once on invalid output.
- Every service ships with pytest tests. Run tests before declaring a task done.
- Small functions, docstrings on public functions, no dead code.
- Use conventional commit messages.