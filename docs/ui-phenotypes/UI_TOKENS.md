# World Sim UI Design Tokens

## Overview
This document consolidates the design tokens extracted from World Sim's HTML interfaces:
- sim.html (Creator Dashboard)
- map-v2.html (World Map)

## Color Tokens

### Shared Semantic Colors
| Token | Dashboard Value | Map Value | Usage Notes |
|-------|----------------|-----------|-------------|
| --bg | #07080c | #0a0a0a | Main background |
| --panel | #0d111b | #1a1a1a | Panel surfaces |
| --card | #151b2a | #2a2a2a | Elevated surfaces |
| --border | #232d45 | #444 | Dividers and borders |
| --text | #f0f4f8 | #ffffff | Primary text |
| --text2 | #a0aec0 | #cccccc | Secondary text |
| --muted | #64748b | #888888 | Hint/disabled text |
| --gold | #f59e0b | #ffd700 | Primary accent |
| --green | #10b981 | #00ff88 | Success/positive |
| --blue | #3b82f6 | #4488ff | Information/actions |
| --red | #ef4444 | #ff4444 | Negative/alerts |

### Hemisphere-Specific Colors
| Token | Dashboard Value | Map Value | Usage |
|-------|----------------|-----------|-------|
| --east-color | #3b82f6 | #4488ff | East hemisphere identification |
| --west-color | #f97316 | #ff8844 | West hemisphere identification |

### Unique to Dashboard
- --purple: #8b5cf6 (secondary accent)
- --teal: #14b8a6 (tertiary accent)

## Typography Tokens

### Font Family
- `font-family: 'Segoe UI', system-ui, sans-serif` (both)

### Type Scale
| Use | Dashboard | Map | Notes |
|-----|-----------|-----|-------|
| Body | 14px | 18px | Map uses larger body text |
| Logo/Header | 1.5rem (24px) | 2rem (32px) | Map has larger headers |
| Subtitle/Small | 0.75rem (12px) | - | Dashboard-specific |
| Nav/Controls | - | 1.2rem (19.2px) | Map-specific |
| Button Text | - | 1.2rem (19.2px) font-weight: 600 | Map buttons are semi-bold |

## Spacing Tokens

### Base Unit
- 4px (both)

### Spacing Scale
- 4, 8, 12, 16, 20, 24, 32, 40, 48, 64px (derived from both)

### Specific Measurements
| Use | Dashboard | Map |
|-----|-----------|-----|
| Header padding | 1.25rem 2rem (20px 32px) | 1.5rem 2rem (24px 32px) |
| Header gap | 1.5rem (24px) | 1rem (16px) |
| Header logo gap | 0.5rem (8px) | - |
| Controls padding | - | 1rem 2rem (16px 32px) |
| Controls gap | - | 1rem (16px) |
| Button min-height | - | 60px |

## Border & Radius Tokens

### Border Widths
- Dashboard: 2px (header border)
- Map: 2px, 3px (header border, button borders)

### Border Radius
- Dashboard: 8px (implied from design system)
- Map: 6px, 10px (nav links, buttons)

### Elevation/Shadows
- Dashboard: `0 4px 20px rgba(0,0,0,0.4)` (header)
- Map: Minimal shadows, prefers background/color changes for depth indication

## Usage Guidelines

### When to Use Which Values
1. **Dashboard (sim.html)**: Use for creator interface, monitoring, and control panels
2. **Map (map-v2.html)**: Use for geographical visualization and spatial interaction
3. **Shared Semantics**: Color meanings are consistent across both interfaces
4. **Typography**: Map uses larger text for better visibility at distance/justified use
5. **Spacing**: Maintain 4px grid consistency in all implementations

### Component-Specific Applications
- **Buttons**: Use --card background with --border, change to --gold text on --gold background for active states
- **Headers**: Use --panel background with --border bottom separator
- **Text**: Primary --text on --bg, secondary --text2 on --bg, muted --muted on --bg
- **Accents**: Use --gold for primary actions, --green for success, --red for warnings/errors
