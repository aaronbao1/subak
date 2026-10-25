#!/usr/bin/env python3
"""Integrity checks on a generated database: the planted patterns must be visible in the data.

    python3 datagen/check.py [datagen/out/uber_ai_spend.sqlite]

Exit code 1 if any check fails.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent / "out" / "uber_ai_spend.sqlite"


def main(argv=None) -> int:
    path = Path((argv or sys.argv[1:] or [str(DEFAULT)])[0])
    con = sqlite3.connect(str(path))
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    failures = []

    def check(name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
        if not ok:
            failures.append(name)

    as_of = q("SELECT as_of FROM company")[0][0]
    n_people, n_teams, n_rows = q("SELECT (SELECT COUNT(*) FROM people), (SELECT COUNT(*) FROM teams), (SELECT COUNT(*) FROM usage_daily)")[0]
    check("volume", n_people >= 100 and n_teams >= 12 and n_rows >= 50000, f"people={n_people} teams={n_teams} usage_rows={n_rows}")

    # every person has a team, every usage row has a person, team and model
    orphans = q("SELECT COUNT(*) FROM usage_daily u LEFT JOIN people p ON p.id = u.person_id WHERE p.id IS NULL")[0][0]
    check("referential integrity", orphans == 0, f"orphan usage rows={orphans}")
    nulls = q("SELECT COUNT(*) FROM usage_daily WHERE model IS NULL OR provider IS NULL OR cost_category IS NULL")[0][0]
    check("no null model/provider/category", nulls == 0)

    # weekday vs weekend vs holiday
    wk, we, hol = q("""SELECT
        (SELECT AVG(tokens) FROM company_daily WHERE is_weekend = 0 AND holiday IS NULL AND day < ?),
        (SELECT AVG(tokens) FROM company_daily WHERE is_weekend = 1 AND day < ?),
        (SELECT AVG(tokens) FROM company_daily WHERE is_weekend = 0 AND holiday IS NOT NULL AND day < ?)""", as_of, as_of, as_of)[0]
    check("weekends well below weekdays", we < 0.45 * wk, f"weekend/weekday={we / wk:.2f}")
    check("holidays well below weekdays", hol < 0.6 * wk, f"holiday/weekday={hol / wk:.2f}")

    # three providers, several models each, and the model mix moves through the year
    provs = q("SELECT provider, COUNT(DISTINCT model) FROM usage_daily WHERE provider IN ('anthropic','openai','google') GROUP BY provider")
    check("three API providers with multiple models", len(provs) == 3 and all(n >= 3 for _, n in provs), str(provs))
    jan, oct_ = q("""SELECT
        (SELECT SUM(tokens) FROM model_monthly WHERE month='2026-01' AND model LIKE '%5.5%'),
        (SELECT SUM(tokens) FROM model_monthly WHERE month='2026-10' AND model LIKE '%5.5%')""")[0]
    check("5.5-generation models absent in January, dominant in October", (jan or 0) == 0 and (oct_ or 0) > 0, f"jan={jan} oct={oct_}")

    # trend: the company spends more in September than in February (adoption growth)
    feb, sep = q("""SELECT (SELECT SUM(cost_usd) FROM usage_daily WHERE day BETWEEN '2026-02-01' AND '2026-02-28'),
                           (SELECT SUM(cost_usd) FROM usage_daily WHERE day BETWEEN '2026-09-01' AND '2026-09-30')""")[0]
    check("adoption trend", sep > 1.3 * feb, f"feb=${feb:,.0f} sep=${sep:,.0f}")

    # out-of-office people: near zero inside their windows
    ooo = q("SELECT id, person_ids_json, starts_on, ends_on FROM events WHERE kind='out_of_office' AND is_future=0 AND ends_on < ?", as_of)
    bad = 0
    for eid, pids, s, e in ooo:
        pid = json.loads(pids)[0]
        inside = q("SELECT COALESCE(AVG(tokens),0) FROM person_daily WHERE person_id=? AND day BETWEEN ? AND ?", pid, s, e)[0][0]
        before = q("SELECT COALESCE(AVG(tokens),0) FROM person_daily WHERE person_id=? AND day BETWEEN date(?, '-28 days') AND date(?, '-1 day')", pid, s, s)[0][0]
        if before and inside > 0.15 * before:
            bad += 1
    check("out-of-office windows are quiet", bad == 0, f"{len(ooo)} windows, {bad} not quiet")

    # project pauses: affected people drop
    paused = q("SELECT id, person_ids_json, starts_on, ends_on, usage_multiplier FROM events WHERE kind='project_paused' AND is_future=0")
    for eid, pids, s, e, mult in paused:
        pids = json.loads(pids)
        marks = ",".join("?" * len(pids))
        inside = q(f"SELECT COALESCE(SUM(cost_usd),0)/COUNT(DISTINCT day) FROM usage_daily WHERE person_id IN ({marks}) AND day BETWEEN ? AND min(?, date(?, '-1 day'))", *pids, s, e, as_of)[0][0]
        before = q(f"SELECT COALESCE(SUM(cost_usd),0)/COUNT(DISTINCT day) FROM usage_daily WHERE person_id IN ({marks}) AND day BETWEEN date(?, '-28 days') AND date(?, '-1 day')", *pids, s, s)[0][0]
        check(f"{eid} pause visible", before and inside < 0.9 * before, f"inside/before={inside / before:.2f}" if before else "no baseline")

    # messages exist on Saturdays and across all channels
    sat = q("SELECT COUNT(*) FROM messages WHERE weekday='Saturday'")[0][0]
    channels = {r[0] for r in q("SELECT DISTINCT channel FROM messages")} | {r[0] for r in q("SELECT DISTINCT tool FROM tasks")}
    check("Saturday messages present", sat >= 4, f"{sat}")
    check("all six evidence channels present", channels >= {"slack", "teams", "gmail", "outlook", "asana", "monday"}, str(sorted(channels)))

    # future-dated evidence exists and is announced before as-of
    fut = q("SELECT COUNT(*) FROM events WHERE is_future=1 AND announced_on <= ?", as_of)[0][0]
    late = q("SELECT COUNT(*) FROM messages WHERE date(sent_at) > ?", as_of)[0][0] + q("SELECT COUNT(*) FROM tasks WHERE date(status_changed_at) > ?", as_of)[0][0]
    check("future events announced before as-of", fut >= 10 and late == 0, f"future events={fut}, artifacts dated after as-of={late}")

    # Fable 5.1 appears only in the holdout truth
    fable_hist = q("SELECT COUNT(*) FROM usage_daily WHERE model LIKE 'Claude Fable%'")[0][0]
    fable_fut = q("SELECT COUNT(*) FROM usage_daily_holdout WHERE model LIKE 'Claude Fable%'")[0][0]
    check("Fable 5.1 only after the pilot start", fable_hist == 0 and fable_fut > 0, f"history={fable_hist} holdout={fable_fut}")

    # budgets: every team has an allocation for every period
    nb = q("SELECT COUNT(*) FROM budgets")[0][0]
    check("budgets for every team and period", nb == n_teams * 4, f"{nb}")

    print(f"\n{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
