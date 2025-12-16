# Design System - n8n Management System v3.0

## Overview
This design system provides the foundation for all storyboard variations. It defines shared design tokens, typography, color palette, spacing, and component patterns that ensure consistency across all interface variations.

---

## Color Palette

### Primary Colors
```
Primary:    #0ea5e9   (sky-600)     - Primary actions, links, focus states
Secondary:  #64748b   (slate-500)   - Secondary text, borders, disabled states
```

### Status Colors
```
Success:    #10b981   (emerald-500) - Successful operations, healthy status
Warning:    #f59e0b   (amber-500)   - Warnings, pending actions
Danger:     #ef4444   (red-500)     - Errors, critical alerts, destructive actions
Info:       #3b82f6   (blue-500)    - Informational messages, tips
```

### Section Icon Colors (for visual hierarchy)
```
Dashboard:      #3b82f6   (blue-500)      - Home/overview icon
Backup:         #8b5cf6   (purple-500)    - Backup/archive icon
Notification:   #f59e0b   (amber-500)     - Bell/notification icon
Container:      #06b6d4   (cyan-500)      - Container/box icon
Flow:           #22c55e   (green-500)     - Workflow/flow icon
System:         #6366f1   (indigo-500)    - System/server icon
Settings:       #64748b   (slate-500)     - Settings/gear icon
```

### Light Theme Colors
```
Background:     #ffffff   (white)         - Main background
Surface:        #f9fafb   (gray-50)       - Secondary background
Card:           #ffffff   (white)         - Card background
Border:         #e5e7eb   (gray-200)      - Borders, dividers
Text Primary:   #111827   (gray-900)      - Primary text
Text Secondary: #6b7280   (gray-500)      - Secondary text, labels
Text Muted:     #9ca3af   (gray-400)      - Placeholder, disabled text
```

### Dark Theme Colors
```
Background:     #0f172a   (slate-950)     - Main background
Surface:        #1e293b   (slate-900)     - Secondary background
Card:           #1e293b   (slate-900)     - Card background
Card Alt:       #334155   (slate-800)     - Alternative card background
Border:         #334155   (slate-700)     - Borders, dividers
Text Primary:   #f1f5f9   (slate-100)     - Primary text
Text Secondary: #94a3b8   (slate-400)     - Secondary text, labels
Text Muted:     #64748b   (slate-500)     - Placeholder, disabled text
```

### Dashboard Heavy Dark (Neon Accent) Colors
```
Background:     #09090b   (zinc-950)      - Main background
Surface:        #18181b   (zinc-900)      - Secondary background
Card:           #27272a   (zinc-800)      - Card background
Border:         #3f3f46   (zinc-700)      - Borders, dividers
Accent Primary: #22d3ee   (cyan-400)      - Primary neon accent
Accent Second:  #c084fc   (purple-400)    - Secondary neon accent
Accent Tertiary:#f0abfc   (fuchsia-400)   - Tertiary neon accent
Text Primary:   #fafafa   (zinc-50)       - Primary text
Text Secondary: #a1a1aa   (zinc-400)      - Secondary text
```

---

## Typography

### Font Families
```
Primary:    'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif
Monospace:  'JetBrains Mono', 'Fira Code', 'Monaco', 'Courier New', monospace
```

### Font Sizes (Tailwind Scale)
```
text-xs:    0.75rem   (12px)  - Small labels, badges, timestamps
text-sm:    0.875rem  (14px)  - Body text, table cells
text-base:  1rem      (16px)  - Default body text
text-lg:    1.125rem  (18px)  - Large body text, card titles
text-xl:    1.25rem   (20px)  - Section headings
text-2xl:   1.5rem    (24px)  - Page titles
text-3xl:   1.875rem  (30px)  - Dashboard welcome headings
text-4xl:   2.25rem   (36px)  - Large stat numbers
```

### Font Weights
```
font-normal:    400   - Body text, descriptions
font-medium:    500   - Emphasized text, labels
font-semibold:  600   - Headings, buttons, active states
font-bold:      700   - Large headings, stat numbers
```

### Line Heights
```
leading-tight:   1.25   - Headings, large numbers
leading-normal:  1.5    - Body text, descriptions
leading-relaxed: 1.625  - Long-form content
```

---

## Spacing Scale (Tailwind)

### Padding & Margins
```
0:    0px     - No spacing
1:    0.25rem (4px)   - Minimal spacing
2:    0.5rem  (8px)   - Tight spacing
3:    0.75rem (12px)  - Compact spacing
4:    1rem    (16px)  - Standard spacing
5:    1.25rem (20px)  - Medium spacing
6:    1.5rem  (24px)  - Large spacing
8:    2rem    (32px)  - XL spacing
10:   2.5rem  (40px)  - Section spacing
12:   3rem    (48px)  - Large section spacing
```

