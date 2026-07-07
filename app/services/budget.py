from app import config
from app.db import core


class BudgetExceeded(Exception):
    pass


def estimate_tokens(text):
    return max(1, len(text) // 4)


def estimate_llm_cost(input_chars, output_tokens=None):
    output_tokens = output_tokens or config.LLM_MAX_OUTPUT_TOKENS
    input_cost = estimate_tokens("x" * input_chars) * config.LLM_PRICE_IN_PER_M / 1_000_000
    output_cost = output_tokens * config.LLM_PRICE_OUT_PER_M / 1_000_000
    return input_cost + output_cost


def actual_llm_cost(input_tokens, output_tokens):
    return (input_tokens * config.LLM_PRICE_IN_PER_M
            + output_tokens * config.LLM_PRICE_OUT_PER_M) / 1_000_000


def spent_today():
    row = core.query_one(
        "SELECT COALESCE(SUM(amount_usd), 0) AS spent, COUNT(*) AS calls "
        "FROM spend_ledger WHERE day = date('now')"
    )
    return row["spent"], row["calls"]


def record(kind, amount_usd):
    core.execute(
        "INSERT INTO spend_ledger(kind, amount_usd) VALUES(?, ?)", (kind, amount_usd)
    )


def guard(kind, estimated_usd):
    if estimated_usd > config.REQUEST_MAX_USD:
        raise BudgetExceeded(
            f"{kind} request estimated at ${estimated_usd:.4f}, "
            f"per-request ceiling is ${config.REQUEST_MAX_USD:.4f}"
        )
    spent, calls = spent_today()
    if calls >= config.DAILY_LLM_CALL_CAP:
        raise BudgetExceeded(f"daily call cap of {config.DAILY_LLM_CALL_CAP} reached")
    if spent + estimated_usd > config.DAILY_BUDGET_USD:
        raise BudgetExceeded(
            f"daily budget of ${config.DAILY_BUDGET_USD:.2f} would be exceeded "
            f"(spent ${spent:.4f} today)"
        )


def status():
    spent, calls = spent_today()
    return {
        "spent_today_usd": round(spent, 4),
        "calls_today": calls,
        "daily_budget_usd": config.DAILY_BUDGET_USD,
        "daily_call_cap": config.DAILY_LLM_CALL_CAP,
        "exceeded": spent >= config.DAILY_BUDGET_USD or calls >= config.DAILY_LLM_CALL_CAP,
    }
