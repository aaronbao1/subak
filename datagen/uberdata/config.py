"""Static configuration for the simulated company dataset.

Everything here is fictional: the company, the people, the model line-up, the list prices and
every message. The company is modelled on a large ride-hailing / delivery business and labelled
"Uber (simulated)" purely as a familiar stand-in; nothing is derived from any real account.
"""
from __future__ import annotations

from datetime import date

SEED = 20261024
COMPANY_ID = "uber-sim"
COMPANY_NAME = "Uber (simulated)"
EMAIL_DOMAIN = "uber.example"
CURRENCY = "USD"

YEAR_START = date(2026, 1, 1)
AS_OF = date(2026, 10, 24)          # last recorded day (partial by default)
COMPLETE_AS_OF_DAY = False        # opt in to a full final day without changing prior history
HORIZON_END = date(2026, 12, 31)    # planning horizon for future-dated evidence

# Planning periods used by the backend: calendar quarters. Q4 is the "current" period on AS_OF.
PERIODS = [
    {"id": "2026-Q1", "label": "Q1 2026", "start": date(2026, 1, 1), "end": date(2026, 3, 31)},
    {"id": "2026-Q2", "label": "Q2 2026", "start": date(2026, 4, 1), "end": date(2026, 6, 30)},
    {"id": "2026-Q3", "label": "Q3 2026", "start": date(2026, 7, 1), "end": date(2026, 9, 30)},
    {"id": "2026-Q4", "label": "Q4 2026", "start": date(2026, 10, 1), "end": date(2026, 12, 31)},
]

# ---------------------------------------------------------------------------------------------
# Calendar: US public holidays observed by the company in 2026, plus closures and half days.
# factor = fraction of a normal weekday's activity expected on that day.
# ---------------------------------------------------------------------------------------------
HOLIDAYS = {
    date(2026, 1, 1): ("New Year's Day", 0.12),
    date(2026, 1, 2): ("Day after New Year's (office closed)", 0.35),
    date(2026, 1, 19): ("Martin Luther King Jr. Day", 0.30),
    date(2026, 2, 16): ("Presidents' Day", 0.35),
    date(2026, 5, 25): ("Memorial Day", 0.25),
    date(2026, 6, 19): ("Juneteenth", 0.30),
    date(2026, 7, 3): ("Independence Day (observed)", 0.20),
    date(2026, 9, 7): ("Labor Day", 0.25),
    date(2026, 11, 26): ("Thanksgiving Day", 0.10),
    date(2026, 11, 27): ("Day after Thanksgiving (office closed)", 0.20),
    date(2026, 12, 24): ("Christmas Eve (half day)", 0.40),
    date(2026, 12, 25): ("Christmas Day", 0.08),
    date(2026, 12, 31): ("New Year's Eve (half day)", 0.40),
}
# Company-wide "recharge" Fridays announced by People Ops.
RECHARGE_DAYS = {
    date(2026, 3, 27): ("Recharge Friday", 0.30),
    date(2026, 8, 14): ("Recharge Friday", 0.30),
}
# Weeks where many people take leave (fraction of normal activity).
SEASONAL = [
    (date(2026, 6, 29), date(2026, 7, 10), 0.82),   # around July 4th
    (date(2026, 8, 17), date(2026, 8, 28), 0.88),   # late summer
    (date(2026, 12, 21), date(2026, 12, 31), 0.45), # year-end shutdown (future)
]
WEEKDAY_FACTOR = {0: 0.96, 1: 1.0, 2: 1.0, 3: 0.98, 4: 0.88, 5: 0.0, 6: 0.0}  # Sat/Sun set per role
DEFAULT_WEEKEND_FACTOR = 0.16

# ---------------------------------------------------------------------------------------------
# Providers, models and (fictional) list prices in USD per million tokens.
# "cached" is the price for cached input tokens.
# ---------------------------------------------------------------------------------------------
PROVIDERS = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
}

