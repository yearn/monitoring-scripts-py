# CLAUDE.md - Monitoring Scripts Python Codebase

## Commands

### Installation
- Create virtual environment: `uv venv`
- Activate virtual environment: `source .venv/bin/activate` (On Windows: `.venv\Scripts\activate`)
- Install dependencies:
  - Regular installation: `uv pip install .`
  - Development installation: `uv pip install -e ".[dev]"`
- Environment setup: `cp .env.example .env` (then edit with your API keys)

### Usage
- Run script: `uv run <protocol>/main.py`
  - Example: `uv run aave/main.py`

### Development
- Format code: `uv run ruff format .`
- Lint code: `uv run ruff check .`
- Fix fixable lint issues: `uv run ruff check --fix .`
- Type checking: `uv run mypy .`

## Code Style Guidelines
- **Imports**: Use ruff for organizing imports (stdlib, third-party, local)
- **Formatting**: Use ruff format with line length 120
- **Typing**: Use type hints for all functions (parameters and return values)
- **Docstrings**: Google style docstrings for all functions and classes
- **Naming**:
  - Snake case for functions/variables (`process_assets`)
  - UPPER_CASE for constants (`THRESHOLD_UR`)
  - PascalCase for classes (`ChainManager`)
- **Error handling**: Use specific exceptions with meaningful error messages
- **Web3**: Use ChainManager for connections, batch requests whenever possible
- **Configuration**: Move hardcoded values to configuration files or env variables
- **Logging**: Use structured logging instead of print statements
- **Testing**: Write unit tests for utility functions and integration tests for protocols

## Best Practices
- Create custom exception types for domain-specific errors
- Extract repeated patterns into utility functions
- Use dataclasses for structured data
- Implement dependency injection for better testability
- Add proper type annotations to improve IDE support and catch errors