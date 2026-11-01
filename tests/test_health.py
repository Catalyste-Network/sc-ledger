"""
Tests for the `view health` feature.
"""
import datetime as dt

import pytest

from sc_audit.loader import impact_projects, minted_blocks, retirement_from_block
from sc_audit.loader import sinking_txs as sink_loader
from sc_audit.loader import sink_events as event_loader
from sc_audit.loader import sink_status as sink_status_loader
from sc_audit.views import health as health_view
from tests.data_fixtures.retirements import get_retirements_with_round_down_and_community
from tests.db_fixtures import new_session  # noqa: F401 — pytest fixture
from tests.test_event import mock_client, patch_mercury_key  # noqa: F401 — pytest fixtures
from tests.test_mint import mock_http as mock_mint_http  # noqa: F401 — pytest fixture
from tests.test_settings import patch_settings  # noqa: F401 — pytest fixture (required by patch_mercury_key)
from tests.test_sink import mock_http as mock_sink_http  # noqa: F401 — pytest fixture


class TestHealthViewEmpty:
    """Health view on an empty database."""

    def test_health_empty_db(self, mock_empty_session):
        df = health_view.view_health()
        assert not df.empty
        assert list(df.columns) == ["table", "row_count", "last_loaded"]
        # all tables present
        assert set(df["table"]) == {
            "vcs_projects",
            "minted_blocks",
            "distribution_txs",
            "sinking_txs",
            "retirements",
            "retirement_from_block",
            "sink_status",
        }
        # no rows loaded yet
        assert df["row_count"].sum() == 0
        # no timestamps yet
        assert df["last_loaded"].isna().all()

    def test_health_returns_seven_rows(self, mock_empty_session):
        df = health_view.view_health()
        assert len(df) == 7


class TestHealthViewPopulated:
    """Health view after data has been loaded."""

    def test_health_row_counts(self, mock_session_with_data):
        df = health_view.view_health()
        counts = df.set_index("table")["row_count"]
        # 1 impact project loaded
        assert counts["vcs_projects"] == 1
        # minted blocks and sinking txs loaded
        assert counts["minted_blocks"] > 0
        assert counts["sinking_txs"] > 0

    def test_health_last_loaded_timestamps(self, mock_session_with_data):
        df = health_view.view_health()
        ts = df.set_index("table")["last_loaded"]
        # tables with timestamp columns should have values
        assert ts["minted_blocks"] is not None
        assert ts["sinking_txs"] is not None
        assert ts["retirements"] is not None
        # tables without timestamp columns should be None/NaT
        assert ts["vcs_projects"] is None or str(ts["vcs_projects"]) == "NaT"
        assert ts["retirement_from_block"] is None or str(ts["retirement_from_block"]) == "NaT"
        assert ts["sink_status"] is None or str(ts["sink_status"]) == "NaT"

    def test_health_last_loaded_minted_blocks_is_datetime(self, mock_session_with_data):
        df = health_view.view_health()
        val = df.set_index("table").loc["minted_blocks", "last_loaded"]
        assert val is not None
        assert hasattr(val, 'year') or isinstance(val, (dt.datetime, dt.date))

    def test_health_last_loaded_retirements_is_date(self, mock_session_with_data):
        df = health_view.view_health()
        val = df.set_index("table").loc["retirements", "last_loaded"]
        assert val is not None

    def test_health_sink_status_count(self, mock_session_with_data):
        df = health_view.view_health()
        counts = df.set_index("table")["row_count"]
        assert counts["sink_status"] >= 0

    def test_health_retirement_from_block_count(self, mock_session_with_data):
        df = health_view.view_health()
        counts = df.set_index("table")["row_count"]
        assert counts["retirement_from_block"] >= 0


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_empty_session(monkeypatch, new_session):
    """Session patched into health_view with an empty DB."""
    monkeypatch.setattr(health_view, 'Session', new_session)
    return new_session


@pytest.fixture
def mock_session_with_data(
    mock_client, mock_mint_http, mock_sink_http, patch_mercury_key,
    monkeypatch, new_session,
):
    """Session populated with impact project, minted blocks, sinking txs, retirements."""
    # patch all loaders and the health view to use the in-memory session
    monkeypatch.setattr(impact_projects, 'Session', new_session)
    monkeypatch.setattr(minted_blocks, 'Session', new_session)
    monkeypatch.setattr(retirement_from_block, 'Session', new_session)
    monkeypatch.setattr(event_loader, 'Session', new_session)
    monkeypatch.setattr(sink_loader, 'Session', new_session)
    monkeypatch.setattr(sink_status_loader, 'Session', new_session)
    monkeypatch.setattr(health_view, 'Session', new_session)

    # load data
    impact_projects.load_impact_projects()

    with new_session.begin() as session:
        session.add_all(get_retirements_with_round_down_and_community())

    minted_blocks.load_minted_blocks()
    sink_loader.load_sinking_txs(cursor=999)
    event_loader.load_sink_events(cursor=0)
    retirement_from_block.load_retirement_from_block()
    sink_status_loader.load_sink_statuses()

    return new_session