MODELS = {
    # id: (provider, display name, input, cached input, output, released_on, reasoning?)
    "claude-opus-4.5":   ("anthropic", "Claude Opus 4.5",   15.00, 1.50, 75.00, date(2025, 11, 24), False),
    "claude-sonnet-4.5": ("anthropic", "Claude Sonnet 4.5",  3.00, 0.30, 15.00, date(2025, 9, 29), False),
    "claude-haiku-4.5":  ("anthropic", "Claude Haiku 4.5",   1.00, 0.10,  5.00, date(2025, 10, 15), False),
    "claude-opus-5.5":   ("anthropic", "Claude Opus 5.5",   15.00, 1.50, 75.00, date(2026, 3, 17), False),
    "claude-sonnet-5.5": ("anthropic", "Claude Sonnet 5.5",  3.00, 0.30, 15.00, date(2026, 3, 17), False),
    "claude-haiku-5.5":  ("anthropic", "Claude Haiku 5.5",   1.00, 0.10,  5.00, date(2026, 3, 17), False),
    "claude-fable-5.1":  ("anthropic", "Claude Fable 5.1",  25.00, 2.50, 125.00, date(2026, 10, 17), False),
    "gpt-5.2":           ("openai",    "GPT-5.2",            1.75, 0.175, 14.00, date(2025, 12, 11), True),
    "gpt-5.2-mini":      ("openai",    "GPT-5.2 mini",       0.40, 0.04,  1.60, date(2025, 12, 11), True),
    "gpt-5.5":           ("openai",    "GPT-5.5",            2.50, 0.25, 15.00, date(2026, 5, 12), True),
    "gpt-5.5-mini":      ("openai",    "GPT-5.5 mini",       0.50, 0.05,  2.00, date(2026, 5, 12), True),
    "gemini-3-pro":      ("google",    "Gemini 3 Pro",       2.00, 0.20, 12.00, date(2025, 11, 18), True),
    "gemini-3-flash":    ("google",    "Gemini 3 Flash",     0.50, 0.05,  3.00, date(2025, 12, 17), True),
    "gemini-3.5-pro":    ("google",    "Gemini 3.5 Pro",     2.50, 0.25, 15.00, date(2026, 2, 10), True),
    "gemini-3.5-flash":  ("google",    "Gemini 3.5 Flash",   0.60, 0.06,  3.50, date(2026, 2, 10), True),
}

# Price changes during the year: (model, effective_on, input, cached, output)
PRICE_CHANGES = [
    ("gpt-5.5-mini", date(2026, 8, 1), 0.30, 0.03, 1.20),      # OpenAI cut mini pricing 40%
    ("claude-haiku-5.5", date(2026, 9, 15), 0.80, 0.08, 4.00),  # Anthropic Haiku price cut
]

# Model line-up per provider over time. Each entry: (effective_from, {model: share}).
# Shares ramp linearly over RAMP_DAYS after effective_from.
RAMP_DAYS = 21
MODEL_MIX_TIMELINE = {
    "anthropic": [
        (date(2026, 1, 1),  {"claude-opus-4.5": 0.30, "claude-sonnet-4.5": 0.55, "claude-haiku-4.5": 0.15}),
        (date(2026, 4, 1),  {"claude-opus-5.5": 0.35, "claude-sonnet-5.5": 0.50, "claude-haiku-5.5": 0.15}),
        # Fable 5.1 adoption is announced but starts after AS_OF (Oct 31 pilots, Nov 16 company-wide).
        (date(2026, 10, 31), {"claude-fable-5.1": 0.30, "claude-opus-5.5": 0.15, "claude-sonnet-5.5": 0.42, "claude-haiku-5.5": 0.13}),
    ],
    "openai": [
        (date(2026, 1, 1),  {"gpt-5.2": 0.68, "gpt-5.2-mini": 0.32}),
        (date(2026, 5, 26), {"gpt-5.5": 0.66, "gpt-5.5-mini": 0.34}),
    ],
    "google": [
        (date(2026, 1, 1),  {"gemini-3-pro": 0.60, "gemini-3-flash": 0.40}),
        (date(2026, 2, 24), {"gemini-3.5-pro": 0.58, "gemini-3.5-flash": 0.42}),
    ],
}

# Company-wide provider-mix adjustments (policy). (effective_from, {provider: additive share}, note)
PROVIDER_POLICY_SHIFTS = [
    (date(2026, 6, 1), {"google": +0.10, "anthropic": -0.05, "openai": -0.05},
     "Gemini enabled for all employees (previously Maps & Routing and Data Platform only)"),
]

# Company-wide usage multipliers around model adoptions (comparison runs, re-evals): (start, end, factor)
COMPANY_BUMPS = [
    (date(2026, 2, 24), date(2026, 3, 9), 1.10),   # Gemini 3.5 adoption
    (date(2026, 4, 1), date(2026, 4, 17), 1.22),   # Claude 5.5 family adoption
    (date(2026, 5, 26), date(2026, 6, 8), 1.12),   # GPT-5.5 adoption
    (date(2026, 11, 16), date(2026, 12, 4), 1.25), # Fable 5.1 company-wide (future, for projections)
]

