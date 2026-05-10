import pandas as pd
import pytest

from calculator import load_demand_data


def make_base_df() -> pd.DataFrame:
    # Small deterministic dataset used by all tests in this file.
    return pd.DataFrame(
        [
            {"timestamp": "2026-03-02 09:15:00", "duration_s": 600, "source": "stream", "group": "G1"},
            {"timestamp": "2026-03-02 09:45:00", "duration_s": 300, "source": "stream", "group": "G1"},
            {"timestamp": "2026-03-02 10:30:00", "duration_s": 1200, "source": "stream", "group": "G2"},
            {"timestamp": None, "duration_s": 900, "source": "batch", "group": "G3"},
            {"timestamp": None, "duration_s": 300, "source": "batch", "group": "G1"},
        ]
    )


def test_load_demand_data_aggregates_stream_and_batch_correctly():
    df = make_base_df()

    # Batch is enabled, so both stream and batch parts should be aggregated.
    stream_by_group, batch_by_group, deadline = load_demand_data(
        df,
        batch_deadline=14,
        use_night_batch=True,
    )

    assert deadline == 14

    # 600 + 300 seconds in hour 9 => 15 minutes for G1.
    assert stream_by_group["G1"].get(9, 0) == 15
    assert stream_by_group["G2"].get(10, 0) == 20
    assert stream_by_group["G3"].empty

    assert batch_by_group["G1"] == 5
    assert batch_by_group["G2"] == 0
    assert batch_by_group["G3"] == 15


def test_load_demand_data_ignores_batch_when_disabled():
    df = make_base_df()

    # Batch is disabled, so all batch totals should be zero.
    stream_by_group, batch_by_group, deadline = load_demand_data(
        df,
        batch_deadline=13,
        use_night_batch=False,
    )

    assert deadline == 13
    assert stream_by_group["G1"].get(9, 0) == 15
    assert stream_by_group["G2"].get(10, 0) == 20
    assert stream_by_group["G3"].empty

    assert batch_by_group == {"G1": 0.0, "G2": 0.0, "G3": 0.0}


@pytest.mark.parametrize(
    "rows,use_night_batch,expected_stream,expected_batch",
    [
        (
            [],
            True,
            {},
            {"G1": 0.0, "G2": 0.0, "G3": 0.0},
        ),
        (
            [
                {"timestamp": None, "duration_s": 600, "source": "batch", "group": "G1"},
                {"timestamp": None, "duration_s": 300, "source": "batch", "group": "G3"},
            ],
            True,
            {},
            {"G1": 10.0, "G2": 0.0, "G3": 5.0},
        ),
        (
            [
                {"timestamp": None, "duration_s": 600, "source": "batch", "group": "G1"},
                {"timestamp": None, "duration_s": 300, "source": "batch", "group": "G3"},
            ],
            False,
            {},
            {"G1": 0.0, "G2": 0.0, "G3": 0.0},
        ),
        (
            [
                {"timestamp": "2026-03-02 09:05:00", "duration_s": 600, "source": "stream", "group": "G1"},
                {"timestamp": None, "duration_s": 300, "source": "stream", "group": "G1"},
            ],
            True,
            {"G1": {9: 10.0}},
            {"G1": 0.0, "G2": 0.0, "G3": 0.0},
        ),
        (
            [
                {"timestamp": "2026-03-02 10:00:00", "duration_s": 900, "source": "other", "group": "G4"},
            ],
            True,
            {},
            {"G1": 0.0, "G2": 0.0, "G3": 0.0},
        ),
    ],
)
def test_load_demand_data_edge_cases_parametrized(rows, use_night_batch, expected_stream, expected_batch):
    df = pd.DataFrame(rows, columns=["timestamp", "duration_s", "source", "group"])

    stream_by_group, batch_by_group, deadline = load_demand_data(
        df,
        batch_deadline=14,
        use_night_batch=use_night_batch,
    )

    assert deadline == 14
    assert set(stream_by_group.keys()) == {"G1", "G2", "G3"}
    assert set(batch_by_group.keys()) == {"G1", "G2", "G3"}
    assert batch_by_group == expected_batch

    for group in ["G1", "G2", "G3"]:
        expected_group = expected_stream.get(group, {})
        for hour, minutes in expected_group.items():
            assert stream_by_group[group].get(hour, 0) == minutes

        reported_hours = set(stream_by_group[group].index.tolist())
        assert reported_hours == set(expected_group.keys())


@pytest.mark.parametrize("missing_column", ["timestamp", "duration_s", "source", "group"])
def test_load_demand_data_raises_on_missing_required_column(missing_column):
    row = {
        "timestamp": "2026-03-02 09:00:00",
        "duration_s": 600,
        "source": "stream",
        "group": "G1",
    }
    row.pop(missing_column)
    df = pd.DataFrame([row])

    with pytest.raises(KeyError):
        load_demand_data(df)


@pytest.mark.parametrize("invalid_timestamp", ["not-a-date", "2026-99-99 09:00:00", "13/13/2026"])
def test_load_demand_data_raises_on_invalid_timestamp_format(invalid_timestamp):
    df = pd.DataFrame(
        [
            {
                "timestamp": invalid_timestamp,
                "duration_s": 600,
                "source": "stream",
                "group": "G1",
            }
        ]
    )

    with pytest.raises((ValueError, TypeError)):
        load_demand_data(df)