### Usage Guidelines
```
Card Padding:         p-4 to p-6 (16-24px)
Section Gaps:         gap-6 to gap-8 (24-32px)
Element Spacing:      space-y-4 (16px between stacked elements)
Table Cell Padding:   px-4 py-3 (16px horizontal, 12px vertical)
Button Padding:       px-4 py-2 (16px horizontal, 8px vertical)
Modal Padding:        p-6 (24px all around)
```

---

## Border Radius

```
rounded-none:   0px      - No rounding
rounded-sm:     0.125rem (2px)  - Minimal rounding
rounded:        0.25rem  (4px)  - Subtle rounding
rounded-md:     0.375rem (6px)  - Medium rounding
rounded-lg:     0.5rem   (8px)  - Standard rounding (cards, buttons)
rounded-xl:     0.75rem  (12px) - Large rounding
rounded-2xl:    1rem     (16px) - Extra large rounding
rounded-full:   9999px   - Fully rounded (pills, avatars)
```

### Usage Guidelines
```
Cards:              rounded-lg
Buttons:            rounded-md or rounded-lg
Inputs:             rounded-md
Modals:             rounded-xl
Badges:             rounded-full or rounded-md
Status Indicators:  rounded-full
```

---

## Shadows

```
shadow-none:  none
shadow-sm:    0 1px 2px 0 rgb(0 0 0 / 0.05)
shadow:       0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)
shadow-md:    0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)
shadow-lg:    0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)
shadow-xl:    0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)
```

### Usage Guidelines
```
Cards (Light):       shadow-sm to shadow
Cards (Dark):        shadow-lg with darker shadow
Modals:              shadow-xl
Dropdowns:           shadow-lg
Hover States:        Increase shadow by one level
Focus States:        Add colored ring shadow
```

### Neon Glow Effects (Dashboard Heavy Dark)
```
Cyan Glow:      shadow-[0_0_15px_rgba(34,211,238,0.3)]
Purple Glow:    shadow-[0_0_15px_rgba(192,132,252,0.3)]
Success Glow:   shadow-[0_0_15px_rgba(16,185,129,0.3)]
Danger Glow:    shadow-[0_0_15px_rgba(239,68,68,0.3)]
```

---

## Component Patterns

### Buttons

#### Primary Button
```
Light Theme:
- Background: bg-sky-600
- Text: text-white
- Hover: bg-sky-700
- Active: bg-sky-800
- Disabled: bg-gray-300 text-gray-500
- Padding: px-4 py-2
- Border Radius: rounded-md
- Font Weight: font-medium

Dark Theme:
- Background: bg-sky-500
- Text: text-white
- Hover: bg-sky-600
- Active: bg-sky-700
- Disabled: bg-slate-700 text-slate-500
```

#### Secondary Button
```
Light Theme:
- Background: bg-white
- Border: border border-gray-300
- Text: text-gray-700
- Hover: bg-gray-50
- Active: bg-gray-100

Dark Theme:
- Background: bg-slate-800
- Border: border border-slate-600
- Text: text-slate-200
- Hover: bg-slate-700
- Active: bg-slate-600
```

#### Danger Button
```
- Background: bg-red-600
- Text: text-white
- Hover: bg-red-700
- Active: bg-red-800
```

### Cards

#### Standard Card
```
Light Theme:
- Background: bg-white
- Border: border border-gray-200
- Shadow: shadow-sm
- Padding: p-6
- Border Radius: rounded-lg
- Hover: shadow-md transition

Dark Theme:
- Background: bg-slate-900
- Border: border border-slate-700
- Shadow: shadow-lg
- Hover: border-slate-600 transition
```

#### Stat Card
```
- Includes: Large number, label, trend indicator, icon
- Icon: Colored background circle in top-right or left
- Number: text-3xl or text-4xl font-bold
- Label: text-sm text-gray-500
- Trend: Small arrow with percentage
```

#### Status Card (Container)
```
- Border-left: 4px solid [status-color]
- Status Dot: Animated pulse for active states
- Metrics: Grid layout for multiple values
- Actions: Dropdown menu in top-right
```

### Tables

#### Standard Table
```
Light Theme:
- Header: bg-gray-50 font-medium text-gray-700
- Rows: bg-white border-b border-gray-200
- Hover: bg-gray-50
- Cell Padding: px-4 py-3

Dark Theme:
- Header: bg-slate-800 font-medium text-slate-200
- Rows: bg-slate-900 border-b border-slate-700
- Hover: bg-slate-800
```