# Seat subscriptions (fictional list prices per seat per month).
TOOLS = {
    "Cursor":             {"provider": "cursor",    "seat_usd": 40.0,  "overage_share": 0.18},
    "Claude Code":        {"provider": "anthropic", "seat_usd": 0.0,   "overage_share": 0.0},   # billed via API
    "GitHub Copilot":     {"provider": "github",    "seat_usd": 39.0,  "overage_share": 0.05},
    "ChatGPT Enterprise": {"provider": "openai",    "seat_usd": 60.0,  "included": True},
    "Gemini Enterprise":  {"provider": "google",    "seat_usd": 30.0,  "included": True},
}

# ---------------------------------------------------------------------------------------------
# Teams. provider_mix = baseline split of API tokens across providers.
# intensity scales every member's daily volume; weekend = weekend factor for the team.
# ---------------------------------------------------------------------------------------------
TEAMS = [
    {"id": "rider-app", "name": "Rider App", "description": "Rider mobile apps: trip booking, pickup experience, in-app support",
     "cost_center": "CC-1101", "provider_mix": {"anthropic": 0.62, "openai": 0.28, "google": 0.10}, "intensity": 1.00, "weekend": 0.14,
     "tool": "Cursor", "headcount": 11, "growth": 1.6, "color": "oklch(0.62 0.13 20)"},
    {"id": "driver-app", "name": "Driver App", "description": "Driver-partner app: dispatch, earnings, navigation hand-off",
     "cost_center": "CC-1102", "provider_mix": {"anthropic": 0.58, "openai": 0.30, "google": 0.12}, "intensity": 0.95, "weekend": 0.14,
     "tool": "Cursor", "headcount": 10, "growth": 1.55, "color": "oklch(0.62 0.13 45)"},
    {"id": "marketplace-pricing", "name": "Marketplace & Pricing", "description": "Dynamic pricing, matching, surge and ETA economics",
     "cost_center": "CC-1201", "provider_mix": {"anthropic": 0.30, "openai": 0.55, "google": 0.15}, "intensity": 1.35, "weekend": 0.22,
     "tool": "Claude Code", "headcount": 9, "growth": 1.9, "color": "oklch(0.62 0.13 70)"},
    {"id": "maps-routing", "name": "Maps & Routing", "description": "Map data, routing, ETA models and geospatial tooling",
     "cost_center": "CC-1202", "provider_mix": {"anthropic": 0.25, "openai": 0.20, "google": 0.55}, "intensity": 1.15, "weekend": 0.18,
     "tool": "Cursor", "headcount": 9, "growth": 1.7, "color": "oklch(0.62 0.13 95)"},
    {"id": "eats-delivery", "name": "Eats Delivery", "description": "Food and grocery delivery: merchant tools, courier flows, order tracking",
     "cost_center": "CC-1301", "provider_mix": {"anthropic": 0.60, "openai": 0.30, "google": 0.10}, "intensity": 1.00, "weekend": 0.16,
     "tool": "Cursor", "headcount": 10, "growth": 1.6, "color": "oklch(0.62 0.13 120)"},
    {"id": "freight", "name": "Freight", "description": "Freight marketplace: shipper portal, carrier matching, load dispatch",
     "cost_center": "CC-1401", "provider_mix": {"anthropic": 0.35, "openai": 0.55, "google": 0.10}, "intensity": 0.85, "weekend": 0.12,
     "tool": "GitHub Copilot", "headcount": 7, "growth": 1.4, "color": "oklch(0.62 0.13 145)"},
    {"id": "safety-trust", "name": "Safety & Trust", "description": "Trip safety features, identity verification, incident review tooling",
     "cost_center": "CC-1501", "provider_mix": {"anthropic": 0.70, "openai": 0.20, "google": 0.10}, "intensity": 1.10, "weekend": 0.20,
     "tool": "Claude Code", "headcount": 8, "growth": 1.75, "color": "oklch(0.62 0.13 170)"},
    {"id": "payments-risk", "name": "Payments & Risk", "description": "Payments, payouts, fraud and chargeback risk models",
     "cost_center": "CC-1601", "provider_mix": {"anthropic": 0.40, "openai": 0.48, "google": 0.12}, "intensity": 1.05, "weekend": 0.18,
     "tool": "Cursor", "headcount": 9, "growth": 1.6, "color": "oklch(0.62 0.13 195)"},
    {"id": "data-platform", "name": "Data Platform", "description": "Warehouse, pipelines, metrics layer and experimentation platform",
     "cost_center": "CC-1701", "provider_mix": {"anthropic": 0.30, "openai": 0.25, "google": 0.45}, "intensity": 1.20, "weekend": 0.18,
     "tool": "Claude Code", "headcount": 9, "growth": 1.7, "color": "oklch(0.62 0.13 220)"},
    {"id": "ai-labs", "name": "AI Labs", "description": "Applied AI research: assistants, evaluation harnesses, model adoption",
     "cost_center": "CC-1801", "provider_mix": {"anthropic": 0.62, "openai": 0.23, "google": 0.15}, "intensity": 2.10, "weekend": 0.30,
     "tool": "Claude Code", "headcount": 8, "growth": 2.3, "color": "oklch(0.62 0.13 245)"},
    {"id": "infra-sre", "name": "Infrastructure & SRE", "description": "Compute, networking, CI/CD, observability and on-call",
     "cost_center": "CC-1901", "provider_mix": {"anthropic": 0.40, "openai": 0.48, "google": 0.12}, "intensity": 1.05, "weekend": 0.34,
     "tool": "Cursor", "headcount": 9, "growth": 1.5, "color": "oklch(0.62 0.13 270)"},
    {"id": "support-automation", "name": "Customer Support Automation", "description": "Ticket triage, reply drafting and support agent assist",
     "cost_center": "CC-2001", "provider_mix": {"anthropic": 0.45, "openai": 0.45, "google": 0.10}, "intensity": 1.45, "weekend": 0.28,
     "tool": "Claude Code", "headcount": 8, "growth": 2.0, "color": "oklch(0.62 0.13 295)"},
    {"id": "security", "name": "Security", "description": "Application security, detection engineering, vendor review",
     "cost_center": "CC-2101", "provider_mix": {"anthropic": 0.65, "openai": 0.25, "google": 0.10}, "intensity": 0.80, "weekend": 0.20,
     "tool": "GitHub Copilot", "headcount": 6, "growth": 1.45, "color": "oklch(0.62 0.13 320)"},
    {"id": "finance-legal", "name": "Finance & Legal Ops", "description": "FP&A automation, contract review, close and audit support",
     "cost_center": "CC-2201", "provider_mix": {"anthropic": 0.55, "openai": 0.40, "google": 0.05}, "intensity": 0.45, "weekend": 0.08,
     "tool": "ChatGPT Enterprise", "headcount": 6, "growth": 1.5, "color": "oklch(0.62 0.13 345)"},
    {"id": "people-recruiting", "name": "People & Recruiting", "description": "Recruiting, internal comms and HR operations",
     "cost_center": "CC-2301", "provider_mix": {"anthropic": 0.25, "openai": 0.30, "google": 0.45}, "intensity": 0.35, "weekend": 0.06,
     "tool": "Gemini Enterprise", "headcount": 5, "growth": 1.35, "color": "oklch(0.62 0.13 10)"},
    {"id": "marketing-comms", "name": "Marketing & Comms", "description": "Campaign content, lifecycle messaging, brand and PR",
     "cost_center": "CC-2401", "provider_mix": {"anthropic": 0.35, "openai": 0.55, "google": 0.10}, "intensity": 0.55, "weekend": 0.10,
     "tool": "ChatGPT Enterprise", "headcount": 6, "growth": 1.5, "color": "oklch(0.62 0.13 60)"},
]

