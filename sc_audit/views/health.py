"""
View database health: record counts and last-loaded timestamps per table.

Author: Alex Olieman <https://keybase.io/alioli>
"""
import datetime as dt

import pandas as pd
from sqlalchemy import func, select

from sc_audit.db_schema.association import RetirementFromBlock, SinkStatus
from sc_audit.db_schema.distribution import DistributionTx
from sc_audit.db_schema.impact_project import VcsProject
from sc_audit.db_schema.mint import MintedBlock
from sc_audit.db_schema.retirement import Retirement
from sc_audit.db_schema.sink import SinkingTx
from sc_audit.session_manager import Session


# Maps a human-readable table label to (model, timestamp_column) tuples.
# Tables without a timestamp column use None.
_TABLE_SPECS: list[tuple[str, object, object | None]] = [
    ("vcs_projects", VcsProject, None),
    ("minted_blocks", MintedBlock, MintedBlock.created_at),
    ("distribution_txs", DistributionTx, DistributionTx.created_at),
    ("sinking_txs", SinkingTx, SinkingTx.created_at),
    ("retirements", Retirement, Retirement.retirement_date),
    ("retirement_from_block", RetirementFromBlock, None),
    ("sink_status", SinkStatus, None),
]


def view_health() -> pd.DataFrame:
    """
    Return a DataFrame with one row per DB table containing:
      - table:       table name
      - row_count:   number of rows currently stored
      - last_loaded: latest timestamp/date value (None if not applicable)
    """
    rows: list[dict] = []
    with Session.begin() as session:
        for table_name, model, ts_col in _TABLE_SPECS:
            db_table = model.__table__  # type: ignore[union-attr]

            row_count: int = session.scalar(
                select(func.count()).select_from(db_table)
            ) or 0

            last_loaded: dt.datetime | dt.date | None = None
            if ts_col is not None:
                last_loaded = session.scalar(
                    select(ts_col).order_by(ts_col.desc()).limit(1)
                )

            rows.append({
                "table": table_name,
                "row_count": row_count,
                "last_loaded": last_loaded,
            })

    return pd.DataFrame(rows)
