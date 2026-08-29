"""A minimal 5-field cron matcher, so the simulator can expand a cadence.

Supports exactly the field shapes the repo's routine cadences use — numbers,
``*``, ``*/step``, comma lists, and ``a-b`` ranges — over the standard five
fields (minute, hour, day-of-month, month, day-of-week; dow 0 and 7 are both
Sunday, and like cron, a restricted dom OR dow matches when either does).
Anything fancier raises: the simulator must refuse a cadence it cannot
faithfully expand rather than quietly simulate the wrong schedule.

Times are naive UTC ``datetime`` objects throughout — the repo's crons are
written in UTC (the workflow comments say so), and the simulator's whole job
is relative arithmetic over a window.
"""

from __future__ import annotations

from datetime import datetime, timedelta


class CronError(ValueError):
    """A cron field this minimal matcher does not support."""


def _parse_field(field: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            raise CronError(f"empty cron field part in {field!r}")
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            if not step_s.isdigit() or int(step_s) < 1:
                raise CronError(f"bad step in cron field {field!r}")
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise CronError(f"bad range in cron field {field!r}")
            start, end = int(a), int(b)
        elif part.isdigit():
            start = end = int(part)
        else:
            raise CronError(f"unsupported cron field {field!r}")
        if start < lo or end > hi or start > end:
            raise CronError(f"cron field {field!r} out of range {lo}-{hi}")
        out.update(range(start, end + 1, step))
    return out


class Cron:
    def __init__(self, expr: str):
        fields = expr.split()
        if len(fields) != 5:
            raise CronError(f"a cron expression has 5 fields, got {expr!r}")
        self.expr = expr
        self.minutes = _parse_field(fields[0], 0, 59)
        self.hours = _parse_field(fields[1], 0, 23)
        self.dom = _parse_field(fields[2], 1, 31)
        self.months = _parse_field(fields[3], 1, 12)
        # dow: accept 0-7, fold 7 onto 0 (both Sunday).
        dow = _parse_field(fields[4], 0, 7)
        self.dow = {d % 7 for d in dow}
        self._dom_restricted = fields[2] != "*"
        self._dow_restricted = fields[4] != "*"

    def matches(self, t: datetime) -> bool:
        if t.minute not in self.minutes or t.hour not in self.hours:
            return False
        if t.month not in self.months:
            return False
        dom_ok = t.day in self.dom
        # isoweekday() % 7 maps Mon..Sun (1..7) onto cron's 1..6,0 numbering.
        dow_ok = (t.isoweekday() % 7) in self.dow
        # Standard cron: if both dom and dow are restricted, either matching
        # fires; if only one is restricted, that one decides.
        if self._dom_restricted and self._dow_restricted:
            return dom_ok or dow_ok
        if self._dom_restricted:
            return dom_ok
        if self._dow_restricted:
            return dow_ok
        return True

    def firings(self, start: datetime, days: int) -> list[datetime]:
        """Every firing time in ``[start, start + days)``, minute granularity."""
        out = []
        t = start.replace(second=0, microsecond=0)
        end = start + timedelta(days=days)
        while t < end:
            if t >= start and self.matches(t):
                out.append(t)
            t += timedelta(minutes=1)
        return out
