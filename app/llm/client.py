import json

from app import config
from app.services import budget


def complete_json(model, system, user, stub_fn):
    if config.USE_LLM_STUB:
        return stub_fn()
    text = _guarded_call(model, system, user)
    if text is None:
        return stub_fn()
    return _extract_json(text, stub_fn)


def complete_text(model, system, user, stub_fn):
    if config.USE_LLM_STUB:
        return stub_fn()
    text = _guarded_call(model, system, user)
    if text is None:
        return stub_fn()
    return text.strip()


def _guarded_call(model, system, user):
    user = user[: config.LLM_MAX_INPUT_CHARS]
    try:
        budget.guard("llm", budget.estimate_llm_cost(len(system) + len(user)))
    except budget.BudgetExceeded:
        return None
    try:
        text, in_tokens, out_tokens = _llm_call(model, system, user)
    except Exception:
        budget.record("llm_failed", 0.0)
        return None
    budget.record("llm", budget.actual_llm_cost(in_tokens, out_tokens))
    return text


def _llm_call(model, system, user):
    if config.LLM_PROVIDER == "anthropic":
        return _anthropic_call(model, system, user)
    return _openai_compat_call(model, system, user)


def _anthropic_call(model, system, user):
    import anthropic

    client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    msg = client.messages.create(
        model=model,
        max_tokens=config.LLM_MAX_OUTPUT_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    return text, msg.usage.input_tokens, msg.usage.output_tokens


def _openai_compat_call(model, system, user):
    import httpx

    base_url = config.OPENAI_COMPAT_BASES[config.LLM_PROVIDER]
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        json={
            "model": model,
            "max_tokens": config.LLM_MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"]["content"] or ""
    usage = data.get("usage", {})
    in_tokens = usage.get("prompt_tokens", budget.estimate_tokens(system + user))
    out_tokens = usage.get("completion_tokens", budget.estimate_tokens(text))
    return text, in_tokens, out_tokens


def _extract_json(text, stub_fn):
    start = text.find("{")
    start_arr = text.find("[")
    if start_arr != -1 and (start == -1 or start_arr < start):
        start = start_arr
    if start == -1:
        return stub_fn()
    depth = 0
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    for i in range(start, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return stub_fn()
    return stub_fn()
