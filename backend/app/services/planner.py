"""Stateless Google OR-Tools CP-SAT allocation solver with solver-grounded explanations (§5)."""

from dataclasses import dataclass, field
from ortools.sat.python import cp_model


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    step_name: str
    required_skill: str
    required_tools: list[str]
    total_units: int
    minutes_per_unit: float


@dataclass(frozen=True)
class MemberCapacity:
    member_id: str
    name: str
    skills: list[str]
    tools: list[str]
    available_minutes: int
    workload_preference: str = "standard"  # standard | more | less (§19)
    consecutive_max_share_cycles: int = 0


@dataclass
class AssignmentResult:
    task_id: str
    step_name: str
    member_id: str
    member_name: str
    assigned_units: int
    estimated_minutes: float
    explanation: str
    solver_metadata: dict = field(default_factory=dict)


@dataclass
class SolveOutput:
    feasible: bool
    status_name: str
    assignments: list[AssignmentResult]
    infeasibility_reason: str | None = None
    fairness_max_utilization_pct: float = 0.0
    fairness_warnings: list[str] = field(default_factory=list)


def _ineligibility_reasons(task: TaskSpec, member: MemberCapacity) -> list[str]:
    reasons: list[str] = []
    if task.required_skill not in member.skills:
        reasons.append(f"missing skill '{task.required_skill}'")
    missing_tools = [t for t in task.required_tools if t not in member.tools]
    if missing_tools:
        reasons.append(f"missing tools {missing_tools}")
    if member.available_minutes < int(round(task.minutes_per_unit)):
        reasons.append(
            f"only {member.available_minutes}m free (< {int(round(task.minutes_per_unit))}m/unit)"
        )
    return reasons


