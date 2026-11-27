"""Tests for OR-Tools CP-SAT planner and solver-grounded explanations (§5)."""

from app.services.planner import MemberCapacity, TaskSpec, solve_allocation


def test_cpsat_fairness_and_explanation_changes_with_constraints():
    tasks = [
        TaskSpec(
            task_id="t1",
            step_name="stitch",
            required_skill="stitching",
            required_tools=["sewing_machine"],
            total_units=20,
            minutes_per_unit=10.0,
        )
    ]
    members_equal = [
        MemberCapacity("m1", "Anita", ["stitching"], ["sewing_machine"], 200),
        MemberCapacity("m2", "Geeta", ["stitching"], ["sewing_machine"], 200),
        MemberCapacity("m3", "Radha", ["qc"], [], 200),
    ]

    res1 = solve_allocation(tasks, members_equal, horizon_days=1)
    assert res1.feasible is True
    by_member_1 = {a.member_name: a for a in res1.assignments}
    assert by_member_1["Anita"].assigned_units == 10
    assert by_member_1["Geeta"].assigned_units == 10
    assert "Radha excluded (missing skill 'stitching'" in by_member_1["Anita"].explanation

    # Now tighten Geeta's capacity to 40 mins (max 4 units) -> explanation & allocation must reflect it
    members_tight = [
        MemberCapacity("m1", "Anita", ["stitching"], ["sewing_machine"], 200),
        MemberCapacity("m2", "Geeta", ["stitching"], ["sewing_machine"], 40),
        MemberCapacity("m3", "Radha", ["qc"], [], 200),
    ]
    res2 = solve_allocation(tasks, members_tight, horizon_days=1)
    assert res2.feasible is True
    by_member_2 = {a.member_name: a for a in res2.assignments}
    assert by_member_2["Geeta"].assigned_units <= 4
    assert by_member_2["Anita"].assigned_units >= 16
    assert by_member_1["Anita"].explanation != by_member_2["Anita"].explanation
    assert "40m" in by_member_2["Geeta"].explanation or "at capacity" in by_member_2["Anita"].explanation
