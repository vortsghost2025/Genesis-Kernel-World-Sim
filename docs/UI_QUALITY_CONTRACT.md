# World Sim UI Quality Contract

## Purpose
This contract defines the minimum quality standards for all UI work in the Genesis-Kernel-World-Sim project. It establishes concrete, measurable criteria that must be met before any UI-related task can be considered complete.

## Core Principles

### 1. HTTP 200 is NOT UI Success
- A successful HTTP response only indicates network connectivity, not UI quality
- UI success requires visual correctness, usability, and adherence to design standards
- All UI tasks must include visual validation beyond basic functionality tests

### 2. DOM Selectors Existing is NOT UI Success
- The presence of HTML elements in the DOM does not constitute a quality UI
- Elements must be visually correct, properly styled, and usable
- UI validation requires visual inspection, not just presence checks

## Mandatory Requirements

### Visual Validation
✅ **Every UI task MUST include:**
- Desktop screenshot (1920x1080 or equivalent)
- Mobile screenshot (375x667 or equivalent, iPhone 8/X/11/12/13 baseline)
- Screenshots must be saved in `docs/ui-phenotypes/screenshots/` with descriptive filenames
- Screenshots must show the actual rendered UI, not placeholders or wireframes

### Text and Readability
✅ **No overlapping text:**
- All text must have sufficient clear space around it
- No text may overlap with other text, icons, or graphical elements
- Line height must be sufficient to prevent overlapping between lines

✅ **No tiny unreadable map labels:**
- All text must be at least 12px in size for body/content text
- Labels on maps or charts must be legible at normal viewing distances
- Text must maintain adequate contrast against its background (≥ 4.5:1 for body text)

### Content and Information Hierarchy
✅ **No hardcoded future/locked places visible by default:**
- Future content, locked features, or unavailable options must not be visible in the default view
- Locked/hidden content should be appropriately obscured or disabled with clear affordances
- Default view should only show currently accessible/available simulation elements

✅ **No provider/debug/admin text in user-facing views:**
- API keys, provider URLs, debug logs, or administrative information must never appear in user interfaces
- Development-only information must be properly segregated behind authentication or feature flags
- Error messages shown to users must be user-friendly, not technical stack traces

### Information Clarity
✅ **Default screen must answer: "What is this, what matters, what do I do next?":**
- Every screen must have a clear, immediately understandable purpose
- Primary information/actions must be visually prominent
- Secondary information must be visually subordinate but still accessible
- Users should not need to hunt for basic information or wonder what to do

## Specific World Sim Requirements

### Dashboard-Specific
- Creator dashboard must clearly show both hemisphere states at a glance
- Resource levels, population counts, and key metrics must be prominently displayed
- Alerts and notifications must be visually distinct but not overwhelming
- Time controls must be obvious and easy to use

### Map-Specific
- Map visualization must remain the dominant visual element
- UI controls must not obscure significant portions of the map
- Hemisphere distinctions must be immediately visible through color coding
- Map legend and scale must be present and readable
- Navigation controls must be intuitive and responsive

### Cross-Cutting
- All text must use the defined typography scale from UI_TOKENS.md
- All colors must come from the defined palette in UI_TOKENS.md
- All spacing must adhere to the 4px grid system
- Interactive elements must provide clear visual feedback for hover, focus, and active states
- Loading states must be clearly indicated when data is being fetched
- Empty states must be helpful and guide users toward meaningful actions

## Validation Process

### Before Marking UI Tasks Complete:
1. Manually inspect the UI in both desktop and mobile viewports
2. Take and save required screenshots to `docs/ui-phenotypes/screenshots/`
3. Verify all requirements in this contract are met
4. Check against the World Sim UI Skills (WORLD_SIM_DASHBOARD_SKILL.md, WORLD_SIM_MAP_SKILL.md)
5. Confirm no contract violations exist
6. Only then mark the task as complete

### Screenshot Requirements:
- Filename format: `[component]-[viewport]-[timestamp].png` (e.g., `dashboard-desktop-20260531-1430.png`)
- Include both light and dark theme variants if applicable
- Show meaningful interaction states (hover, focus, active) where relevant
- File format: PNG for lossless quality
- Maximum file size: 5MB per screenshot

## Enforcement
- UI tasks violating this contract will be reopened until compliance is achieved
- Automated visual regression testing should be implemented where possible
- Peer review of UI changes must include contract compliance verification
- Contract violations found in production will be treated as severity-level bugs