def solve_allocation(
    tasks: list[TaskSpec],
    members: list[MemberCapacity],
    horizon_days: int = 1,
) -> SolveOutput:
    """Pure, stateless CP-SAT allocation solver.

    Constraints:
    - Each task's total_units must be completely assigned across eligible members.
    - Each member's total assigned minutes <= available_minutes * horizon_days.
    - Fairness: minimize the maximum utilization percentage (scaled 0..1000) across members,
      plus small secondary tie-breaker on total utilization spread.
    """
    if not tasks:
        return SolveOutput(feasible=True, status_name="OPTIMAL", assignments=[])
    if not members:
        return SolveOutput(
            feasible=False,
            status_name="INFEASIBLE",
            assignments=[],
            infeasibility_reason="No active members available.",
        )

    model = cp_model.CpModel()
    effective_cap = {m.member_id: max(0, m.available_minutes * horizon_days) for m in members}

    # Decision vars: units[t_idx, m_idx]
    units_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    eligible_map: dict[int, list[int]] = {}

    for t_idx, task in enumerate(tasks):
        eligible_map[t_idx] = []
        for m_idx, member in enumerate(members):
            if not _ineligibility_reasons(task, member):
                eligible_map[t_idx].append(m_idx)
                units_vars[(t_idx, m_idx)] = model.NewIntVar(
                    0, task.total_units, f"u_t{t_idx}_m{m_idx}"
                )

        if not eligible_map[t_idx]:
            return SolveOutput(
                feasible=False,
                status_name="INFEASIBLE",
                assignments=[],
                infeasibility_reason=(
                    f"No member satisfies skill '{task.required_skill}' and tools {task.required_tools} "
                    f"for task '{task.step_name}'."
                ),
            )

        # Cover all units of task
        model.Add(sum(units_vars[(t_idx, m_idx)] for m_idx in eligible_map[t_idx]) == task.total_units)

    # Member capacity & fairness utilization (per-mille, 0..1000)
    max_util = model.NewIntVar(0, 1000, "max_utilization_permille")
    member_used_mins: dict[int, cp_model.LinearExpr] = {}
    member_util_vars: dict[int, cp_model.IntVar] = {}

    for m_idx, member in enumerate(members):
        cap = effective_cap[member.member_id]
        terms = []
        for t_idx, task in enumerate(tasks):
            if (t_idx, m_idx) in units_vars:
                terms.append(units_vars[(t_idx, m_idx)] * int(round(task.minutes_per_unit)))

        used_expr = sum(terms) if terms else 0
        member_used_mins[m_idx] = used_expr
        if terms:
            model.Add(used_expr <= cap)

        util_var = model.NewIntVar(0, 1000, f"util_m{m_idx}")
        member_util_vars[m_idx] = util_var
        if cap > 0 and terms:
            # util_var * cap >= used_expr * 1000 (upper bound on utilization permille)
            model.Add(util_var * cap >= used_expr * 1000)
            model.Add(util_var <= max_util)
        else:
            model.Add(util_var == 0)

    # Soft preference penalty/bonus (§19): only shifts work among equally-qualified/available members
    # after hard constraints. Weighted so preference can shift within fairness bounds without breaking
    # equal-split for "standard" members.
    pref_terms = []
    for m_idx, member in enumerate(members):
        if member.workload_preference == "less":
            pref_terms.append(member_util_vars[m_idx] * 15)
        elif member.workload_preference == "more":
            pref_terms.append(member_util_vars[m_idx] * -15)

    # Fairness objective: minimize max utilization + small sum of utilizations + soft preference terms
    model.Minimize(max_util * 10 + sum(member_util_vars.values()) * 2 + sum(pref_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        total_req_mins = sum(t.total_units * t.minutes_per_unit for t in tasks)
        total_avail_mins = sum(effective_cap.values())
        return SolveOutput(
            feasible=False,
            status_name=status_name,
            assignments=[],
            infeasibility_reason=(
                f"CP-SAT {status_name}: required {total_req_mins:.0f}m across tasks, "
                f"total eligible capacity {total_avail_mins}m."
            ),
        )

    # Compute actual post-solve utilization and slack per member
    used_by_member: dict[int, float] = {m_idx: 0.0 for m_idx in range(len(members))}
    for (t_idx, m_idx), var in units_vars.items():
        u = solver.Value(var)
        if u > 0:
            used_by_member[m_idx] += u * tasks[t_idx].minutes_per_unit

    max_util_pct = solver.Value(max_util) / 10.0

    assignments: list[AssignmentResult] = []
    for (t_idx, m_idx), var in units_vars.items():
        u = solver.Value(var)
        if u <= 0:
            continue
        task = tasks[t_idx]
        member = members[m_idx]
        cap = effective_cap[member.member_id]
        used = used_by_member[m_idx]
        slack = max(0.0, cap - used)
        util_pct = (used / cap * 100.0) if cap > 0 else 0.0
        est_mins = u * task.minutes_per_unit

        # Build solver-grounded explanation from actual constraints & alternatives
        alternatives_notes: list[str] = []
        for alt_idx, alt in enumerate(members):
            if alt_idx == m_idx:
                continue
            inelig = _ineligibility_reasons(task, alt)
            if inelig:
                alternatives_notes.append(f"{alt.name} excluded ({', '.join(inelig)})")
            else:
                alt_cap = effective_cap[alt.member_id]
                alt_used = used_by_member[alt_idx]
                alt_slack = max(0.0, alt_cap - alt_used)
                alt_util = (alt_used / alt_cap * 100.0) if alt_cap > 0 else 0.0
                if alt_slack < task.minutes_per_unit:
                    alternatives_notes.append(
                        f"{alt.name} at capacity ({alt_util:.0f}% used, {alt_slack:.0f}m slack)"
                    )
                else:
                    alternatives_notes.append(
                        f"{alt.name} balanced at {alt_util:.0f}% ({alt_slack:.0f}m slack)"
                    )

        binding_note = (
            f"capacity binding ({slack:.0f}m slack remaining)"
            if slack < task.minutes_per_unit
            else f"{slack:.0f}m slack remaining"
        )
        pref_note = ""
        if member.workload_preference != "standard":
            pref_note = f"; workload preference='{member.workload_preference}' applied as soft constraint"
        alt_text = "; ".join(alternatives_notes[:3]) if alternatives_notes else "sole eligible member"
        explanation = (
            f"CP-SAT {status_name}: assigned {u}u ({est_mins:.0f}m) to {member.name} "
            f"[{util_pct:.0f}% of {cap}m cap, {binding_note}; fairness max={max_util_pct:.0f}%{pref_note}]. "
            f"Alternatives: {alt_text}."
        )

        assignments.append(
            AssignmentResult(
                task_id=task.task_id,
                step_name=task.step_name,
                member_id=member.member_id,
                member_name=member.name,
                assigned_units=u,
                estimated_minutes=est_mins,
                explanation=explanation,
                solver_metadata={
                    "solver_status": status_name,
                    "member_utilization_pct": round(util_pct, 1),
                    "member_slack_minutes": round(slack, 1),
                    "group_max_utilization_pct": round(max_util_pct, 1),
                    "alternatives": alternatives_notes,
                },
            )
        )

    # §19 Explainability for unhonored non-standard preferences:
    # Emit a 0-unit AssignmentResult for any member with workload_preference != 'standard' who got 0 units,
    # citing the exact solver/eligibility constraint reason so silence never hides why a preference wasn't honored.
    for m_idx, member in enumerate(members):
        if member.workload_preference != "standard" and used_by_member[m_idx] == 0:
            per_task_reasons: list[str] = []
            for task in tasks:
                inelig = _ineligibility_reasons(task, member)
                if inelig:
                    per_task_reasons.append(f"task '{task.step_name}': {', '.join(inelig)}")
                else:
                    per_task_reasons.append(
                        f"task '{task.step_name}': eligible but 0u assigned under fairness/capacity balance"
                    )
            reason_summary = "; ".join(per_task_reasons)
            assignments.append(
                AssignmentResult(
                    task_id=tasks[0].task_id,
                    step_name=tasks[0].step_name,
                    member_id=member.member_id,
                    member_name=member.name,
                    assigned_units=0,
                    estimated_minutes=0.0,
                    explanation=(
                        f"CP-SAT {status_name}: 0u assigned to {member.name} "
                        f"(workload preference='{member.workload_preference}' recorded but not honored: {reason_summary})."
                    ),
                    solver_metadata={
                        "solver_status": status_name,
                        "member_utilization_pct": 0.0,
                        "member_slack_minutes": float(effective_cap[member.member_id]),
                        "group_max_utilization_pct": round(max_util_pct, 1),
                        "preference_unhonored_reasons": per_task_reasons,
                    },
                )
            )

    # Anti-favoritism guardrail (§19): flag if a member has absorbed max share in >= 2 consecutive cycles
    fairness_warnings: list[str] = []
    if used_by_member:
        max_used = max(used_by_member.values())
        for m_idx, used in used_by_member.items():
            m = members[m_idx]
            if max_used > 0 and used >= max_used * 0.99 and m.consecutive_max_share_cycles >= 2:
                fairness_warnings.append(
                    f"Fairness signal: {m.name} has taken the maximum share in "
                    f"{m.consecutive_max_share_cycles + 1} consecutive cycles (pref='{m.workload_preference}')."
                )

    return SolveOutput(
        feasible=True,
        status_name=status_name,
        assignments=assignments,
        fairness_max_utilization_pct=round(max_util_pct, 1),
        fairness_warnings=fairness_warnings,
    )
