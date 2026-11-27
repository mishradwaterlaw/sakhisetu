# SakhiSetu

Production coordination, fair task allocation, quality control, and group-governed payout software for women's Self-Help Groups (SHGs).

From a buyer's order to every member's payout, SakhiSetu gives the group one shared record that every member can hear in her own language, verify on her own terms, and approve together.

---

## Quickstart

### Start both apps locally

Start Docker Desktop, or Docker Engine with the Compose v2 plugin. Clone or download the branch you want to try and open a terminal in the folder containing `docker-compose.yml`.

On a fresh clone, create the local environment file once. The example uses sandbox providers and works with the included demo data.

```sh
cp .env.example .env
```

Run this command for the first launch and again after pulling changes. Compose rebuilds both frontends and the API, starts PostgreSQL and Redis, and waits for the services to become healthy.

```sh
docker compose up --build -d --wait
```

| App | Local URL |
| --- | --- |
| Leader dashboard | [http://localhost:5173](http://localhost:5173/) |
| Buyer portal | [http://localhost:5174](http://localhost:5174/) |

The first launch seeds Kaveri Mahila Sangha, five members, and a sample draft order. Use `docker compose ps` to check service health. Use `docker compose down` to stop the local stack and keep its database for next time.

### Share a live demo

Friends who run their own copy can use the localhost links above. To let friends try the demo in a browser on your running stack, start the optional Cloudflare tunnels. Use sample data for this option because anyone with a tunnel URL can reach that app and its API.

```sh
docker compose --profile tunnel up -d --wait tunnel-leader tunnel-buyer
docker compose logs --tail=50 tunnel-leader
docker compose logs --tail=50 tunnel-buyer
```

Share the `https://…trycloudflare.com` URL from each service’s log and label it **Leader dashboard** or **Buyer portal**. Keep Docker running while friends try the apps. To end public sharing while continuing locally, run `docker compose --profile tunnel stop tunnel-leader tunnel-buyer`.

---

## The Problem

A single bulk production order can break an informal group in several places at once.

Consider a typical 12-member stitching group. A buyer asks for 120 stitched pouches in 3 days. The group leader splits the work verbally and tracks it in a notebook. On day 2, one member's sewing machine breaks, so she can finish only 10 of her 28 pouches. The leader only finds out on the final day when output is gathered for shipping. By then, the order is short, the price was guessed rather than calculated, and nobody has an independent record of who earned what.

Field visits and published research (SEWA/WIEGO, TNAU, and SHG-bank linkage reviews) highlight five recurring failure modes:
1. **Verbal splitting and silent overload**: Tasks live in memory or notebooks, so the same few members quietly absorb extra rush work while others are sidelined.
2. **Late blocker discovery**: Problems surface only at final consolidation, when it is too late to reassign capacity.
3. **Underpricing by guesswork**: Material, labour, overhead, and margin are rarely itemized, leading to 30% to 40% underpricing.
4. **Opaque payouts**: Members cannot independently verify their own work and pay record in their own language, eroding trust in group accounting.
5. **Upstream and credit exclusion**: Roughly 60% of surveyed SHG members struggle to buy raw material in small lots at fair prices, and bank loans stall due to missing paperwork and low literacy. Members on basic keypad phones or without phones at all are left out of smartphone-only tools.

---

## Solution Overview

SakhiSetu separates what AI is good at from what must be deterministic and what must be decided by humans:

- **Agents where input is messy (Lyzr Python ADK + Bhashini + Vision OCR)**: Converts unstructured WhatsApp texts, regional-language voice notes, purchase-order photos, and assisted entries into structured order drafts, task graphs, and blocker reports, while logging every step as an `agent_event`.
- **Exact code where numbers and constraints matter (OR-Tools CP-SAT + PostgreSQL + Cost Engine)**: Solves fair work allocation across skills, hours, tools, and materials; computes minimum viable prices down to the rupee; and maintains a relational ledger.
- **Human gates before anything commits**: Nothing that moves money, finalizes an allocation, sends an external negotiation message, or closes a group decision proceeds on a timeout or silent assumption. Every such transition requires an explicit, logged human approval.

---

## How SakhiSetu Works

### 1. Three Front Doors, One Intake Pipeline
Orders, blocker reports, finished-work photos, and clarification replies arrive through three channels and converge into a single `inbound_message` pipeline:
- **WhatsApp Business API (Gupshup / Karix)**: Text, voice notes, photos, and tappable interactive buttons for smartphone users, leaders, and buyers.
- **Programmable Voice and DTMF (Exotel)**: Spoken prompts and keypad responses (`Press 1`, `Press 2`) for members on basic phones with no data access, powered by **Bhashini** (primary Indian multilingual ASR/TTS for Kannada, Hindi, Tamil, and others) with a Sarvam AI commercial fallback.
- **JanAI Cafe Assisted Entry**: A simplified operator view (`/cafe` tab) for members with no phone at all, requiring explicit member consent on every submission.
- **Manual Leader Entry**: A web form in the Leader Desk that enters the exact same `DRAFT` review pipeline rather than bypassing confirmation.

Every inbound message is durably stored before processing. Unknown senders are quarantined (never silently turned into orders) with direct onboarding actions in the leader's inbox. Photo inputs are disambiguated between purchase-order documents (routed to OCR) and sample/finished-work photos (attached as quality rubric candidates); ambiguous photos trigger a channel-appropriate clarification prompt rather than a guess.

### 2. Fair, Explainable Task Allocation (OR-Tools CP-SAT)
Once an order is confirmed and priced, a stateless CP-SAT solver assigns tasks (`cut`, `stitch`, `check_and_pack`) across members:
- **Hard constraints**: Required skill match, required tool availability, material inventory feasibility, and each member's daily available minutes ceiling.
- **Fairness and soft workload preferences**: Minimizes peak utilization across the group. Members can optionally set a workload preference (`standard`, `more`, or `less`), which acts strictly as a soft constraint after hard constraints are satisfied.
- **Anti-favoritism guardrail**: If a member absorbs the maximum share in consecutive cycles, the solver surfaces a visible fairness warning to the leader.
- **Solver-grounded explanations**: Every assignment reason is generated directly from solver utilization, slack minutes, and counterfactual ineligibility checks. If a member stated `more` or `less` and received zero units (for example due to a missing skill or tool), the planner emits a zero-unit explanation record stating her preference was recorded and citing the exact disqualifying constraint.

### 3. Pricing, Supplier Comparison, and Counter-Offer Drafting
- **Minimum Viable Price**: Computes material cost, labour (from task minutes and wage benchmarks), overhead, and target margin alongside the buyer's offer. Any non-live parameter (such as market trend adjustment) is explicitly labeled as a configured placeholder assumption.
- **Supplier Comparison**: Compares quotes from known suppliers side by side on unit price, minimum order quantity, total cost, and delivery days using the same cost engine.
- **Counter-Offer Drafting**: When a buyer's offer falls below the minimum viable price, the system drafts a counter-offer citing the real cost breakdown. The leader always reviews, edits, and confirms dispatch in a modal dialog; no external message is ever sent automatically.

### 4. Early Recovery and Quality Control
- **Blocker Recovery**: Members can report machine breakdowns or delays at any time via WhatsApp, keypad call, or JanAI Cafe. The system generates ranked recovery options (such as reassigning remaining units to members with free capacity or extending the deadline), and waits for explicit leader sign-off.
- **Quality Rubric and Human-Assisted Photo QC**: Leader and buyer agree on concrete rubric criteria and reference photos before work starts; disagreements are flagged as an explicit risk on the order. Finished pieces are photographed by members and reviewed side-by-side by a rotating checker or leader (automated visual pass/fail classification is intentionally excluded). Repeat defects generate private coaching notes visible only to that member.

### 5. Group-Governed Payouts and Two-Type State Machine
SakhiSetu enforces two distinct state-machine transition types in code:
- **`EXPLICIT_APPROVAL_REQUIRED`**: Transitions such as `DRAFT -> CONFIRMED`, `ALLOCATION_PROPOSED -> ALLOCATION_APPROVED`, and `PAYOUT_PENDING -> PAYOUT_APPROVED` require a persisted `Approval` row. No timer or background job can advance them.
- **`TIME_GATED_CONTEST_WINDOW`**: Only applies out of an already-approved payout (`PAYOUT_APPROVED -> DISBURSED`). Once the rotating review committee (2 to 3 members selected by an auditable seeded pseudo-random rotation, with opt-out reshuffling and no leader-assignment option) approves the payout:
  1. Every member receives a group-wide notice while review is pending, and a group-level approval broadcast before any individual earnings read-back.
  2. Individual earnings read-backs are stored as replayable records in each member's language.
  3. A bounded contest window opens for all members. Any objection halts disbursement and moves the batch to `DISPUTED` until explicitly resolved.

### 6. Federation Operations and Credit Readiness
- **Pooled Material Buying**: Aggregates small-lot material requests across multiple SHGs under one federation using the supplier comparison engine while keeping each SHG's financial ledger strictly separate (supported by two independent field-research citations).
- **Neutral Quality Dispute Escalation**: Allows contested quality flags to escalate to a federation-level reviewer (`OPEN -> FEDERATION_REVIEW -> RESOLVED_UPHELD | RESOLVED_DISMISSED`), closing the neutrality gap when a member contests a flag raised by her own leader.
- **Bank-Ready Creditworthiness Summary**: Generates a group-level history (completed orders, group quality score, payout consistency) containing zero individual member names or payout amounts. External sharing to a bank or federation is blocked unless a group-approved `ConsentEvent` exists.

### 7. Structural Privacy and Cost Metering
- **Buyer Isolation**: The Buyer Portal is both a restricted PostgreSQL view (`buyer_order_summary_v`) and a completely separate frontend bundle (`frontend-buyer/`) that never receives individual member identities, assignments, or compensation.
- **Member-to-Member Privacy**: Member read-back endpoints enforce `require_member_self` at the data-access layer so no member can query another member's earnings, quality notes, or task details.
- **Field-Level Encryption and Usage Metering**: Phone numbers and bank details are encrypted at rest with Fernet and indexed via keyed SHA-256 blind indexes. Every LLM token, speech minute, and channel message is metered in `usage_meters` per SHG per month to verify the economics of the free-to-leader model.

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Redis 7, Google OR-Tools CP-SAT, Lyzr Python ADK pattern
- **Channels and Speech**: Gupshup/Karix WhatsApp adapter, Exotel Voice/DTMF ExoML adapter, Bhashini primary ASR/TTS + Sarvam AI fallback (with full sandbox mode when API keys are omitted)
- **Frontends**:
  - `frontend-leader/`: React 18, Vite, Tailwind CSS, reskinned Radix UI / shadcn primitives, Recharts, Framer Motion, IBM Plex Sans, PWA service worker
  - `frontend-buyer/`: Independent React 18 + Vite + Tailwind bundle with zero Leader/Member code
- **UI Design Specification**: [DESIGN.md](DESIGN.md)
- **System Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Running Tests

The backend test suite covers the enforced state machine, deterministic order validation, CP-SAT fairness and explainability, shared rotation and payout broadcasts, buyer isolation, member-to-member privacy, federation workflows, and intake routing:

```powershell
cd d:\SakhiSetu
backend\.venv\Scripts\pytest backend\tests -v
```
