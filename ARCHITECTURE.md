# SakhiSetu — Production Architecture

## 1. System Overview
SakhiSetu is a production operations, fair-allocation, quality-control, and group-governed payout platform for women's Self-Help Groups (SHGs).

### Non-Negotiable Product & Engineering Boundaries
1. **Member Self-Verification**: Every member can view or hear (via replayable WhatsApp thread or Exotel voice read-back in her own language, e.g. Kannada/Hindi) her own work and pay record without intermediation.
2. **Group-Governed Payouts**: No payout moves without explicit group review-committee sign-off and a visible group-wide notice + contest window.
3. **No Silent Assumptions (§2)**: Every state transition that moves money, finalizes an allocation, or closes a group decision requires an explicit, logged `Approval` record. Timeouts never manufacture approval.
4. **Data-Layer Buyer Isolation (§6, §12)**: The Buyer portal is both a separate database/API projection (`buyer_order_summary_v`) and a **genuinely separate frontend bundle (`frontend-buyer/`)** that never contains member identities, assignments, or individual compensation in its JavaScript payload or API responses.

---

## 2. State Machine Model (§2 & §7)
To resolve the tension between §2 (no timeout-based approval) and §7 (post-approval contest window), the state machine (`backend/app/services/state_machine.py`) enforces **two distinct transition classes**:

| Transition Class | Behavior | Examples |
|---|---|---|
| `EXPLICIT_APPROVAL_REQUIRED` | Requires an existing, persisted `Approval` row referencing the target entity and transition. **No timer or background job can trigger this transition.** | `DRAFT -> CONFIRMED`, `ALLOCATION_PROPOSED -> ALLOCATION_APPROVED`, `BLOCKED -> RECOVERY_APPROVED`, `QC_FLAGGED -> QC_RESOLVED`, `PAYOUT_PENDING -> PAYOUT_APPROVED`, `DISPUTED -> RESOLVED` |
| `TIME_GATED_CONTEST_WINDOW` | Only valid *out of* an already-explicitly-approved state (`PAYOUT_APPROVED -> DISBURSED`). Checks that `contest_window_ends_at <= now` AND `open_contests_count == 0`. If any member raises a `Contest` during the window, the payout halts into `DISPUTED` (`EXPLICIT_APPROVAL_REQUIRED` to resolve). | `PAYOUT_APPROVED -> DISBURSED` |

---

## 3. Multi-Channel Convergence (§3)
All three front doors normalize into a single `InboundMessage` record before any interpretation:
- **WhatsApp (Gupshup / Karix BSP)**: Text, voice notes, photos, interactive buttons/lists.
- **Voice / DTMF (Exotel)**: Basic-phone IVR with ExoML, DTMF digit capture, and voice-note recording.
- **JanAI Café**: Assisted-entry PWA route (`/cafe`) with operator consent logging.

Every outbound member prompt follows the fixed 3-part grammar:
1. **Fact**: What the system observed/recorded.
2. **Action**: What decision or step is needed.
3. **Request**: Channel-appropriate response (tappable WhatsApp buttons vs. spoken DTMF keypad prompt — never a keypress instruction on a button-only channel).

---

## 4. AI, Speech & Solver Stack
- **Orchestration**: Lyzr Python ADK (`Manager Agent` + `SuperFlow`) tracing every pipeline step (`identify`, `normalize`, `route`, `extract`, `clarify`, `explain_allocation`, `escalate`) as individual `AgentEvent` records.
- **Speech (ASR/TTS)**: **Bhashini** (MeitY government-backed multilingual API for Kannada, Hindi, Tamil, etc.) as primary engine, with Sarvam AI / Google STT fallback adapter.
- **Vision**: Scoped strictly to intake PO/reference-photo OCR. **Automated QC defect classification is intentionally not built**; `QualityClassifierPort` provides a clean seam for future opt-in integration.
- **Allocation Solver**: **Google OR-Tools CP-SAT** (`backend/app/services/planner.py`) — stateless, pure-constraint solver. Assignment explanations are computed directly from solver constraint slack, capacity utilization, and counterfactual feasibility checks (why alternative members were ineligible or higher-cost).
- **Cost & Usage Metering (§9)**: Every LLM token, Bhashini/fallback ASR/TTS minute, and Exotel/WhatsApp call/message is metered into `UsageMeter` keyed by `shg_id` and billing period (`YYYY-MM`).

---

## 5. Security & Privacy
- **Encryption at Rest**: Sensitive member PII (phone numbers, bank account/IFSC, Aadhaar-last4 if any) encrypted at the application/DB boundary using Fernet (`cryptography`) with `SAKHI_ENCRYPTION_KEY`, plus SHA-256 deterministic blind-index hashes for phone-number lookup without decrypting the table.
- **Consent Gate (§8)**: Exporting bank-ready payout files or sharing group data with buyers/federations requires a persisted `ConsentEvent` before the service will release bytes.
- **Rotation Integrity (§7)**: `ReviewRotation` uses a seeded, auditable pseudo-random selection (`sha256(entity_id + cycle + group_epoch)`) stored on the record. Members can opt out ("pass"), which deterministically reshuffles. Leader-assigned payout rotation is structurally absent.