# Roles: (title, daily tokens on a normal weekday in thousands BEFORE TOKEN_SCALE, input share, cache rate, weight in team)
# Agentic coding tools push heavy users to several million tokens a day; TOKEN_SCALE lifts the role baselines to that level.
TOKEN_SCALE = 8.0
ENGINEERING_ROLES = [
    ("Staff Engineer", 950, 0.86, 0.48, 1.0),
    ("Senior Engineer", 720, 0.85, 0.45, 2.5),
    ("Software Engineer", 560, 0.84, 0.42, 3.0),
    ("ML Engineer", 1250, 0.80, 0.40, 1.2),
    ("Data Scientist", 820, 0.78, 0.38, 1.0),
    ("Site Reliability Engineer", 640, 0.84, 0.44, 0.8),
    ("Product Manager", 190, 0.70, 0.30, 1.0),
    ("Product Designer", 130, 0.68, 0.28, 0.6),
    ("Engineering Manager", 320, 0.76, 0.35, 0.8),
]
BUSINESS_ROLES = [
    ("Financial Analyst", 260, 0.72, 0.32, 2.0),
    ("Corporate Counsel", 110, 0.70, 0.30, 1.0),
    ("Recruiter", 90, 0.66, 0.25, 2.0),
    ("Content Strategist", 170, 0.68, 0.26, 2.0),
    ("Marketing Manager", 150, 0.70, 0.30, 1.5),
    ("People Operations Partner", 95, 0.66, 0.25, 1.0),
    ("Operations Analyst", 240, 0.72, 0.32, 1.5),
]
BUSINESS_TEAMS = {"finance-legal", "people-recruiting", "marketing-comms"}

