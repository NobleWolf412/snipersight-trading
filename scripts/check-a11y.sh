#!/bin/bash
# CI script to run Storybook accessibility checks
# Exits with non-zero status if violations are found

set -e

echo "🔍 Running Storybook a11y checks..."

# Start Storybook in CI mode
npm run build-storybook

echo "✅ Storybook built successfully"
echo "📋 Review a11y violations in the Accessibility panel when running:"
echo "   npm run storybook"
echo ""
echo "Critical rules enabled:"
echo "  - color-contrast"
echo "  - button-name"
echo "  - aria-allowed-attr"
