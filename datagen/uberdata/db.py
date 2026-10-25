"""SQLite output: one self-contained database with everything the generator knows."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from . import config as C

SCHEMA = """
CREATE TABLE company (id TEXT PRIMARY KEY, name TEXT NOT NULL, is_demo INTEGER NOT NULL, email_domain TEXT, currency TEXT,
                      as_of DATE NOT NULL, year_start DATE NOT NULL, horizon_end DATE NOT NULL, seed INTEGER NOT NULL, generated_at TEXT NOT NULL);
CREATE TABLE periods (id TEXT PRIMARY KEY, label TEXT NOT NULL, starts_on DATE NOT NULL, ends_on DATE NOT NULL);
CREATE TABLE teams (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, cost_center TEXT, lead_person_id TEXT, color TEXT,
                    default_tool TEXT, provider_mix_json TEXT, weekend_factor REAL, growth REAL);
CREATE TABLE people (id TEXT PRIMARY KEY, team_id TEXT NOT NULL REFERENCES teams(id), name TEXT NOT NULL, role TEXT, level TEXT,
                     email TEXT, primary_tool TEXT, start_date DATE, end_date DATE, is_lead INTEGER, timezone TEXT,
                     integrations_json TEXT, base_tokens_per_weekday INTEGER, weekend_factor REAL);
CREATE TABLE providers (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE models (id TEXT PRIMARY KEY, provider TEXT NOT NULL REFERENCES providers(id), name TEXT NOT NULL,
                     list_input_usd_per_mtok REAL, list_cached_input_usd_per_mtok REAL, list_output_usd_per_mtok REAL,
                     released_on DATE, reasoning INTEGER);
CREATE TABLE model_prices (model_id TEXT NOT NULL REFERENCES models(id), effective_from DATE NOT NULL, input_usd_per_mtok REAL,
                           cached_input_usd_per_mtok REAL, output_usd_per_mtok REAL, PRIMARY KEY (model_id, effective_from));
CREATE TABLE model_events (id TEXT PRIMARY KEY, provider TEXT, model_ids_json TEXT, kind TEXT NOT NULL, announced_on DATE, effective_on DATE, details_json TEXT);
CREATE TABLE calendar (day DATE PRIMARY KEY, weekday INTEGER, weekday_name TEXT, is_weekend INTEGER, holiday TEXT, holiday_factor REAL,
                       seasonal_factor REAL, period_id TEXT, is_partial INTEGER, is_future INTEGER);
CREATE TABLE projects (id TEXT PRIMARY KEY, team_id TEXT REFERENCES teams(id), name TEXT NOT NULL);
CREATE TABLE events (id TEXT PRIMARY KEY, kind TEXT NOT NULL, scope TEXT NOT NULL, team_ids_json TEXT, person_ids_json TEXT, project TEXT,
                     starts_on DATE NOT NULL, ends_on DATE, usage_multiplier REAL, weekend_multiplier REAL, model_override_json TEXT,
                     provider_shift_json TEXT, announced_on DATE NOT NULL, title TEXT, summary TEXT, expected_effect TEXT, category TEXT,
                     confidence TEXT, claim_type TEXT, magnitude_pct INTEGER, uncertainty TEXT, is_future INTEGER);
CREATE TABLE messages (id TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), channel TEXT NOT NULL, sent_at TEXT NOT NULL,
                       weekday TEXT, from_person_id TEXT, from_name TEXT, to_json TEXT, where_ TEXT, body TEXT, team_ids_json TEXT, person_ids_json TEXT);
CREATE TABLE tasks (id TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), tool TEXT NOT NULL, board TEXT, title TEXT, assignee_id TEXT,
                    assignee_name TEXT, created_at TEXT, due_on DATE, prev_due_on DATE, status TEXT, prev_status TEXT, status_changed_at TEXT,
                    body TEXT, team_ids_json TEXT, person_ids_json TEXT);
CREATE TABLE usage_daily (id INTEGER PRIMARY KEY, day DATE NOT NULL, person_id TEXT NOT NULL REFERENCES people(id), team_id TEXT NOT NULL,
                          provider TEXT NOT NULL, model_id TEXT, model TEXT, tool TEXT, cost_category TEXT NOT NULL,
                          input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER, total_tokens INTEGER,
                          requests INTEGER, cost_usd REAL, notional_usd REAL, period_id TEXT);