FIRST_NAMES = [
    "Aaliyah", "Adrian", "Aisha", "Alejandro", "Amara", "Anika", "Arjun", "Beatriz", "Bianca", "Caleb", "Camila",
    "Chidi", "Clara", "Daniel", "Dara", "Devon", "Diego", "Elena", "Elif", "Emeka", "Esther", "Ezra", "Farah",
    "Felix", "Fatima", "Gabriel", "Grace", "Hana", "Hiro", "Idris", "Imani", "Ines", "Isaac", "Ivan", "Jamal",
    "Jonas", "Jun", "Kavya", "Keiko", "Kofi", "Laila", "Leo", "Lucia", "Luis", "Mai", "Malik", "Marcus", "Mateo",
    "Maya", "Mei", "Mikael", "Nadia", "Naomi", "Nikhil", "Noor", "Olamide", "Oliver", "Omar", "Priya", "Rafael",
    "Ravi", "Rosa", "Ruth", "Sana", "Santiago", "Sebastian", "Selin", "Simone", "Sofia", "Tariq", "Tomas", "Uma",
    "Valentina", "Victor", "Wei", "Yara", "Yusuf", "Zainab", "Zoe", "Ahmed", "Anya", "Bruno", "Celine", "Dmitri",
]
LAST_NAMES = [
    "Abara", "Adeyemi", "Ahmed", "Alvarez", "Andersen", "Banerjee", "Bauer", "Bello", "Brennan", "Castillo", "Chen",
    "Choi", "Costa", "Dubois", "Eriksen", "Fernandes", "Fischer", "Flores", "Garcia", "Gupta", "Haddad", "Hassan",
    "Hernandez", "Ibrahim", "Ito", "Jensen", "Kaur", "Khan", "Kim", "Kowalski", "Kumar", "Larsen", "Lee", "Lima",
    "Lopez", "Mahmoud", "Marin", "Mendes", "Mensah", "Morales", "Nakamura", "Nguyen", "Novak", "Okafor", "Oliveira",
    "Osei", "Park", "Patel", "Pereira", "Petrov", "Popescu", "Quinn", "Rahman", "Ramirez", "Reyes", "Rossi", "Sato",
    "Schmidt", "Silva", "Singh", "Sousa", "Suzuki", "Tanaka", "Torres", "Tran", "Varga", "Vasquez", "Wang", "Yilmaz",
    "Zhang", "Zhou",
]

PROJECTS = {
    "rider-app": ["Pickup Spot Guidance v3", "Rider Support Copilot", "Trip Receipt Redesign"],
    "driver-app": ["Earnings Explainer", "Dispatch Offer Card Refresh", "Driver Assist Chat"],
    "marketplace-pricing": ["Surge Model Retrain", "Matching Latency Reduction", "Pricing Explainability"],
    "maps-routing": ["ETA Model v7", "Map Edit Copilot", "Routing Fallback Resilience"],
    "eats-delivery": ["Merchant Menu Assistant", "Courier Batching Optimizer", "Order Tracking Overhaul"],
    "freight": ["AI Dispatch v2", "Shipper Quote Assistant", "Carrier Document Extraction"],
    "safety-trust": ["Incident Summarization", "Identity Check Modernization", "Trip Audio Review Tooling"],
    "payments-risk": ["Chargeback Triage Assistant", "Payout Anomaly Detection", "Fraud Rules Migration"],
    "data-platform": ["Metrics Layer Semantic Search", "Pipeline Lineage Copilot", "Warehouse Cost Governance"],
    "ai-labs": ["Agent Evaluation Harness", "Model Adoption Program", "Internal Assistant Platform"],
    "infra-sre": ["Incident Response Copilot", "CI Flake Reduction", "Kubernetes Fleet Upgrade"],
    "support-automation": ["Ticket Auto-Triage v2", "Reply Drafting Rollout", "Support Agent Assist"],
    "security": ["Vendor Review Automation", "Detection Rule Authoring", "AppSec Review Copilot"],
    "finance-legal": ["Contract Clause Extraction", "Close Automation", "Audit Evidence Assistant"],
    "people-recruiting": ["Interview Note Summaries", "Job Description Assistant", "Policy FAQ Bot"],
    "marketing-comms": ["Lifecycle Campaign Generator", "Brand Voice Checker", "Localization Pipeline"],
}
