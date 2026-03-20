"""
Budget model definitions.

Each model specifies named buckets with category assignments and targets.
The calculator is model-agnostic — add a new model here and it Just Works.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bucket:
    name: str
    label: str
    target_pct: float | None  # None = informational only, no target
    # "lte" → spending bucket (on_track when actual <= target)
    # "gte" → savings bucket (on_track when actual >= target)
    # None  → no on_track assessment
    on_track_direction: str | None
    categories: frozenset[str]


@dataclass(frozen=True)
class BudgetModel:
    key: str
    name: str
    description: str
    buckets: list[Bucket]
    # Which bucket uncategorized expenses land in
    default_bucket: str


# ---------------------------------------------------------------------------
# 50 / 30 / 20  (Elizabeth Warren)
# ---------------------------------------------------------------------------
MODEL_50_30_20 = BudgetModel(
    key="50_30_20",
    name="50/30/20",
    description="50% needs, 30% wants, 20% savings & debt repayment.",
    buckets=[
        Bucket(
            name="needs",
            label="Needs",
            target_pct=50,
            on_track_direction="lte",
            categories=frozenset(
                {
                    "housing",
                    "utilities",
                    "groceries",
                    "insurance",
                    "healthcare",
                    "transport",
                    "childcare",
                    "education",
                }
            ),
        ),
        Bucket(
            name="wants",
            label="Wants",
            target_pct=30,
            on_track_direction="lte",
            categories=frozenset(
                {
                    "dining",
                    "entertainment",
                    "shopping",
                    "travel",
                    "subscriptions",
                    "personal_care",
                    "gifts",
                    "fitness",
                }
            ),
        ),
        Bucket(
            name="savings",
            label="Savings & Debt",
            target_pct=20,
            on_track_direction="gte",
            categories=frozenset(
                {
                    "savings",
                    "investment",
                    "retirement",
                    "debt_payment",
                }
            ),
        ),
    ],
    default_bucket="wants",
)

# ---------------------------------------------------------------------------
# 70 / 20 / 10
# ---------------------------------------------------------------------------
MODEL_70_20_10 = BudgetModel(
    key="70_20_10",
    name="70/20/10",
    description="70% living expenses, 20% savings, 10% giving & debt.",
    buckets=[
        Bucket(
            name="living",
            label="Living Expenses",
            target_pct=70,
            on_track_direction="lte",
            categories=frozenset(
                {
                    "housing",
                    "utilities",
                    "groceries",
                    "insurance",
                    "healthcare",
                    "transport",
                    "childcare",
                    "education",
                    "dining",
                    "entertainment",
                    "shopping",
                    "travel",
                    "subscriptions",
                    "personal_care",
                    "fitness",
                }
            ),
        ),
        Bucket(
            name="savings",
            label="Savings & Investing",
            target_pct=20,
            on_track_direction="gte",
            categories=frozenset(
                {
                    "savings",
                    "investment",
                    "retirement",
                }
            ),
        ),
        Bucket(
            name="giving_debt",
            label="Giving & Debt",
            target_pct=10,
            on_track_direction="lte",
            categories=frozenset(
                {
                    "gifts",
                    "charity",
                    "debt_payment",
                }
            ),
        ),
    ],
    default_bucket="living",
)

# ---------------------------------------------------------------------------
# 80 / 20  ("Pay yourself first")
# ---------------------------------------------------------------------------
MODEL_80_20 = BudgetModel(
    key="80_20",
    name="80/20 (Pay yourself first)",
    description="Save 20% off the top; spend the remaining 80% however you like.",
    buckets=[
        Bucket(
            name="savings",
            label="Savings & Investing",
            target_pct=20,
            on_track_direction="gte",
            categories=frozenset(
                {
                    "savings",
                    "investment",
                    "retirement",
                    "debt_payment",
                }
            ),
        ),
        Bucket(
            name="spending",
            label="Spending",
            target_pct=80,
            on_track_direction="lte",
            categories=frozenset(
                {
                    "housing",
                    "utilities",
                    "groceries",
                    "insurance",
                    "healthcare",
                    "transport",
                    "childcare",
                    "education",
                    "dining",
                    "entertainment",
                    "shopping",
                    "travel",
                    "subscriptions",
                    "personal_care",
                    "gifts",
                    "fitness",
                    "charity",
                }
            ),
        ),
    ],
    default_bucket="spending",
)

# ---------------------------------------------------------------------------
# Zero-based  (every dollar assigned; goal: remaining == 0)
# Sentinel model — calculator handles this one specially.
# ---------------------------------------------------------------------------
MODEL_ZERO_BASED = BudgetModel(
    key="zero_based",
    name="Zero-based",
    description=(
        "Every dollar gets a job. Income minus all categorised spending should equal zero. "
        "Displays each category as its own line item."
    ),
    buckets=[],  # calculator drives off raw transaction categories
    default_bucket="",  # unused
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
MODELS: dict[str, BudgetModel] = {
    m.key: m
    for m in [
        MODEL_50_30_20,
        MODEL_70_20_10,
        MODEL_80_20,
        MODEL_ZERO_BASED,
    ]
}

DEFAULT_MODEL = "50_30_20"
