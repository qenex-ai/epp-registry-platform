# Contributing to EPP Registry Platform

First off, thank you for considering contributing to the EPP Registry Platform! It's people like you that make this project a great tool for the domain registry community.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps to reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed and what behavior you expected**
* **Include screenshots if relevant**
* **Include your environment details** (OS, Docker version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and expected behavior**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Do not include issue numbers in the PR title
* Include screenshots and animated GIFs in your pull request whenever possible
* Follow the Python/JavaScript style guides
* Include thoughtfully-worded, well-structured tests
* Document new code
* End all files with a newline

## Development Setup

### Prerequisites

* Docker & Docker Compose
* Python 3.11+
* PostgreSQL 15+
* Git

### Setup Steps

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR-USERNAME/epp-registry-platform.git
   cd epp-registry-platform
   ```

3. Set up development environment:
   ```bash
   docker-compose up -d
   ```

4. Run tests:
   ```bash
   docker-compose exec epp-server python -m pytest
   ```

### Coding Standards

#### Python

* Follow PEP 8
* Use type hints where applicable
* Write docstrings for all public methods
* Maximum line length: 100 characters

Example:
```python
def create_domain(domain_name: str, registrar_id: str) -> Domain:
    """
    Create a new domain in the registry.

    Args:
        domain_name: The domain name to register
        registrar_id: The ID of the registrar creating the domain

    Returns:
        Domain: The created domain object

    Raises:
        DomainAlreadyExists: If the domain is already registered
        InvalidDomainName: If the domain name is invalid
    """
    # Implementation
    pass
```

#### Documentation

* Use Markdown for all documentation
* Keep line length to 80 characters where possible
* Use code blocks with language identifiers

## Testing

All code changes should include tests. We use pytest for Python testing.

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_epp_server.py

# Run with coverage
pytest --cov=src tests/
```

## Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

Example:
```
Add domain transfer functionality

Implements EPP transfer commands as per RFC 5731.
Includes transfer request, approve, and reject operations.

Fixes #123
```

## Project Structure

```
epp-registry-platform/
├── epp-server/          # EPP protocol server
├── rdap-server/         # RDAP API server
├── whois-server/        # WHOIS protocol server
├── admin-dashboard/     # Web admin interface
├── database/            # Database schemas and migrations
├── docs/                # Documentation
├── examples/            # Example configurations
├── tests/               # Test suite
└── scripts/             # Utility scripts
```

## Need Help?

* Join our [Discord community](https://discord.gg/qenex)
* Email us at [opensource@qenex.ai](mailto:opensource@qenex.ai)
* Check the [documentation](https://docs.qenex.ai)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🎉
