# SakhiSetu Leader Operations — DESIGN.md

## 1. Design Identity
SakhiSetu Leader Operations is a high-trust financial and production operations console for women's Self-Help Group (SHG) leaders—modeled after an airline operations board or banking ledger, never a consumer social feed or marketing site. Every screen is mobile-first for modest Android devices over patchy connections.

**Single Typeface Family**: `IBM Plex Sans` everywhere (body, headings, tabular numbers via `font-variant-numeric: tabular-nums`). No mixing font families across screens.

---

## 2. Exact Color Tokens (Hex)

| Token | Role | Light Mode | Dark Mode |
|---|---|---|---|
| `--bg-base` | App canvas / page background | `#F4F5F7` | `#0F172A` |
| `--bg-surface` | Operational cards, tables, panels | `#FFFFFF` | `#1E293B` |
| `--bg-surface-muted` | Table headers, secondary rows | `#E8ECEF` | `#162032` |
| `--text-primary` | Primary headings, ledger figures, labels | `#0F172A` | `#F8FAFC` |
| `--text-secondary` | Supporting metadata, timestamps, hints | `#475569` | `#94A3B8` |
| `--border-neutral` | 1px / 2px structural dividers & table rules | `#CBD5E1` | `#334155` |
| `--accent-gate` | **EXCLUSIVELY** for approval-gate & money-moving actions | `#D97706` | `#F59E0B` |
| `--accent-gate-text` | Text on `--accent-gate` | `#0F172A` | `#0F172A` |
| `--status-warning` | Low-confidence extracted fields, QC flags, blockers | `#B45309` | `#FBBF24` |
| `--status-warning-bg` | Warning surface tint | `#FEF3C7` | `#451A03` |
| `--status-success` | Confirmed, QC passed, disbursed | `#047857` | `#34D399` |
| `--status-success-bg` | Success surface tint | `#D1FAE5` | `#064E3B` |
| `--status-danger` | Disputed, halted, validation error | `#B91C1C` | `#F87171` |
| `--status-danger-bg` | Error / dispute surface tint | `#FEE2E2` | `#450A0A` |

> **Strict Accent Rule**: `--accent-gate` (`#D97706` / `#F59E0B`) may NEVER be used decoratively (no badges, no chart bars, no nav highlights). It appears **only** on explicit human approval-gate and money-moving controls so its visual meaning is unmistakable.
>
> **WCAG AA Contrast Verification**: Because approval-gate button text is `16px` (`12pt`) weight `800` (below WCAG's `18.66px` / `14pt` bold large-text threshold), the `4.5:1` normal-text standard applies. Measured contrast against `--accent-gate-text` (`#0F172A`): Light mode `#D97706` = **5.60:1** (passes AA `4.5:1`); Dark mode `#F59E0B` = **8.31:1** (passes AA `4.5:1` and AAA `7.0:1`).
>
> **Buyer Portal (`frontend-buyer/`) Inheritance**: The genuinely separate `frontend-buyer` bundle reuses this exact `IBM Plex Sans` type scale and surface/text/status tokens (`--bg-base`, `--bg-surface`, `--text-primary`, `--text-secondary`, `--border-neutral`, `--status-success`, `--status-warning`) unchanged, and ships **only** the display-only summary tokens and components it uses—zero Leader-only components or `--accent-gate` approval controls are bundled into `frontend-buyer`.

---

## 3. Defined Type Scale (6 Sizes Total — No Exceptions)
No component in the Leader app may use a font size outside these 6 steps:

| Token | Size | Weight | Line Height | Usage |
|---|---|---|---|---|
| `text-scale-xs` | `12px` (`0.75rem`) | `600` | `16px` | Table column headers, status badges, timestamps |
| `text-scale-sm` | `13px` (`0.8125rem`) | `500` | `18px` | Dense table cells, solver explanations, form labels |
| `text-scale-base` | `14px` (`0.875rem`) | `500` | `20px` | Standard body text, input controls |
| `text-scale-md` | `16px` (`1rem`) | `700` | `22px` | Panel headers, order codes, approval-gate CTA text |
| `text-scale-lg` | `20px` (`1.25rem`) | `700` | `26px` | Section titles, KPI card numbers |
| `text-scale-xl` | `24px` (`1.5rem`) | `800` | `30px` | Ledger totals, primary money figures |

---

## 4. Explicit Named Bans (Forbidden Patterns)
1. **No decorative gradients** (`linear-gradient`, `radial-gradient`) anywhere in backgrounds, buttons, or headers.
2. **No glassmorphism or frosted-glass effects** (`backdrop-blur`, translucent panels).
3. **No centered hero-section layouts** with a large rounded CTA button.
4. **No decorative background blob or wave SVG shapes**.
5. **No emoji used as functional icons** — every icon uses `lucide-react` at a uniform `1.75px` stroke weight.
6. **No unstyled default shadows** — use crisp `1px` or `2px` `--border-neutral` borders for elevation and hierarchy.

---

## 5. Operational Density Principle
This is a daily operations console, not a marketing site.
- Tables use compact `8px` vertical cell padding (`py-2 px-3`) and `tabular-nums` alignment.
- Panels use `12px`–`16px` internal padding (`p-3` / `p-4`) and `12px` grid gaps (`gap-3`).
- AI extraction confidence, `source_span`, and CP-SAT solver reasons appear **inline** next to the action they govern—never hidden behind secondary drawers.

---

## 6. Mandatory 3-State Screen Checklist
Every screen and panel MUST explicitly implement and render all three non-happy states:
- [ ] **Loading state**: Explicit skeleton or loading indicator with `aria-busy="true"`.
- [ ] **Empty state**: Clear operational message + next action when zero records exist.
- [ ] **Error state**: High-contrast `--status-danger` banner with retry action and exact error detail.

---

## 7. Approval-Gate Dominance Rule
Any screen involving a money-moving or group-decision action (`Confirm Order`, `Approve Price`, `Approve Allocation`, `Approve & Send Counter-Offer`, `Evaluate Contest Window`) MUST:
1. Place the action in a dedicated **Approval Gate** container (`border-2 border-[#0F172A]`, `--bg-surface` or `#0F172A` header bar).
2. Render the primary approve button in `--accent-gate` (`#D97706`) with `--accent-gate-text` (`#0F172A`), `min-height: 44px`, `font-weight: 800`, and `text-scale-md` (`16px`), making it the single largest, highest-contrast interactive element on the screen.
3. Require explicit Radix `Dialog` confirmation (with keyboard focus trap and `Esc` support) for irreversible money/external-send actions.
