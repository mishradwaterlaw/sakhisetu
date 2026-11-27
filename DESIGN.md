# SakhiSetu Leader Operations — DESIGN.md

## 1. Design Identity
SakhiSetu Leader Operations is a high-trust financial and production operations console for women's Self-Help Group (SHG) leaders—modeled after an airline operations board or banking ledger, never a consumer social feed or marketing site. Every screen is mobile-first for modest Android devices over patchy connections.

**Single Typeface Family**: `IBM Plex Sans` everywhere (body, headings, tabular numbers via `font-variant-numeric: tabular-nums`). No mixing font families across screens.

---

## 2. Workspace palette

The leader and buyer interfaces use a warm neutral canvas, white panels, burgundy navigation and the SakhiSetu lotus mark. Keep the buyer portal in its own bundle and use group-level order summaries there.

| Token | Role | Light theme |
|---|---|---|
| `--bg-base` | Workspace canvas | `#FAF8F7` |
| `--bg-surface` | Cards and forms | `#FFFFFF` |
| `--bg-surface-muted` | Table headers and supporting details | `#F8F5F4` |
| `--text-primary` | Headings and figures | `#30242C` |
| `--text-secondary` | Metadata and hints | `#736A6E` |
| `--border-neutral` | Panel borders and table dividers | `#E7DFE0` |
| `--brand` | Primary actions and links | `#922E52` |
| `--brand-dark` | Page headings and decision panels | `#68203B` |
| `--accent-gate` | Human approval controls | `#D97706` |
| `--accent-gate-text` | Approval button text | `#0F172A` |
| `--status-warning` / `--status-warning-bg` | Uncertain fields and blockers | `#8C571C` / `#FFF2DC` |
| `--status-success` / `--status-success-bg` | Passed checks and confirmed decisions | `#31664D` / `#E9F3EC` |
| `--status-danger` / `--status-danger-bg` | Disputes and errors | `#9D3047` / `#FFEDF0` |

Reserve the solid amber approval color for explicit decisions. Pair status colors with readable labels. Use the local shadcn/ui primitives for leader buttons, dialogs, tables, tabs and badges.

## 3. Typography

Bundle IBM Plex Sans with each frontend. Use tabular numbers for quantities, currency and chart values. Reserve the largest type for page titles and summary figures. Keep operational text at 13–16px and use smaller labels for chart axes, timestamps and table headers.

## 4. Visual hierarchy

Use thin borders and restrained rose, sage, lavender and amber tints to distinguish actions and statuses. Use Lucide icons at 1.75px stroke width. Keep the workshop illustration in the welcome panel and use a translucent area fill to distinguish the plotted delivery series.

## 5. Responsive layout

Keep the main navigation visible beside the workspace on desktop. At narrower widths, move it into the keyboard-accessible navigation dialog. Stack the order detail below the register when both panels cannot fit comfortably. Allow wide tables to scroll inside their own containers. Show extraction confidence, source text and allocation explanations alongside the order decision they support.

## 6. Mandatory 3-State Screen Checklist
Every screen and panel MUST explicitly implement and render all three non-happy states:
- [ ] **Loading state**: Explicit skeleton or loading indicator with `aria-busy="true"`.
- [ ] **Empty state**: Clear operational message + next action when zero records exist.
- [ ] **Error state**: High-contrast `--status-danger` banner with retry action and exact error detail.

---

## 7. Approval-Gate Dominance Rule
Any screen involving a money-moving or group-decision action (`Confirm Order`, `Approve Price`, `Approve Allocation`, `Evaluate Contest Window`) MUST:
1. Place the action in a dedicated decision panel or confirmation dialog. Use the dark burgundy surface to identify the next order decision.
2. Render the primary approve button in `--accent-gate` (`#D97706`) with `--accent-gate-text` (`#0F172A`), `min-height: 44px`, `font-weight: 800`, and `text-scale-md` (`16px`), making it the single largest, highest-contrast interactive element on the screen.
3. Require explicit Radix `Dialog` confirmation (with keyboard focus trap and `Esc` support) for irreversible money/external-send actions.
