# UV Instructions

## Package management

Use uv for all Python operations in this project.

- Install dependencies: `uv add <package>`
- Remove dependencies: `uv remove <package>`
- Run scripts and tools: `uv run <command>`
- Sync environment: `uv sync`
- Never use pip, pip install, or bare python/pytest/ruff

## Testing

- Run tests: `uv run pytest`
- Write tests in `tests/` following pytest conventions
- Use `src/` layout imports: `from foo.counter import count_foos`

## Code quality

- Format: `uv run ruff format .`
- Lint: `uv run ruff check --fix .`
- Ruff config lives in pyproject.toml