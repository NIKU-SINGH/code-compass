---
name: Documentation Standard
description: Enforces Google Style docstrings and clear attribute definitions for Python code.
---

# Documentation Standard Skill

A skill for ensuring all project code follows premium documentation and aesthetics standards.

## Instructions
When writing or refactoring code:
1. **Google Style**: Use the Google Python Style Guide for all docstrings.
2. **Field Documentation**: Remove all inline comments (e.g., `field: type  # comment`). Instead, document these in the `Attributes:` section of the class docstring.
3. **Examples**: Provide concrete code-to-model mapping examples in the class docstring.
4. **Metadata Accuracy**: For parsing models, ensure 1-indexed line numbers are clearly labeled as such.

## Aesthetics
- **Rich Aesthetics**: Interfaces should be vibrant, use dark modes, and have sleek typography.
- **Dynamic Design**: All UI elements must have hover/micro-transitions.
- **Premium Feels**: Use curated HSL colors and modern icons.

## Verification
Review all generated code to ensure no placeholder comments like `# ...` or `# TODO` remain. Ensure all docstrings are thorough and follow the `Attributes:`, `Args:`, and `Returns:` format.