CREATE TABLE usage_daily_holdout (id INTEGER PRIMARY KEY, day DATE NOT NULL, person_id TEXT NOT NULL, team_id TEXT NOT NULL,
                          provider TEXT NOT NULL, model_id TEXT, model TEXT, tool TEXT, cost_category TEXT NOT NULL,
                          input_tokens INTEGER, cached_input_tokens INTEGER, output_tokens INTEGER, reasoning_tokens INTEGER, total_tokens INTEGER,
                          requests INTEGER, cost_usd REAL, notional_usd REAL, period_id TEXT);
CREATE TABLE seat_subscriptions (id INTEGER PRIMARY KEY, month DATE NOT NULL, person_id TEXT NOT NULL, team_id TEXT NOT NULL, tool TEXT, provider TEXT, amount_usd REAL, period_id TEXT);
CREATE TABLE seat_subscriptions_holdout (id INTEGER PRIMARY KEY, month DATE NOT NULL, person_id TEXT NOT NULL, team_id TEXT NOT NULL, tool TEXT, provider TEXT, amount_usd REAL, period_id TEXT);
CREATE TABLE budgets (team_id TEXT NOT NULL, period_id TEXT NOT NULL, allocated_usd REAL NOT NULL, actual_usd_to_date REAL, PRIMARY KEY (team_id, period_id));
CREATE INDEX ix_usage_day ON usage_daily(day);
CREATE INDEX ix_usage_person ON usage_daily(person_id, day);
CREATE INDEX ix_usage_team ON usage_daily(team_id, day);
CREATE INDEX ix_holdout_team ON usage_daily_holdout(team_id, day);
CREATE INDEX ix_messages_sent ON messages(sent_at);
CREATE INDEX ix_tasks_created ON tasks(created_at);
CREATE VIEW team_daily AS
  SELECT team_id, day, period_id, provider, cost_category, SUM(total_tokens) AS tokens, ROUND(SUM(cost_usd), 2) AS cost_usd,
         ROUND(SUM(notional_usd), 2) AS notional_usd FROM usage_daily GROUP BY team_id, day, period_id, provider, cost_category;
CREATE VIEW person_daily AS
  SELECT person_id, team_id, day, SUM(total_tokens) AS tokens, ROUND(SUM(cost_usd), 2) AS cost_usd FROM usage_daily GROUP BY person_id, team_id, day;
CREATE VIEW company_daily AS
  SELECT c.day, c.weekday_name, c.is_weekend, c.holiday, COALESCE(SUM(u.total_tokens), 0) AS tokens, ROUND(COALESCE(SUM(u.cost_usd), 0), 2) AS cost_usd
  FROM calendar c LEFT JOIN usage_daily u ON u.day = c.day WHERE c.is_future = 0 GROUP BY c.day;
CREATE VIEW model_monthly AS
  SELECT substr(day, 1, 7) AS month, provider, model, SUM(total_tokens) AS tokens, ROUND(SUM(cost_usd), 2) AS cost_usd
  FROM usage_daily GROUP BY month, provider, model;
