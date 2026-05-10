import math

import pandas as pd

from calculator import optimize_schedule


def make_simple_feasible_df() -> pd.DataFrame:
    # Simple input that should have a feasible/optimal staffing solution.
    return pd.DataFrame(
        [
            {"timestamp": "2026-03-02 09:10:00", "duration_s": 1800, "source": "stream", "group": "G1"},
            {"timestamp": "2026-03-02 10:05:00", "duration_s": 600, "source": "stream", "group": "G2"},
            {"timestamp": None, "duration_s": 1200, "source": "batch", "group": "G1"},
        ]
    )


def test_optimize_schedule_returns_optimal_and_respects_hourly_coverage():
    df = make_simple_feasible_df()

    # Use one long shift to keep expected behavior easy to reason about.
    results = optimize_schedule(
        data_source=df,
        groups=["G1", "G2", "G3"],
        cost_per_hour={"G1": 150, "G2": 220, "G3": 350},
        limit={"G1": 20, "G2": 20, "G3": 20},
        shift_starts=[9],
        shift_length=12,
        occupancy=0.5,
        batch_deadline=14,
        use_night_batch=True,
    )

    assert results["status"] == "Optimal"
    assert results["total_cost"] is not None
    # Hours 9..20 are included => 12 hourly rows.
    assert len(results["hourly_coverage"]) == 12

    # In every hour, capacity must cover total work (stream + assigned batch).
    for row in results["hourly_coverage"]:
        assert row["capacity"] + 1e-9 >= row["total_demand"]

    # All batch work must be fully assigned before deadline.
    total_batch_assigned = sum(row["batch_assigned_total"] for row in results["hourly_coverage"])
    expected_batch = sum(results["batch_total_by_group"].values())
    assert math.isclose(total_batch_assigned, expected_batch, rel_tol=0, abs_tol=1e-7)


def test_optimize_schedule_can_be_infeasible_when_limits_too_low():
    df = pd.DataFrame(
        [
            {"timestamp": "2026-03-02 09:15:00", "duration_s": 1800, "source": "stream", "group": "G1"},
        ]
    )

    # Zero staff limits force an infeasible model.
    results = optimize_schedule(
        data_source=df,
        groups=["G1", "G2", "G3"],
        cost_per_hour={"G1": 150, "G2": 220, "G3": 350},
        limit={"G1": 0, "G2": 0, "G3": 0},
        shift_starts=[9],
        shift_length=12,
        occupancy=0.5,
        batch_deadline=14,
        use_night_batch=False,
    )

    assert results["status"] == "Infeasible"
    assert results["total_cost"] is None


def test_optimize_schedule_infeasible_when_batch_exceeds_deadline_capacity():
    # Vytvoříme nesplnitelný objem batch práce (120 000 sekund = 2000 minut)
    df = pd.DataFrame(
        [
            {"timestamp": None, "duration_s": 120000, "source": "batch", "group": "G1"},
        ]
    )

    # Deadline je 11:00, takže na batch jsou k dispozici jen 2 hodiny (9:00 - 11:00).
    # S limitem 10 lidí a occupancy 0.5 je maximální kapacita za tyto 2 hodiny pouhých 600 minut.
    results = optimize_schedule(
        data_source=df,
        groups=["G1", "G2", "G3"],
        cost_per_hour={"G1": 150, "G2": 220, "G3": 350},
        limit={"G1": 10, "G2": 10, "G3": 10},
        shift_starts=[9],
        shift_length=8,
        occupancy=0.5,
        batch_deadline=11,
        use_night_batch=True,
    )

    assert results["status"] == "Infeasible"
    assert results["total_cost"] is None