#### Table Features
```
- Sortable columns (with arrow indicators)
- Row actions (dropdown or inline buttons)
- Status badges in cells
- Pagination at bottom
- Row selection (checkboxes)
- Empty state with icon and message
```

### Forms

#### Input Fields
```
Light Theme:
- Background: bg-white
- Border: border border-gray-300
- Focus: ring-2 ring-sky-500 border-sky-500
- Error: border-red-500 ring-red-500
- Padding: px-3 py-2
- Border Radius: rounded-md

Dark Theme:
- Background: bg-slate-800
- Border: border border-slate-600
- Text: text-slate-100
- Placeholder: text-slate-400
- Focus: ring-2 ring-sky-400 border-sky-400
```

#### Labels
```
- Font Weight: font-medium
- Font Size: text-sm
- Margin Bottom: mb-2
- Color: text-gray-700 (light) / text-slate-300 (dark)
```

#### Help Text
```
- Font Size: text-sm
- Color: text-gray-500 (light) / text-slate-400 (dark)
- Margin Top: mt-1
```

#### Validation Errors
```
- Font Size: text-sm
- Color: text-red-600 (light) / text-red-400 (dark)
- Icon: Alert triangle or circle
- Display: Below field, animated slide-down
```

### Badges

#### Status Badge
```
Success:
- Background: bg-emerald-100 (light) / bg-emerald-500/20 (dark)
- Text: text-emerald-800 (light) / text-emerald-400 (dark)
- Border Radius: rounded-full
- Padding: px-2.5 py-0.5
- Font Size: text-xs
- Font Weight: font-medium

Warning:
- Background: bg-amber-100 / bg-amber-500/20
- Text: text-amber-800 / text-amber-400

Danger:
- Background: bg-red-100 / bg-red-500/20
- Text: text-red-800 / text-red-400

Info:
- Background: bg-blue-100 / bg-blue-500/20
- Text: text-blue-800 / text-blue-400
```

### Modals

#### Modal Overlay
```
- Background: bg-gray-900/50 (light) / bg-black/70 (dark)
- Backdrop Blur: backdrop-blur-sm
- Z-Index: z-50
```

#### Modal Container
```
- Width: max-w-md (small), max-w-2xl (medium), max-w-4xl (large)
- Background: bg-white (light) / bg-slate-900 (dark)
- Shadow: shadow-xl
- Border Radius: rounded-xl
- Padding: p-6
- Animation: Scale up and fade in
```

#### Modal Header
```
- Title: text-xl font-semibold
- Close Button: Top-right, hover:bg-gray-100
- Border Bottom: border-b border-gray-200
- Padding Bottom: pb-4
```

### Toast Notifications

#### Position
```
Default: top-right
Distance from edge: 4rem (64px)
Stacking: Stack vertically with gap-2
```

#### Styling
```
Success:
- Background: bg-white (light) / bg-slate-800 (dark)
- Border-left: border-l-4 border-emerald-500
- Icon: Green checkmark circle
- Shadow: shadow-lg

Error:
- Border-left: border-l-4 border-red-500
- Icon: Red X circle

Warning:
- Border-left: border-l-4 border-amber-500
- Icon: Yellow alert triangle

Info:
- Border-left: border-l-4 border-blue-500
- Icon: Blue info circle
```

#### Animation
```
Enter: Slide in from right + fade in (200ms)
Exit: Slide out to right + fade out (150ms)
Duration: 5000ms (5 seconds) or until dismissed
```

---

## Icons

### Icon Library
```
Primary: Heroicons (outline for general use, solid for active states)
Alternative: Lucide Icons
Size: 20px (w-5 h-5) for general use, 16px (w-4 h-4) for small contexts
```

### Icon Usage
```
Navigation:        24px (w-6 h-6)
Buttons:           20px (w-5 h-5)
Table Actions:     16px (w-4 h-4)
Status Indicators: 12px (w-3 h-3)
Section Headers:   24px (w-6 h-6) with colored background
```

### Icon Colors
```
Use section-specific colors for primary icons
Use gray for secondary/utility icons
Use status colors for status indicators
Use white for icons on colored backgrounds
```

---

## Transitions & Animations

### Standard Transitions
```
Default:     transition duration-150 ease-in-out
Longer:      transition duration-300 ease-in-out
Hover:       transition-colors duration-150
Transform:   transition-transform duration-200
```

### Common Animations
```
Pulse (Status):  animate-pulse (for loading/active states)
Spin (Loading):  animate-spin (for loading spinners)
Bounce:          animate-bounce (for notifications)
Fade In:         opacity-0 to opacity-100
Slide In:        translate-x-4 to translate-x-0
```

