# Contributing to n8n_nginx

Thank you for your interest in contributing to n8n_nginx! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project follows a simple code of conduct:

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Keep discussions professional

---

## Getting Started

### Prerequisites

- Docker 20.10+
- Docker Compose v2+
- Git
- A domain name for testing (can use local DNS)
- Basic knowledge of:
  - Bash scripting
  - Python (for backend)
  - Vue.js (for frontend)
  - Docker and Docker Compose

### Project Structure

```
n8n_nginx/
├── setup.sh                    # Main installation script
├── docker-compose.yaml         # Docker Compose template
├── nginx.conf                  # Nginx configuration template
├── management/
│   ├── backend/               # FastAPI backend
│   │   ├── api/              # API routes
│   │   ├── core/             # Core functionality
│   │   ├── models/           # Database models
│   │   └── services/         # Business logic
│   └── frontend/             # Vue.js frontend
│       ├── src/
│       │   ├── components/   # Vue components
│       │   ├── views/        # Page views
│       │   ├── stores/       # Pinia stores
│       │   └── services/     # API services
│       └── public/
├── scripts/                   # Utility scripts
├── tests/                     # Test suites
└── docs/                      # Documentation
```

---

## How to Contribute

### Types of Contributions

1. **Bug Fixes**: Fix issues reported in GitHub Issues
2. **Features**: Implement features from the roadmap or propose new ones
3. **Documentation**: Improve docs, add examples, fix typos
4. **Testing**: Add test coverage, fix failing tests
5. **Translations**: Help translate the management UI

### Contribution Process

1. **Check existing issues** - Look for related issues or discussions
2. **Open an issue** - Discuss your idea before starting work
3. **Fork the repository** - Create your own copy
4. **Create a branch** - Use descriptive branch names
5. **Make changes** - Follow coding standards
6. **Test thoroughly** - Run existing tests, add new ones
7. **Submit PR** - Provide clear description of changes

---

## Development Setup

### Clone and Setup

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/n8n_nginx.git
cd n8n_nginx

# Add upstream remote
git remote add upstream https://github.com/rjsears/n8n_nginx.git
```

### Backend Development

```bash
cd management/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Run locally
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd management/frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### Running Tests

```bash
# Backend tests
cd management/backend
pytest

# Frontend tests
cd management/frontend
npm run test

# Integration tests (requires Docker)
cd tests
./test_installation.sh
```

---

## Coding Standards

### Bash Scripts

- Use `shellcheck` for linting
- Add shebang: `#!/bin/bash`
- Use `set -e` for error handling
- Quote variables: `"$VAR"` not `$VAR`
- Use lowercase for local variables, uppercase for exports
- Add comments for complex logic

```bash
#!/bin/bash
set -e

# Good
local my_var="value"
export MY_EXPORT="value"

if [ -f "$config_file" ]; then
    source "$config_file"
fi
```

### Python (Backend)

- Follow PEP 8 style guide
- Use type hints
- Use async/await for I/O operations
- Document functions with docstrings
- Use meaningful variable names

```python
from typing import Optional

async def get_backup_by_id(backup_id: int) -> Optional[Backup]:
    """
    Retrieve a backup record by ID.

    Args:
        backup_id: The unique identifier of the backup

    Returns:
        Backup object if found, None otherwise
    """
    ...
```

### JavaScript/Vue.js (Frontend)

- Use ESLint configuration provided
- Use Composition API for new components
- Use Pinia for state management
- Keep components focused and small
- Use meaningful component names

```javascript
// Good component structure
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useBackupStore } from '@/stores/backup'

const backupStore = useBackupStore()
const isLoading = ref(false)

const backups = computed(() => backupStore.backups)

onMounted(async () => {
  await backupStore.fetchBackups()
})
</script>
```

### Commit Messages

Follow conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(backup): add NFS storage support

fix(auth): handle expired token gracefully

docs(readme): update installation instructions

refactor(api): extract backup service logic
```

---

## Testing

### Running Tests

```bash
# All tests
./tests/test_installation.sh

# Specific test group
./tests/test_installation.sh -g backend

# With integration tests
./tests/test_installation.sh -i

# Generate JUnit report
./tests/test_installation.sh -j results.xml
```

### Writing Tests

#### Bash Tests

Use the test utilities provided in `tests/test_utils.sh`:

```bash
source tests/test_utils.sh

test_my_feature() {
    log_section "Testing My Feature"

    assert_success "Feature works" "my_command --test"
    assert_file_exists "Config created" "/path/to/config"
    assert_equals "Value correct" "expected" "$actual"
}
```

#### Python Tests

Use pytest for backend tests:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_backups(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/backups/history", headers=auth_headers)
    assert response.status_code == 200
    assert "items" in response.json()
```

#### Frontend Tests

Use Vitest for frontend tests:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BackupList from '@/components/BackupList.vue'

describe('BackupList', () => {
  it('renders backup items', () => {
    const wrapper = mount(BackupList, {
      props: {
        backups: [{ id: 1, name: 'Test Backup' }]
      }
    })
    expect(wrapper.text()).toContain('Test Backup')
  })
})
```

---

## Submitting Changes

### Pull Request Process

1. **Update your fork**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Create feature branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat(scope): description"
   ```

4. **Push to your fork**:
   ```bash
   git push origin feature/my-feature
   ```

5. **Create Pull Request** on GitHub

### PR Requirements

- [ ] Code follows project style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions
- [ ] PR description explains changes clearly

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other (describe)

## Testing
How was this tested?

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

---

## Reporting Issues

### Before Reporting

1. Check existing issues for duplicates
2. Try the latest version
3. Gather relevant information

### Issue Template

```markdown
## Description
Clear description of the issue

## Environment
- OS: Ubuntu 22.04
- Docker: 24.0.7
- Docker Compose: 2.21.0
- n8n_nginx version: 3.0.0

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Logs
```
Relevant log output
```

## Additional Context
Any other relevant information
```

### Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **n8n Community**: https://community.n8n.io

---

## Recognition

Contributors will be recognized in:
- Release notes for significant contributions
- README acknowledgments section
- GitHub contributors list

Thank you for contributing to n8n_nginx!
