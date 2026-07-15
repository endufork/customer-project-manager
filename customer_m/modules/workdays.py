"""Business-day date helpers for workbench schedules."""

from datetime import date, timedelta


def add_workdays(start: date, workdays: int) -> date:
    if workdays < 0:
        raise ValueError("工作日偏移不能为负数")
    current = start
    remaining = workdays
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current
