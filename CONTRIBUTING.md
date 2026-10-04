# Contributing to `mcp-netgear-genie`

Thank you for your interest in contributing to `mcp-netgear-genie`! We welcome bug reports, feature requests, documentation improvements, and pull requests.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/FrankXLT/mcp-netgear-genie.git
   cd mcp-netgear-genie
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run Unit Tests**:
   ```bash
   python3 -m unittest discover tests
   ```

## Guidelines

- **Code Style**: Follow PEP 8 guidelines. Write clear, type-annotated Python code (`typing`).
- **Pydantic Models**: Ensure all new response structures are defined as strongly typed Pydantic models in `models.py`.
- **Sanitization**: Never commit real cable modem MAC addresses, serial numbers, external IP addresses, or passwords into test fixtures or documentation.
- **Backwards Compatibility**: Keep the `format: str = "table"` option available across tools, supporting `"table"`, `"json"`, and `"both"`.

## Submitting Pull Requests

1. Fork the repository and create a feature branch (`git checkout -b feature/my-new-feature`).
2. Make your modifications, adhering to existing patterns and adding unit tests for new functionality.
3. Verify all tests pass: `python3 -m unittest discover tests`.
4. Commit your changes with a clear message following conventional commits (e.g., `feat: ...`, `fix: ...`, `docs: ...`).
5. Open a Pull Request on GitHub with a description of the changes and testing performed.
