# UI Review Gate - Copy-Paste Prompt

## Instructions
Copy and paste the entire prompt below into your conversation with the AI when reviewing UI work. The AI should respond with specific findings for each checklist item.

---

Please review the following UI work against the World Sim UI Quality Contract and provide specific findings for each item:

## UI Quality Contract Verification

### 1. Visual Validation
- [ ] Desktop screenshot provided and saved to docs/ui-phenotypes/screenshots/
- [ ] Mobile screenshot provided and saved to docs/ui-phenotypes/screenshots/
- [ ] Screenshots show actual rendered UI (not placeholders/wireframes)
- [ ] Screenshots have descriptive filenames

### 2. HTTP 200 is NOT UI Success
- [ ] Visual correctness verified beyond basic functionality
- [ ] UI adherence to design standards confirmed
- [ ] More than just network connectivity checked

### 3. DOM Selectors Existing is NOT UI Success
- [ ] Visual correctness of elements confirmed
- [ ] Proper styling verified
- [ ] Usability assessed beyond mere presence

### 4. Text and Readability
- [ ] No overlapping text detected
- [ ] All text ≥12px for body/content
- [ ] Map labels are readable at normal viewing distances
- [ ] Text contrast ≥ 4.5:1 against backgrounds

### 5. Content Restrictions
- [ ] No hardcoded future/locked places visible by default
- [ ] No provider/debug/admin text in user-facing views
- [ ] Default view shows only currently accessible elements

### 6. Information Clarity
- [ ] Screen purpose is immediately understandable
- [ ] Primary information/actions are visually prominent
- [ ] Secondary information is appropriately subordinate
- [ ] Clear answer to: "What is this, what matters, what do I do next?"

## World Sim Specific Checks

### Dashboard (if applicable)
- [ ] Both hemisphere states clearly visible
- [ ] Resource levels/prominent metrics displayed
- [ ] Alerts/notifications visually distinct but not overwhelming
- [ ] Time controls obvious and easy to use

### Map (if applicable)
- [ ] Map visualization remains dominant visual element
- [ ] UI controls do not obscure significant map portions
- [ ] Hemisphere distinctions immediately visible via color coding
- [ ] Map legend and scale present and readable
- [ ] Navigation controls intuitive and responsive

### Cross-Cutting
- [ ] All text uses defined typography scale (UI_TOKENS.md)
- [ ] All colors from defined palette (UI_TOKENS.md)
- [ ] All spacing adheres to 4px grid system
- [ ] Interactive elements provide clear visual feedback
- [ ] Loading states clearly indicated when applicable
- [ ] Empty states helpful and action-guiding

## Screenshot Requirements Verification
- [ ] Filename format: [component]-[viewport]-[timestamp].png
- [ ] Both light and dark variants included if applicable
- [ ] Meaningful interaction states shown where relevant
- [ ] Format: PNG, Maximum size: 5MB per screenshot

## Final Assessment
Based on the above checks:
- [ ] ALL requirements met - UI can be marked complete
- [ ] SOME requirements not met - UI requires revision
- [ ] MANY requirements not met - Significant rework needed

## Specific Issues Found
[List any specific violations or issues discovered during review]

## Required Actions Before Completion
[List specific actions needed to bring UI into compliance]

---

Please provide your detailed findings for each checkbox above and conclude with whether the UI meets the quality contract standards.
