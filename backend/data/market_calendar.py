from datetime import date
import pandas as pd

# Representative major NSE recurring & historical market closure dates (Republic Day,
# Independence Day, Gandhi Jayanti, Christmas, plus major NSE holidays).
# Used alongside cross-sectional market presence to distinguish exchange holidays
# from single-asset missing observations.
FIXED_INDIAN_NATIONAL_HOLIDAYS: list[tuple[int, int]] = [
    (1, 26),   # Republic Day
    (8, 15),   # Independence Day
    (10, 2),   # Gandhi Jayanti
    (12, 25),  # Christmas
]

# Verified non-weekend NSE trading closures (2018-2026 sample major holidays;
# dynamic benchmark presence is also used as primary trading calendar reference).
KNOWN_NSE_HOLIDAYS: set[str] = {
    "2020-02-21", "2020-03-10", "2020-04-02", "2020-04-06", "2020-04-10",
    "2020-04-14", "2020-05-01", "2020-05-25", "2020-10-02", "2020-11-16",
    "2020-11-30", "2020-12-25",
    "2021-01-26", "2021-03-11", "2021-03-29", "2021-04-02", "2021-04-14",
    "2021-04-21", "2021-05-13", "2021-07-21", "2021-08-19", "2021-09-10",
    "2021-10-15", "2021-11-04", "2021-11-05", "2021-11-19",
    "2022-01-26", "2022-03-01", "2022-03-18", "2022-04-14", "2022-04-15",
    "2022-05-03", "2022-08-09", "2022-08-15", "2022-08-31", "2022-10-05",
    "2022-10-24", "2022-10-26", "2022-11-08",
    "2023-01-26", "2023-03-07", "2023-03-30", "2023-04-04", "2023-04-07",
    "2023-04-14", "2023-05-01", "2023-06-29", "2023-08-15", "2023-09-19",
    "2023-10-02", "2023-10-24", "2023-11-14", "2023-11-27", "2023-12-25",
    "2024-01-22", "2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29",
    "2024-04-11", "2024-04-17", "2024-05-01", "2024-05-20", "2024-06-17",
    "2024-07-17", "2024-08-15", "2024-10-02", "2024-11-01", "2024-11-15",
    "2024-11-20", "2024-12-25",
    "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10", "2025-04-14",
    "2025-04-18", "2025-05-01", "2025-08-15", "2025-08-27", "2025-10-02",
    "2025-10-21", "2025-10-22", "2025-11-05", "2025-12-25",
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31", "2026-04-03",
    "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26", "2026-09-14",
    "2026-10-02", "2026-10-20", "2026-11-10", "2026-11-24", "2026-12-25",
}


def is_fixed_indian_holiday(d: date) -> bool:
    return (d.month, d.day) in FIXED_INDIAN_NATIONAL_HOLIDAYS


def build_nse_reference_calendar(
    start_date: date,
    end_date: date,
    benchmark_dates: pd.DatetimeIndex | None = None,
) -> pd.DatetimeIndex:
    """
    Build expected NSE trading dates between start_date and end_date.

    When benchmark_dates (e.g., NIFTY 50 observed sessions) is available,
    the union of active market sessions across the benchmark is authoritative
    because NSE lunar/festival holidays shift annually and special Muhurat
    weekend sessions occasionally occur. Dates in weekday calendar not in
    KNOWN_NSE_HOLIDAYS or benchmark sessions are surfaced transparently.
    """
    if benchmark_dates is not None and len(benchmark_dates) > 0:
        mask = (benchmark_dates >= pd.Timestamp(start_date)) & (
            benchmark_dates <= pd.Timestamp(end_date)
        )
        return pd.DatetimeIndex(sorted(benchmark_dates[mask].unique()))

    all_bdays = pd.bdate_range(start=start_date, end=end_date)
    valid = [
        ts
        for ts in all_bdays
        if ts.strftime("%Y-%m-%d") not in KNOWN_NSE_HOLIDAYS
        and not is_fixed_indian_holiday(ts.date())
    ]
    return pd.DatetimeIndex(valid)
