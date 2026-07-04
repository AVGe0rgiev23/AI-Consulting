# LeadGenius Project Rules

## Architecture & Style
- Language: Python 3.10+
- Strategy: Lean, highly performant, modular procedural/functional design. Avoid deep OOP or premature abstractions.
- Framework: Lightweight web UI using FastAPI or Flask, paired with native HTML/Tailwind CSS via CDN (No complex React/Node configurations).
- Database: SQLite with an isolated database layer for easy portability.
- Code Rules: Strictly NO code comments inside the logic. Write self-documenting code with clear variable and function names.

## Verification Requirements
- Every backend tool or API router must have a corresponding test case.
- Run tests automatically after modifying files to verify system state.