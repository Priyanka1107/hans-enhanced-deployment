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



_EXPLICIT_DAY_MONTH_DATE = re.compile(
    r"\b(?P<day>\d{1,2})"
    r"\s*(?:st|nd|rd|th)?\s+"
    r"(?P<month>[a-z????]+)"
    r"(?:\s+(?:of\s+)?)?"
    r"(?P<year>\d{4})\b",
    flags=re.IGNORECASE,
)

_EXPLICIT_MONTH_DAY_DATE = re.compile(
    r"\b(?P<month>[a-z????]+)\s+"
    r"(?P<day>\d{1,2})"
    r"\s*(?:st|nd|rd|th)?"
    r"(?:\s+of)?"
    r"\s*,?\s*"
    r"(?P<year>\d{4})\b",
    flags=re.IGNORECASE,
)

_EXPLICIT_NUMERIC_DATE = re.compile(
    r"\b(?P<day>\d{1,2})"
    r"[./-](?P<month>\d{1,2})"
    r"[./-](?P<year>\d{4})\b",
    flags=re.IGNORECASE,
)

_DEADLINE_ANCHOR = re.compile(
    r"\b(?:application\s+deadline|deadline|bewerbungsfrist)\b",
    flags=re.IGNORECASE,
)

_DEADLINE_LABEL = re.compile(
    r"\b(?P<label>"
    r"[a-z????]+\s+\d{4}\s+intake"
    r"|(?:winter|summer)\s+semester\s+\d{2,4}(?:/\d{2,4})?"
    r"|(?:winter|sommer)semester\s+\d{2,4}(?:/\d{2,4})?"
    r")\b",
    flags=re.IGNORECASE,
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



def _extract_first_explicit_date(
    value: str,
) -> Optional[date]:
    candidates: List[tuple[int, date]] = []

    for pattern in (
        _EXPLICIT_DAY_MONTH_DATE,
        _EXPLICIT_MONTH_DAY_DATE,
    ):
        for match in pattern.finditer(
            str(value or "")
        ):
            parsed = _build_date(
                match.group("day"),
                match.group("month"),
                match.group("year"),
            )

            if parsed is not None:
                candidates.append(
                    (match.start(), parsed)
                )

    for match in _EXPLICIT_NUMERIC_DATE.finditer(
        str(value or "")
    ):
        try:
            parsed = date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            continue

        candidates.append(
            (match.start(), parsed)
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


def _extract_explicit_deadlines(
    text: str,
    *,
    as_of_date: date,
) -> List[Dict[str, Any]]:
    """
    Extract explicit single application deadlines from official
    evidence when no structured application-period range exists.

    Examples:
        "The application deadline is 15 June 2026."
        "The new deadline is June 15th of 2026."
        "Bewerbungsfrist: 15.06.2026"

    This is temporal parsing only. It contains no programme-
    specific deadline values.
    """
    clean_text = re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()

    if not clean_text:
        return []

    deadlines: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for anchor in _DEADLINE_ANCHOR.finditer(
        clean_text
    ):
        # The actual deadline should normally appear after
        # the deadline phrase. Keep the window deliberately
        # local so unrelated dates elsewhere on the page do
        # not become deadlines.
        after = clean_text[
            anchor.end():
            min(
                len(clean_text),
                anchor.end() + 220,
            )
        ]

        deadline_date = (
            _extract_first_explicit_date(
                after
            )
        )

        if deadline_date is None:
            continue

        context = clean_text[
            max(0, anchor.start() - 160):
            min(
                len(clean_text),
                anchor.end() + 180,
            )
        ]

        labels = list(
            _DEADLINE_LABEL.finditer(
                context
            )
        )

        if labels:
            label = (
                labels[-1]
                .group("label")
                .strip()
            )
        else:
            label = "application deadline"

        key = (
            label.lower(),
            deadline_date.isoformat(),
        )

        if key in seen:
            continue

        seen.add(key)

        if as_of_date < deadline_date:
            status = "future"
        elif as_of_date > deadline_date:
            status = "closed"
        else:
            status = "open"

        deadlines.append(
            {
                "label": label,
                "study_start": None,
                "application_start": (
                    deadline_date
                ),
                "application_end": (
                    deadline_date
                ),
                "deadline_date": (
                    deadline_date
                ),
                "status": status,
                "explicitly_closed": False,
                "date_kind": "deadline",
            }
        )

    return deadlines


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

    if not periods:
        periods.extend(
            _extract_explicit_deadlines(
                text,
                as_of_date=reference_date,
            )
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
