# Development Guide

This document outlines the development workflow, coding standards, and automated tools used in the Voice-to-Text System project.

## 🚀 Quick Start

1. **Initialize the development environment:**
   ```bash
   ./scripts/init-linting.sh
   ```

2. **Run all checks:**
   ```bash
   npm run analyze
   ```

## 📋 Automated Code Quality Tools

This project uses comprehensive automated tools to ensure code quality, security, accessibility, and compatibility:

### 🔍 Linting & Code Quality
- **ESLint**: JavaScript/TypeScript linting with security and accessibility plugins
- **Prettier**: Consistent code formatting
- **SonarJS**: Code quality and maintainability analysis

### 🔒 Security Analysis
- **npm audit**: Dependency vulnerability scanning
- **audit-ci**: Automated security audit in CI/CD
- **ESLint Security Plugin**: Security vulnerability detection in code

### ♿ Accessibility
- **eslint-plugin-jsx-a11y**: Accessibility linting for React/JSX
- **ARIA role validation**
- **Semantic HTML enforcement**

### 🔄 Compatibility
- **Node.js compatibility checks**
- **Browser compatibility validation**
- **ESLint environment configurations**

## 🛠️ Available Commands

### Primary Commands
```bash
# Run all checks (linting, security, accessibility)
npm run analyze

# Run linting only
npm run lint

# Auto-fix linting issues
npm run lint:fix

# Format code
npm run format

# Check formatting
npm run format:check

# Security audit
npm run security

# Accessibility checks
npm run accessibility

# Compatibility checks
npm run compatibility
```

### Development Workflow
```bash
# Pre-commit checks (runs automatically)
npm run pre-commit

# CI/CD pipeline checks
npm run ci
```

## 📏 Code Standards

### JavaScript/TypeScript
- **ESLint** configuration in `.eslintrc.js`
- **Prettier** configuration in `.prettierrc`
- **TypeScript** strict mode enabled
- **Import/export** organization with `eslint-plugin-import`

### Python (for any Python code)
- **Black** for code formatting
- **isort** for import organization
- **flake8** for linting
- **mypy** for type checking
- **bandit** for security analysis
- **safety** for dependency vulnerability scanning

### General Standards
- **Semantic versioning** for releases
- **Conventional commits** for commit messages
- **Pre-commit hooks** for automated checks
- **GitHub Actions** for CI/CD

## 🔧 Configuration Files

### ESLint Configuration (`.eslintrc.js`)
Comprehensive ESLint configuration including:
- **Security rules**: Detects injection attacks, unsafe regex, etc.
- **Accessibility rules**: ARIA validation, semantic HTML
- **Code quality rules**: Cognitive complexity, duplicate detection
- **Import rules**: Dependency cycle detection, unused modules
- **TypeScript rules**: Strict type checking, no-explicit-any

### Prettier Configuration (`.prettierrc`)
```json
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 80,
  "tabWidth": 2,
  "useTabs": false
}
```

### Security Configuration (`audit-ci.json`)
```json
{
  "moderate": true,
  "output-format": "text",
  "allowlist": ["GHSA-1234-5678-9012"],
  "retry-count": 3
}
```

## 🔒 Security Features

### Automated Security Checks
1. **Dependency scanning** with `npm audit`
2. **Code security analysis** with ESLint security plugin
3. **Secrets detection** with detect-secrets
4. **Python security analysis** with bandit

### Security Rules Enforced
- **Object injection prevention**
- **Eval expression detection**
- **CSRF protection validation**
- **Timing attack prevention**
- **Buffer overflow protection**
- **Unsafe regex detection**

## ♿ Accessibility Features

### Automated Accessibility Checks
1. **ARIA attributes validation**
2. **Semantic HTML enforcement**
3. **Keyboard navigation support**
4. **Screen reader compatibility**
5. **Color contrast validation**
6. **Focus management**

### Accessibility Rules
- **Alt text requirements** for images
- **ARIA roles and properties**
- **Interactive element requirements**
- **Heading structure validation**
- **Form label associations**

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow (`.github/workflows/ci.yml`)

The CI/CD pipeline runs on:
- **Push** to main/master/develop branches
- **Pull requests** to main/master/develop branches

### Pipeline Stages
1. **Lint and Security**: JavaScript/TypeScript linting and security checks
2. **Python Lint**: Python code quality checks
3. **Build**: Project build verification
4. **Test**: Automated testing

## 🪝 Pre-commit Hooks

### Pre-commit Configuration (`.pre-commit-config.yaml`)

Automatic checks before commits:
- **Trailing whitespace** removal
- **Code formatting** with Black and Prettier
- **Import sorting** with isort
- **Linting** with ESLint and flake8
- **Security scanning** with detect-secrets

### Installing Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

## 📊 Reports and Monitoring

### Generated Reports
- **ESLint reports**: Code quality and security issues
- **Security audit reports**: Dependency vulnerabilities
- **Accessibility reports**: WCAG compliance issues
- **Complexity reports**: Code maintainability metrics

### Monitoring
- **GitHub Actions** for continuous monitoring
- **Pre-commit hooks** for immediate feedback
- **Automated PR checks** for quality gates

## 🐛 Troubleshooting

### Common Issues

#### ESLint Errors
```bash
# Auto-fix most issues
npm run lint:fix

# Check specific file
npx eslint path/to/file.js

# Ignore files in .eslintignore
```

#### Prettier Formatting
```bash
# Format all files
npm run format

# Check formatting without changes
npm run format:check
```

#### Security Vulnerabilities
```bash
# Check current vulnerabilities
npm audit

# Fix automatically fixable vulnerabilities
npm audit fix

# Generate detailed report
npm audit --audit-level moderate
```

#### Pre-commit Hook Issues
```bash
# Skip hooks for a commit
git commit --no-verify

# Run hooks manually
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

## 📈 Best Practices

### Development Workflow
1. **Write code** following established patterns
2. **Run pre-commit checks** before committing
3. **Create feature branches** for new work
4. **Submit pull requests** with detailed descriptions
5. **Review automated checks** in CI/CD pipeline

### Code Review Checklist
- [ ] ESLint passes without errors
- [ ] Code is properly formatted
- [ ] Security scan passes
- [ ] Accessibility requirements met
- [ ] Tests pass (if applicable)
- [ ] Documentation updated

### Security Considerations
- [ ] No hardcoded secrets or credentials
- [ ] Input validation implemented
- [ ] XSS prevention measures in place
- [ ] CSRF protection enabled
- [ ] Dependency vulnerabilities addressed

## 📚 Additional Resources

- [ESLint Documentation](https://eslint.org/docs/)
- [Prettier Documentation](https://prettier.io/docs/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [WCAG Accessibility Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [OWASP Security Guidelines](https://owasp.org/www-project-top-ten/)

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Run** all checks: `npm run analyze`
5. **Commit** with conventional commit messages
6. **Push** to your fork
7. **Create** a pull request

All automated checks must pass before merge.

