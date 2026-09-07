from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
import re


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


_PERIOD_PATTERN = re.compile(
    r"(?P<label>"
    r"(?:winter|summer)\s+semester\s+\d{2}(?:/\d{2})?"
    r")"
    r".{0,220}?"
    r"start\s+of\s+studies:\s*"
    r"(?P<study_start_day>\d{1,2})\s+"
    r"(?P<study_start_month>[a-z]+)\s+"
    r"(?P<study_start_year>\d{4})"
    r".{0,220}?"
    r"application\s+period"
    r"(?:\s*:\s*"
    r"(?P<application_start_day>\d{1,2})\s+"
    r"(?P<application_start_month>[a-z]+)"
    r"(?:\s+(?P<application_start_year>\d{4}))?"
    r"\s+to\s+"
    r"(?P<application_end_day>\d{1,2})\s+"
    r"(?P<application_end_month>[a-z]+)\s+"
    r"(?P<application_end_year>\d{4})"
    r"|"
    r"\s+(?P<closed>closed)"
    r")",
    flags=re.IGNORECASE | re.DOTALL,
)


def _month_number(value: str) -> Optional[int]:
    return _MONTHS.get(
        str(value or "").strip().lower()
    )


def _build_date(
    day: str,
    month: str,
    year: str,
) -> Optional[date]:
    month_number = _month_number(month)

    if month_number is None:
        return None

    try:
        return date(
            int(year),
            month_number,
            int(day),
        )
    except (TypeError, ValueError):
        return None


def _infer_start_year(
    start_month: int,
    end_month: int,
    end_year: int,
) -> int:
    # Application periods can cross the calendar year,
    # e.g. November 2026 to February 2027.
    if start_month > end_month:
        return end_year - 1

    return end_year


def extract_application_periods(
    text: str,
    *,
    as_of_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Extract programme-specific application periods and classify
    them relative to a reference date.

    No application dates are stored in code. Every period comes
    from the supplied evidence text.
    """
    reference_date = as_of_date or date.today()
    periods: List[Dict[str, Any]] = []

    for match in _PERIOD_PATTERN.finditer(
        str(text or "")
    ):
        label = str(
            match.group("label") or ""
        ).strip()

        study_start = _build_date(
            match.group("study_start_day"),
            match.group("study_start_month"),
            match.group("study_start_year"),
        )

        explicitly_closed = bool(
            match.group("closed")
        )

        application_start = None
        application_end = None

        if not explicitly_closed:
            start_month = _month_number(
                match.group(
                    "application_start_month"
                )
            )

            end_month = _month_number(
                match.group(
                    "application_end_month"
                )
            )

            end_year_text = match.group(
                "application_end_year"
            )

            if (
                start_month is not None
                and end_month is not None
                and end_year_text
            ):
                end_year = int(
                    end_year_text
                )

                start_year_text = match.group(
                    "application_start_year"
                )

                if start_year_text:
                    start_year = int(
                        start_year_text
                    )
                else:
                    start_year = _infer_start_year(
                        start_month,
                        end_month,
                        end_year,
                    )

                application_start = _build_date(
                    match.group(
                        "application_start_day"
                    ),
                    match.group(
                        "application_start_month"
                    ),
                    str(start_year),
                )

                application_end = _build_date(
                    match.group(
                        "application_end_day"
                    ),
                    match.group(
                        "application_end_month"
                    ),
                    str(end_year),
                )

        if explicitly_closed:
            status = "closed"
        elif (
            application_start is None
            or application_end is None
        ):
            status = "unknown"
        elif reference_date < application_start:
            status = "future"
        elif reference_date > application_end:
            status = "closed"
        else:
            status = "open"

        periods.append(
            {
                "label": label,
                "study_start": study_start,
                "application_start": (
                    application_start
                ),
                "application_end": (
                    application_end
                ),
                "status": status,
                "explicitly_closed": (
                    explicitly_closed
                ),
            }
        )

    return periods


def determine_application_timeline(
    text: str,
    *,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Return all parsed periods plus the current and next
    application period relative to the reference date.
    """
    reference_date = as_of_date or date.today()

    periods = extract_application_periods(
        text,
        as_of_date=reference_date,
    )

    open_periods = [
        period
        for period in periods
        if period["status"] == "open"
    ]

    future_periods = sorted(
        (
            period
            for period in periods
            if (
                period["status"] == "future"
                and period[
                    "application_start"
                ] is not None
            )
        ),
        key=lambda item: item[
            "application_start"
        ],
    )

    current_period = (
        open_periods[0]
        if open_periods
        else None
    )

    if current_period is not None:
        next_period = current_period
    elif future_periods:
        next_period = future_periods[0]
    else:
        next_period = None

    return {
        "as_of_date": reference_date,
        "periods": periods,
        "current_period": current_period,
        "next_period": next_period,
    }