"""


def j(x) -> str:
    return json.dumps(x, default=str)


def write_sqlite(path: Path, *, teams, people, story, calendar, usage_rows, seat_rows, holdout_rows, holdout_seats, budgets, generated_at: str) -> None:
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(path) + suffix)
        if p.exists():
            p.unlink()
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    con.execute("INSERT INTO company VALUES (?,?,?,?,?,?,?,?,?,?)",
                (C.COMPANY_ID, C.COMPANY_NAME, 1, C.EMAIL_DOMAIN, C.CURRENCY, C.AS_OF.isoformat(), C.YEAR_START.isoformat(),
                 C.HORIZON_END.isoformat(), C.SEED, generated_at))
    con.executemany("INSERT INTO periods VALUES (?,?,?,?)", [(p["id"], p["label"], p["start"].isoformat(), p["end"].isoformat()) for p in C.PERIODS])
    con.executemany("INSERT INTO teams VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(t.id, t.name, t.description, t.cost_center, t.lead_id, t.color, t.tool, j(t.provider_mix), t.weekend, t.growth) for t in teams])
    con.executemany("INSERT INTO people VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(p.id, p.team_id, p.name, p.role, p.level, p.email, p.tool, p.start_date.isoformat(),
                      p.end_date.isoformat() if p.end_date else None, int(p.is_lead), p.timezone, j(p.integrations),
                      int(p.base_tokens_k * 1000), round(p.weekend_factor, 3)) for p in people])
    con.executemany("INSERT INTO providers VALUES (?,?)", list(C.PROVIDERS.items()) + [("cursor", "Cursor"), ("github", "GitHub")])
    con.executemany("INSERT INTO models VALUES (?,?,?,?,?,?,?,?)",
                    [(mid, v[0], v[1], v[2], v[3], v[4], v[5].isoformat(), int(v[6])) for mid, v in C.MODELS.items()])
    price_rows = [(mid, v[5].isoformat(), v[2], v[3], v[4]) for mid, v in C.MODELS.items()]
    price_rows += [(mid, eff.isoformat(), i, c, o) for mid, eff, i, c, o in C.PRICE_CHANGES]
    con.executemany("INSERT INTO model_prices VALUES (?,?,?,?,?)", price_rows)
    con.executemany("INSERT INTO model_events VALUES (?,?,?,?,?,?,?)",
                    [(m.id, m.provider, j(m.model_ids), m.kind, m.announced_on.isoformat(), m.effective_on.isoformat(), j(m.details)) for m in story.model_events])
    con.executemany("INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(c.day.isoformat(), c.weekday, c.day.strftime("%A"), int(c.is_weekend), c.holiday, c.holiday_factor, c.seasonal_factor,
                      c.period_id, int(c.partial), int(c.day > C.AS_OF)) for c in calendar.values()])
    con.executemany("INSERT INTO projects VALUES (?,?,?)",
                    [(f"{t.id}:{i + 1}", t.id, name) for t in teams for i, name in enumerate(t.projects)])
    con.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(e.id, e.kind, e.scope, j(e.team_ids), j(e.person_ids), e.project, e.starts_on.isoformat(),
                      e.ends_on.isoformat() if e.ends_on else None, e.multiplier, e.weekend_multiplier, j(e.model_override) if e.model_override else None,
                      j(e.provider_shift) if e.provider_shift else None, e.announced_on.isoformat(), e.title, e.summary, e.expected_effect,
                      e.category, e.confidence, e.claim_type, e.magnitude_pct, e.uncertainty, int(e.future)) for e in story.events])
    con.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(m.id, m.event_id, m.channel, m.sent_at.isoformat(), m.weekday, m.from_person_id, m.from_name, j(m.to), m.where, m.body,
                      j(m.team_ids), j(m.person_ids)) for m in story.messages])
    con.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(t.id, t.event_id, t.tool, t.board, t.title, t.assignee_id, t.assignee_name, t.created_at.isoformat(),
                      t.due_on.isoformat() if t.due_on else None, t.prev_due_on.isoformat() if t.prev_due_on else None, t.status, t.prev_status,
                      t.status_changed_at.isoformat() if t.status_changed_at else None, t.body, j(t.team_ids), j(t.person_ids)) for t in story.tasks])

    def usage_tuples(rows):
        for r in rows:
            yield (r.day.isoformat(), r.person_id, r.team_id, r.provider, r.model_id, r.model_name, r.tool, r.cost_category,
                   r.input_tokens, r.cached_input_tokens, r.output_tokens, r.reasoning_tokens,
                   r.input_tokens + r.output_tokens, r.requests, round(r.cost_usd, 4), round(r.notional_usd, 4), period_of(r.day))

    def period_of(d: date):
        for p in C.PERIODS:
            if p["start"] <= d <= p["end"]:
                return p["id"]
        return None

    con.executemany("INSERT INTO usage_daily (day, person_id, team_id, provider, model_id, model, tool, cost_category, input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, total_tokens, requests, cost_usd, notional_usd, period_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", usage_tuples(usage_rows))
    con.executemany("INSERT INTO usage_daily_holdout (day, person_id, team_id, provider, model_id, model, tool, cost_category, input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, total_tokens, requests, cost_usd, notional_usd, period_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", usage_tuples(holdout_rows))
    con.executemany("INSERT INTO seat_subscriptions (month, person_id, team_id, tool, provider, amount_usd, period_id) VALUES (?,?,?,?,?,?,?)",
                    [(s.month.isoformat(), s.person_id, s.team_id, s.tool, s.provider, s.amount_usd, period_of(s.month)) for s in seat_rows])
    con.executemany("INSERT INTO seat_subscriptions_holdout (month, person_id, team_id, tool, provider, amount_usd, period_id) VALUES (?,?,?,?,?,?,?)",
                    [(s.month.isoformat(), s.person_id, s.team_id, s.tool, s.provider, s.amount_usd, period_of(s.month)) for s in holdout_seats])
    con.executemany("INSERT INTO budgets VALUES (?,?,?,?)", [(b["team_id"], b["period_id"], b["allocated_usd"], b["actual_usd_to_date"]) for b in budgets])
    con.commit()
    con.execute("VACUUM")
    con.close()
