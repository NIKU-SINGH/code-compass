# Claude Project Instructions

The rules every coding agent follows live in AGENTS.md; read and follow them:

@AGENTS.md

This project prioritizes high-quality, professional code with strict documentation standards.

### Standards Checklist:
- **Style**: Use the Google Python Style Guide for all docstrings.
- **Attributes**: All class/method field metadata must live in the docstring, not in inline comments.
- **Examples**: Include functional examples (mapping code to model) in documentation.
- **Line numbering**: Always specify 1-indexed line numbers where metadata contains source locations.
- **Architecture**: Keep all models as plain dataclasses with no side effects or DB dependencies.

### Design Principles:
When asked to design UI, use modern aesthetics (HSL colors, dark mode, rich icons, and glassmorphism) to create a premium user experience.

## UI Development Rules

### Components
- Always use shadcn/ui components. Do not hand-roll a component if a shadcn equivalent exists.
- Shared/reusable components live in `components/ui/`.
- Feature-specific components live alongside their feature, not in `ui/`.

### Icons
- Use `lucide-react` for all icons. No inline SVGs unless explicitly requested.

### Interactivity
- Any clickable element (buttons, cards, list items, icons acting as buttons) must have `cursor-pointer`.

### Styling / Theming
- Follow the existing design system for colors, borders, radii, and spacing — no ad-hoc hex values or arbitrary Tailwind classes when a design token exists.
- Reuse existing CSS variables/theme tokens instead of introducing new ones.

### Component Design
- Components should be stateless with respect to app/server state — accept data and callbacks via props, don't manage state that belongs to a parent or a data layer.
- Local UI-only state (open/closed, hover, input focus, etc.) is fine to keep internal.
- Components must be configurable/reusable — avoid hardcoding text, values, or behavior that could reasonably vary.
- No file should exceed 500 lines. Split into smaller components/hooks if it grows past that.

### Naming
- Use clear, descriptive names — no generic names like `index.tsx` for logic-heavy files.
- Don't repeat the parent directory name in the file name.
  - ❌ `graph/GraphModal.tsx`
  - ✅ `graph/NodeDetailsModal.tsx`
- When a directory has multiple similar components (e.g. several modals), name by what's specific to each, not by the shared pattern: `graph/NodeModal.tsx`, `graph/EdgeModal.tsx` — not `graph/Modal1.tsx` / `graph/Modal2.tsx`.
- Same "don't repeat parent name" rule applies to nested folders.
