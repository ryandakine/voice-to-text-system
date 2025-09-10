#!/bin/bash

# Voice-to-Text System - Linting and Security Setup Script
# This script initializes comprehensive linting, security, and accessibility checking

set -e

echo "🚀 Initializing comprehensive linting and security setup..."
echo "========================================================"

# Check if Node.js and npm are installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

echo "✅ Node.js $(node --version) and npm $(npm --version) are installed"

# Install dependencies
echo "📦 Installing linting and security dependencies..."
npm install

# Install pre-commit hooks
if command -v pre-commit &> /dev/null; then
    echo "🔧 Installing pre-commit hooks..."
    pre-commit install
    echo "✅ Pre-commit hooks installed"
else
    echo "⚠️  pre-commit not found. Install with: pip install pre-commit"
fi

# Create secrets baseline for detect-secrets
if command -v detect-secrets &> /dev/null; then
    echo "🔒 Creating secrets baseline..."
    detect-secrets scan --all-files --exclude-files 'package-lock.json' > .secrets.baseline 2>/dev/null || true
    echo "✅ Secrets baseline created"
else
    echo "⚠️  detect-secrets not found. Install with: pip install detect-secrets"
fi

# Run initial checks
echo "🧪 Running initial checks..."

echo "🔍 Running ESLint..."
npm run lint || echo "⚠️  ESLint found issues. Run 'npm run lint:fix' to auto-fix"

echo "🎨 Checking code formatting..."
npm run format:check || echo "⚠️  Formatting issues found. Run 'npm run format' to fix"

echo "🔒 Running security audit..."
npm run security || echo "⚠️  Security vulnerabilities found. Review npm audit output"

echo "♿ Running accessibility checks..."
npm run accessibility || echo "⚠️  Accessibility issues found"

echo ""
echo "🎉 Setup complete!"
echo "=================="
echo ""
echo "Available commands:"
echo "  npm run lint          - Run all linting checks"
echo "  npm run lint:fix      - Auto-fix linting issues"
echo "  npm run format        - Format code with Prettier"
echo "  npm run security      - Run security audits"
echo "  npm run accessibility - Check accessibility issues"
echo "  npm run analyze       - Run all checks"
echo "  npm run pre-commit    - Run pre-commit checks"
echo ""
echo "Git hooks are configured to run automatically on commit."
echo "Push to trigger GitHub Actions CI/CD pipeline."
echo ""
echo "📚 For more information, see DEVELOPMENT.md"

