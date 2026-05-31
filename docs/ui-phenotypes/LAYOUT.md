# World Sim UI Layout Patterns

## Overview
Documentation of layout systems and structural patterns observed in World Sim interfaces.

## Layout Systems

### 1. Flex-Based Layout
**Primary Layout System**: Both interfaces use CSS Flexbox for primary layout arrangements.

**Dashboard (sim.html)**:
- Header: `display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1.5rem;`
- Logo section: Flex column implied by structure
- Overall: Header flex with main content area below

**Map (map-v2.html)**:
- Header: `display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1rem;`
- Nav links: `display: flex;` (implied)
- Map controls: `display: flex; gap: 1rem; flex-wrap: wrap;`
- Overall: Header + map visualization + controls sections

### 2. Section-Based Layout
Both pages follow a clear sectional structure:
1. Header/Navigation
2. Main Content Area
3. Controls/Footers (where applicable)

### 3. Card-Based Content Organization
Content is grouped into visually distinct cards/containers:
- Defined borders and background colors
- Consistent border-radius
- Padding internal to cards
- Margin between cards following 4px grid

## Breakpoints and Responsive Behavior

### Observed Responsive Patterns
While no explicit media queries were found in the style tags, the layouts use responsive techniques:

1. **Flex Wrapping**: `flex-wrap: wrap;` allows items to flow to new lines
2. **Gap Properties**: `gap` replaces margin hacks for consistent spacing
3. **Relative Units**: Use of `rem` units (based on font size) for scalability
4. **Min/Max Sizing**: Implicit through content constraints

### Breakpoint-Informed Design
Although no breakpoints are defined in CSS, the layouts suggest these considerations:
- **Mobile (< 640px)**: Single column stacking, full-width elements
- **Tablet (640px-1024px)**: Mixed layouts, some side-by-side where space allows
- **Desktop (> 1024px)**: Full multi-column layouts possible

## Grid and Alignment Systems

### Implicit 4px Grid
All measurements align to a 4px base grid:
- Padding: 8px, 12px, 16px, 20px, 24px, 32px, 40px
- Margin: Following same pattern
- Gap: 8px, 12px, 16px, 24px
- Font sizes: 12px, 14px, 18px, 24px, 32px
- Border widths: 2px, 3px
- Border radius: 6px, 8px, 10px

### Alignment Patterns
- **Horizontal**: `justify-content: space-between`, `space-around`, `center`, `flex-start`, `flex-end`
- **Vertical**: `align-items: center`, `start`, `end`, `baseline`, `stretch`
- **Text alignment**: `text-align: left`, `center`, `right` (where specified)

## Z-Index and Layering

### Observed Layering
While no explicit z-index values were found, the layout implies:
1. **Background**: Map visualization or page background
2. **Content**: Cards, panels, main information
3. **Overlays**: Popups, modals (not observed but implied for future)
4. **Foreground**: Tooltips, dropdowns, temporary UI

### Layering Guidelines
- Use consistent z-index values if implementing layered UI
- Reserve negative values for rare background elements
- Use 1000+ for modal/overlay systems
- Use 10000+ for system-level UI (tooltips, notifications)

## Scrolling and Overflow

### Observed Patterns
- Main content areas appear to allow natural scrolling
- No custom scrollbar styling observed
- Overflow likely handled through browser defaults

### Guidelines
- Allow natural scrolling for long content
- Consider custom scrollbars only if branding requires
- Ensure touch scrolling works smoothly
- Avoid disabling scroll entirely on scrollable content

## Page Structure Templates

### Dashboard Layout Template
```
-------------------------------------------------
|           HEADER (flex, space-between)        |
|  LOGO SECTION   |   NAV/ACTIONS   | USER INFO |
-------------------------------------------------
|                                               |
|              MAIN CONTENT AREA              |
|  [CARD] [CARD] [CARD]                       |
|  [CARD] [CARD]                              |
|                                               |
-------------------------------------------------
|           FOOTER/CONTROLS (if present)        |
-------------------------------------------------
```

### Map Layout Template
```
-------------------------------------------------
|           HEADER (flex, space-between)        |
|   TITLE   |      NAV LINKS      |  ACTIONS  |
-------------------------------------------------
|                                               |
|              MAP VISUALIZATION              |
|                                               |
|                                               |
|                                               |
-------------------------------------------------
|        MAP CONTROLS (flex, wrap, gap)       |
|  [BTN] [BTN] [BTN] [BTN]  [MORE CONTROLS]   |
-------------------------------------------------
```

## Implementation Guidelines

### Do's
1. Use flexbox for primary layout arrangements
2. Apply the 4px spacing grid consistently
3. Use relative units (rem, em, %) for scalability
4. Implement flex-wrap for responsive behavior
5. Maintain consistent alignment patterns
6. Consider touch target sizes in layout planning
7. Allow natural content flow where possible

### Don'ts
1. Don't use absolute positioning for main layout structures
2. Don't use fixed pixel widths that break responsiveness
3. Don't override natural scrolling without good reason
4. Don't create layouts that require horizontal scrolling on mobile
5. Don't ignore accessibility in layout decisions (tab order, screen reader flow)
6. Don't use floats for layout when flexbox/grid is available
7. Don't sacrifice clarity for novelty in layout choices

## Specific Component Layouts

### Header Layout
```
[LOGO/BRANDING]  [SPACER]  [NAVIGATION/ACTIONS]  [USER/SYSTEM]
```
- Space-between distribution
- Wrapping on narrow screens
- Vertically centered content

### Card Layout
```
+---------------------------+
|  HEADER (if present)      |
|                           |
|  CONTENT AREA             |
|  [text, images, etc.]     |
|                           |
|  FOOTER/ACTIONS (if used) |
+---------------------------+
```
- Consistent padding
- Clear visual hierarchy
- Defined boundaries

### Button Group Layout
```
[BTN1] [BTN2] [BTN3] [SPACER] [MORE BTNS]
```
- Consistent sizing
- Equal or proportional spacing
- Wrapping behavior for overflow
- Visual distinction for primary/secondary actions
