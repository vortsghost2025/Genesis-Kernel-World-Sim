# World Sim Dashboard Skill

## Design System Overview

The World Sim Creator Dashboard (sim.html) features a dark-themed interface designed for monitoring and managing the dual hemisphere civilization simulation. The design emphasizes readability, information density, and clear visual hierarchy.

## Color Palette

### Core Neutrals
- `--bg: #07080c` - Main background (near-black dark blue)
- `--panel: #0d111b` - Panel surfaces (slightly lighter than background)
- `--card: #151b2a` - Card/elevated surfaces
- `--border: #232d45` - Borders and dividers
- `--text: #f0f4f8` - Primary text (off-white)
- `--text2: #a0aec0` - Secondary text (muted gray-blue)
- `--muted: #64748b` - Disabled/hint text (slate)

### Accent Colors
- `--gold: #f59e0b` - Primary accent (amber/gold)
- `--green: #10b981` - Success/positive actions (emerald)
- `--blue: #3b82f6` - Information/primary actions (blue)
- `--red: #ef4444` - Negative actions/alerts (red)
- `--purple: #8b5cf6` - Secondary accent (purple)
- `--teal: #14b8a6` - Tertiary accent (teal)

### Hemisphere Colors
- `--east-color: #3b82f6` - East hemisphere (blue)
- `--west-color: #f97316` - West hemisphere (orange)

## Typography

### Font Family
- Primary: `'Segoe UI', system-ui, sans-serif`

### Type Scale (derived from usage)
- Body text: 14px
- Logo/headers: 1.5rem (24px)
- Subtitle text: 0.75rem (12px)
- Header elements: 1.5rem (24px)

## Spacing System

### Base Unit
- 4px spacing grid

### Scale
- 4px, 8px, 12px, 16px, 20px, 24px, 32px, 40px
- Header padding: 1.25rem 2rem (20px 32px)
- Header gap: 1.5rem (24px)
- Logo section gap: 0.5rem (8px)
- Subtitle letter spacing: 0.05em, 0.15em

## Component Patterns

### Layout
- Header: Flex layout with space-between, wrapping, gap
- Logo section: Flex column/row with gap
- Card-based organization with elevation shadows

### Button/Interaction Styles
- Default: Card background with border
- Active/hover: Gold background with inverted text
- Focus states: Ring outlines with offset

### Elevation/Shadows
- Header: `0 4px 20px rgba(0,0,0,0.4)` (subtle depth)
- Interactive elements: Use background/color changes rather than shadows for hover states

## Visual Language

### Design Principles
1. **Dark theme optimized** for low-light monitoring environments
2. **Clear visual hierarchy** using color and spacing
3. **Consistent hemisphere coloring** for instant recognition
4. **Information-dense layout** with clear section separation
5. **Minimal motion** - prefer instant state changes

### Do's
- Use the 4px spacing grid consistently
- Apply hemisphere colors for East/West distinctions
- Use gold for primary actions and highlights
- Maintain contrast ratios for readability
- Use border-radius: 8-10px for cards and buttons

### Don'ts
- Don't use gradients - all colors are flat/solid
- Don't introduce colors outside the defined palette
- Don't use arbitrary spacing values
- Don't add box-shadow to interactive elements (use background changes)
- Don't use backdrop-blur or blur effects

## Responsive Considerations
- Flexible wrapping in headers
- Font sizes scale reasonably
- Touch-friendly button sizing (min-height: 60px in map controls)
