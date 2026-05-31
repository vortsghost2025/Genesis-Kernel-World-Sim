# World Map Skill

## Design System Overview

The World Sim Map (map-v2.html) features a dark-themed geographical interface for visualizing the dual hemisphere civilization simulation. The design emphasizes geographical clarity, interactive controls, and clear visual distinction between simulation elements.

## Color Palette

### Core Neutrals
- `--bg: #0a0a0a` - Main background (near-black)
- `--panel: #1a1a1a` - Panel surfaces (dark gray)
- `--card: #2a2a2a` - Card/elevated surfaces (lighter dark gray)
- `--border: #444` - Borders and dividers (medium gray)
- `--text: #ffffff` - Primary text (pure white)
- `--text2: #cccccc` - Secondary text (light gray)
- `--muted: #888888` - Disabled/hint text (medium-light gray)

### Accent Colors
- `--gold: #ffd700` - Primary accent (rich gold)
- `--green: #00ff88` - Success/positive actions (bright green-cyan)
- `--blue: #4488ff` - Information/primary actions (bright blue)
- `--red: #ff4444` - Negative actions/alerts (bright red)

### Hemisphere Colors
- `--east-color: #4488ff` - East hemisphere (bright blue)
- `--west-color: #ff8844` - West hemisphere (orange)

## Typography

### Font Family
- Primary: `'Segoe UI', system-ui, sans-serif`

### Type Scale (derived from usage)
- Body text: 18px
- Headers: 2rem (32px)
- Nav links: 1.2rem (19.2px)
- Map controls: 1.2rem (19.2px)
- Font weight: 600 (semi-bold) for buttons

## Spacing System

### Base Unit
- 4px spacing grid

### Scale
- 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px
- Header padding: 1.5rem 2rem (24px 32px)
- Header gap: 1rem (16px)
- Map controls padding: 1rem 2rem (16px 32px)
- Map controls gap: 1rem (16px)
- Border widths: 2px, 3px
- Border radius: 6px, 10px

## Component Patterns

### Layout
- Header: Flex layout with space-between, wrapping, gap
- Nav links: Horizontal flex with padding
- Map controls: Flex wrapping with gap and card-based buttons

### Button/Interaction Styles
- Default: Card background with thick border (3px)
- Active/hover: Gold background with black text
- Active states: Solid background color with matching border
- Focus states: Thick outline with offset (3px outline, 2px offset)

### Map-Specific Elements
- Controls use generous padding (1rem 2rem) for touch/finger use
- Minimum height of 60px for touch targets
- Clear visual feedback for active states

## Visual Language

### Design Principles
1. **Geographical clarity** - map should remain visually dominant
2. **Touch-friendly controls** - large hit targets for interaction
3. **Clear state indication** - active states use bold color changes
4. **Information accessibility** - controls always visible and accessible
5. **Consistent with dashboard** - shared color semantics and typography

### Do's
- Use the 4px spacing grid consistently
- Apply hemisphere colors for East/West distinctions
- Use gold for primary actions and highlights
- Maintain large touch targets (min 60px height)
- Use clear border styles for button states (3px width)
- Keep map visualization uncluttered by UI

### Don'ts
- Don't use gradients - all colors are flat/solid
- Don't introduce colors outside the defined palette
- Don't use arbitrary spacing values
- Don't make controls too small for touch interaction
- Don't let UI overlap or obscure map visualization
- Don't use box-shadow on primary elements

## Responsive Considerations
- Flexible wrapping in headers and controls
- Font sizes appropriate for viewing distance
- Touch-friendly minimum target sizes
- Layout adapts to different screen widths through wrapping
