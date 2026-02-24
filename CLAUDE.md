# AI Racing Coach — Project Conventions

## Project Overview
AI-powered racing coach for ACC (Assetto Corsa Competizione). Analyzes telemetry data (live via shared memory) and provides driving feedback via LLM-generated reports. MVP scope: post-race analysis only (no real-time voice coaching).

## Tech Stack
- **Language**: Python 3.11+
- **Package manager**: uv
- **Testing**: pytest + pytest-cov + pytest-benchmark
- **Linting/Formatting**: ruff
- **Database**: SQLite (stdlib sqlite3)
- **Telemetry SDK**: ctypes + mmap (ACC shared memory, Windows stdlib only)

## Development Workflow
- **TDD**: Red → Green → Refactor. Write failing tests first.
- **Run tests**: `uv run pytest`
- **Run linter**: `uv run ruff check .`
- **Auto-fix lint**: `uv run ruff check --fix .`
- **Format**: `uv run ruff format .`
- **Coverage**: `uv run pytest --cov`

## Code Conventions
- Commit messages: `<type>(scope): <description>` (e.g., `feat(telemetry): add brake pressure parser`)
- Branch naming: `feature/<sprint>-<task>` (e.g., `feature/s1-telemetry-connection`)
- Test coverage: core modules >= 80%, utilities >= 60%
- Line length: 100 characters
- Use type hints for public APIs

## Project Structure
```
src/racing_coach/
  __init__.py          # Package root
  telemetry/           # Sprint 1: ACC data acquisition
  track/               # Sprint 2: track modeling & corner detection
  analysis/            # Sprint 3: reference lap comparison & error detection
  reporting/           # Sprint 4: LLM feedback generation
tests/
  test_smoke.py        # Toolchain smoke test
  telemetry/           # Tests mirroring src structure
  track/
  analysis/
  reporting/
```

## Sprint Tracking
- When a sprint's tasks and acceptance criteria are all met, update `SPRINT_PLAN.md`:
  - Strike through completed task rows (use `~~text~~`)
  - Check off acceptance checkpoints (`[x]`) and add completion date

## Key Architecture Decisions
- Dual-path architecture: hot path (local, low-latency) + warm path (LLM-powered analysis)
- MVP focuses on warm path only (post-race analysis)
- ACC-only for MVP; multi-sim support deferred
- SQLite for all persistence (zero-deployment)
