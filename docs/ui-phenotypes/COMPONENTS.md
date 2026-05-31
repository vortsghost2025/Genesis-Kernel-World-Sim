# World Sim UI Components

## Overview
Documentation of reusable UI patterns and components observed in World Sim interfaces.

## Component Catalog

### 1. Header Bar
**Files**: sim.html, map-v2.html
**Purpose**: Primary navigation and branding container
**Structure**:
- Flex container with `justify-content: space-between`
- Wrapping capability for responsive behavior
- Defined height with padding
- Border bottom for separation

**Variants**:
- Dashboard: Simpler layout with logo and subtitle
- Map: Includes navigation links array

**Styling**:
- Background: var(--panel)
- Border-bottom: 2px solid var(--border) (dashboard) or 3px solid var(--gold) (map)
- Padding: 1.25rem 2rem (dashboard) or 1.5rem 2rem (map)
- Gap: 1.5rem (dashboard) or 1rem (map) between sections

### 2. Logo Section
**File**: sim.html
**Purpose**: Brand identification
**Structure**:
- Flex column layout
- Main title (h1)
- Subtitle text

**Styling**:
- Title: 1.5rem, var(--gold) color, letter-spacing 0.05em
- Subtitle: 0.75rem, var(--text2) color, text-transform uppercase, letter-spacing 0.15em
- Gap: 0.5rem between icon and text

### 3. Navigation Links
**File**: map-v2.html
**Purpose**: Primary navigation
**Structure**:
- Horizontal flex container
- Anchor links with hover states

**Styling**:
- Color: var(--blue)
- Text-decoration: underline
- Font-size: 1.2rem
- Padding: 0.5rem 1rem
- Hover: Background var(--card), border-radius 6px

### 4. Control Buttons
**Files**: Primarily map-v2.html (map controls)
**Purpose**: User interaction and simulation control
**Structure**:
- Individual buttons in flex container
- Generous touch targets
- Clear visual feedback for states

**Styling**:
- Base: var(--card) background, 3px solid var(--border) border
- Text: var(--color), font-size 1.2rem, font-weight 600
- Min-height: 60px
- Border-radius: 10px
- Cursor: pointer

**States**:
- Hover/Focus: Background var(--gold), color #000, 3px solid var(--gold) border, 3px outline 2px offset
- Active: Solid background color (--east-color/--west-color/--gold) with matching border
- Disabled: Would use --muted text on --card background (not observed but pattern implied)

### 5. Card Container
**Files**: Both (implied through usage)
**Purpose**: Content grouping and elevation
**Structure**:
- Rectangular container with padding
- Border and background styling
- Border radius for soft corners

**Styling**:
- Background: var(--card)
- Border: 1px-2px solid var(--border)
- Border-radius: 8px-10px
- Padding: 16px-24px (4px grid multiples)

### 6. Section Divider
**Files**: Both (implied)
**Purpose**: Visual separation of content areas
**Structure**:
- Thin horizontal rule or bordered element

**Styling**:
- Height: 1px-2px
- Background: var(--border)
- Margin: Vertical spacing using 4px grid

## Interaction Patterns

### Button Interactions
1. **Default State**: Card background with border
2. **Hover/Focus**: Background change to accent color (typically gold) with text inversion
3. **Active State**: Solid background color matching context (hemisphere colors or gold)
4. **Disabled State**: Muted text on muted background (pattern to implement)

### Focus Indicators
- Use of outline properties for keyboard accessibility
- Outline-offset to prevent touching element edges
- Consistent 3px width for visibility

## Anti-Patterns Observed (What to Avoid)

1. **Inconsistent Hemisphere Colors**: Always use --east-color and --west-color for East/West distinctions
2. **Arbitrary Spacing**: All measurements should align with 4px grid
3. **Gradient Usage**: All colors should be flat/solid - no gradients observed
4. **Inconsistent Border Widths**: Use defined widths (2px, 3px) consistently
5. **Poor Contrast**: Maintain WCAG compliance for text/background combinations
6. **Overly Complex Shadows**: Prefer background/color changes over shadows for interactive states
7. **Inconsistent Typography**: Stick to defined type scale and font family

## Component Composition Guidelines

### Building New Components
1. Start with COLOR tokens from UI_TOKENS.md
2. Apply TYPE SCALE for text elements
3. Use SPACING SYSTEM for all margins/padding/gaps
4. Apply BORDER & RADIUS tokens appropriately
5. Follow INTERACTION PATTERNS for button/states
6. Ensure RESPONSIVE BEHAVIOR through flex wrapping and relative units

### Example: New Control Panel
```
Container:
  Background: var(--panel)
  Border: 1px solid var(--border)
  Border-radius: 8px
  Padding: 16px
  Gap: 12px (internal flex)

Title:
  Font-size: 1rem
  Color: var(--text)
  Margin-bottom: 8px

Button:
  Background: var(--card)
  Border: 2px solid var(--border)
  Color: var(--text)
  Padding: 8px 16px
  Border-radius: 6px
  Font-size: 0.875rem (14px)
  
  Hover/Focus:
    Background: var(--gold)
    Color: #000
    Border-color: var(--gold)
    
  Active:
    Background: var(--east-color) [or --west-color]
    Color: #000
    Border-color: var(--east-color) [or --west-color]
```