### Loading States
```
Skeleton:
- Background: bg-gray-200 (light) / bg-slate-700 (dark)
- Animation: animate-pulse
- Border Radius: Same as component being loaded

Spinner:
- Size: 20px for buttons, 32px for page loading
- Color: Inherits from context
- Animation: animate-spin
```

---

## Accessibility

### Color Contrast
```
All text must meet WCAG 2.1 AA standards:
- Normal text: Minimum 4.5:1 contrast ratio
- Large text: Minimum 3:1 contrast ratio
- UI components: Minimum 3:1 contrast ratio
```

### Focus States
```
All interactive elements must have visible focus indicators:
- Ring: ring-2 ring-sky-500 ring-offset-2
- Ring (Dark): ring-2 ring-sky-400 ring-offset-2 ring-offset-slate-900
- Outline: For elements that can't use ring
```

### Keyboard Navigation
```
- All interactive elements must be keyboard accessible
- Tab order must be logical
- Skip links for main content
- Escape to close modals/dropdowns
- Arrow keys for menu navigation
```

### Screen Readers
```
- Use semantic HTML (nav, main, aside, etc.)
- ARIA labels for icon-only buttons
- ARIA live regions for dynamic updates
- Alt text for all images
- Role attributes where appropriate
```

---

## Responsive Breakpoints

### Breakpoint Definitions
```
sm:   640px   - Small tablets, large phones (landscape)
md:   768px   - Tablets
lg:   1024px  - Small laptops, large tablets (landscape)
xl:   1280px  - Laptops, desktops
2xl:  1536px  - Large desktops, external monitors
```

### Layout Behavior
```
Mobile (< 640px):
- Single column layout
- Stacked cards
- Bottom navigation or hamburger menu
- Full-width modals
- Simplified tables (card view)

Tablet (640px - 1024px):
- 2-column grid for cards
- Collapsible sidebar (icon-only)
- Side-panel modals
- Tables with horizontal scroll

Desktop (> 1024px):
- 3-4 column grid for cards
- Full sidebar with labels
- Multi-column tables
- Overlay modals
- Side-by-side panels
```

---

## Grid System

### Container
```
Max Width: max-w-7xl (1280px)
Padding: px-4 sm:px-6 lg:px-8
Margin: mx-auto
```

### Grid Layouts
```
Card Grid:
- Mobile: grid-cols-1
- Tablet: grid-cols-2
- Desktop: grid-cols-3 or grid-cols-4
- Gap: gap-6

Dashboard Stats:
- Mobile: grid-cols-1
- Tablet: grid-cols-2
- Desktop: grid-cols-4
- Gap: gap-4
```

---

## Data Visualization

### Chart Colors (Sequential)
```
Primary Series:   #0ea5e9 (sky-600)
Secondary Series: #8b5cf6 (purple-500)
Tertiary Series:  #06b6d4 (cyan-500)
Fourth Series:    #22c55e (green-500)
```

### Chart Colors (Status)
```
Success: #10b981 (emerald-500)
Warning: #f59e0b (amber-500)
Danger:  #ef4444 (red-500)
```

### Chart Styling
```
Grid Lines:       Subtle gray (#e5e7eb light / #334155 dark)
Axis Labels:      text-sm text-gray-600
Tooltips:         bg-white shadow-lg border with white text
Legend:           Positioned top-right or bottom
Animation:        Smooth transitions on data updates
```

---

## Best Practices

### Performance
```
- Use CSS transforms for animations (not positioning)
- Lazy load images and heavy components
- Debounce search inputs
- Throttle scroll events
- Use CSS variables for theme switching
```

### Consistency
```
- Use design tokens, never hard-coded values
- Maintain consistent spacing throughout
- Use the same component for the same purpose
- Follow naming conventions
- Reuse components across views
```

### User Experience
```
- Provide immediate feedback for all actions
- Show loading states for async operations
- Display helpful error messages
- Use optimistic UI updates where appropriate
- Maintain state when navigating between views
```

---

## Implementation Notes

### CSS Organization
```
Use Tailwind utility classes for most styling
Create custom components for repeated patterns
Use @apply for complex component styles
Leverage Tailwind's JIT mode for custom values
```

### Dark Mode Implementation
```
Use Tailwind's dark: variant
Store preference in localStorage
Respect system preference by default
Provide manual toggle switch
Smooth transition between themes
```

### Component Library Structure
```
/components
  /ui           - Basic components (Button, Input, Card)
  /layout       - Layout components (Sidebar, Header, Container)
  /dashboard    - Dashboard-specific components
  /charts       - Chart components
  /modals       - Modal dialogs
  /forms        - Form components
```

---

This design system provides the foundation for all storyboard variations. Each storyboard will apply these tokens with specific layout approaches and visual styles.
