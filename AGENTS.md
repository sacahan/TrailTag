# Repository Guidelines

## Project Structure & Module Organization

- `src/api/` — FastAPI backend (routes, services, middleware, monitoring, cache).
- `src/trailtag/` — CrewAI workflow, memory, tools, CLI entry (`main.py`).
- `src/extension/` — Chrome extension (TS/JS, tests, build config, assets).
- `tests/` — Python tests (unit/integration, e2e helpers).
- `scripts/` — Build/deploy utilities (`build_backend.sh`, `build_frontend.sh`).
- `outputs/`, `dist/` — Generated artifacts. Keep out of VCS.

## Build, Test, and Development Commands

- Run API (dev): `uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload`.
- Run Crew CLI: `python -m src.trailtag.main YT_VIDEO_ID`.
- Python tests: `pytest -q` (or `uv run pytest -q`).
- Extension tests: `npm test --prefix src/extension`.
- Extension build: `npm run package --prefix src/extension`.
- Pre-commit all hooks: `pre-commit run -a`.
- Docker (optional): `docker-compose up --build`.

## Coding Style & Naming Conventions

- Formatting: Python via Ruff formatter; JS/TS via Prettier (pre-commit enforces).
- Indentation: 2 spaces (`.editorconfig`).
- Python: snake_case functions/vars, PascalCase classes, modules lowercase with underscores.
- Type hints required for public functions; prefer dataclasses/Pydantic models for API IO.
- Extension TS: filenames kebab-case, exported classes PascalCase.

## Testing Guidelines

- Frameworks: `pytest`, `pytest-asyncio`, `pytest-mock`; TS tests via Jest config in `src/extension/config`.
- Location: add unit tests near modules and integration tests under `tests/integration/`.
- Naming: `test_*.py` and `*_test.py`; mark slow/async with `@pytest.mark.asyncio`.
- Coverage: use `tests/run_e2e_tests.py --coverage` or `pytest --cov` if configured.

## Commit & Pull Request Guidelines

- Conventional Commits style preferred: `feat(api): ...`, `fix(memory): ...`, `docs: ...`, `refactor: ...`, `style: ...`.
- PRs: include a clear description, linked issues, test scope, and screenshots/gifs for extension changes.
- Keep diffs focused; update README/API docs when contracts change.

## Security & Configuration

- Never commit secrets. Use `.env` (see `.env.simple`). Keys: `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `LANGTRACE_API_KEY`.
- Respect provider rate limits; caching lives behind `src/api/cache/` and CrewAI Memory.

## Agent-Specific Instructions

- Modify only relevant modules; follow directory conventions above.
- When adding endpoints, wire routers under `src/api/routes/` and update tests.
- Prefer small, focused patches and run `pre-commit run -a` before proposing changes.
