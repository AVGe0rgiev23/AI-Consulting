from app.llm import score


def test_slop_phrases_penalized():
    findings = [{"claim": "acme uses quote-based pricing", "id": 1}]
    clean = ("I was going to call about your dispatch team but figured I'd write first. "
             "You use quote-based pricing which likely slows deals. "
             "I built a short example for you with the numbers. Mind if I send it over?")
    slop = "I came across your amazing website and hope you're doing well. Want to book a call?"
    clean_score, _ = score.score_asset(clean, findings)
    slop_score, breakdown = score.score_asset(slop, findings)
    assert clean_score > slop_score
    assert breakdown["slop_hits"]


def test_soft_question_cta_scores_higher_than_imperative():
    findings = [{"claim": "hiring dispatchers", "id": 1}]
    soft = ("You're hiring dispatchers, so quoting is probably getting tighter. "
            "I put together an example. Mind if I send it?")
    hard = ("You're hiring dispatchers, so quoting is probably getting tighter. "
            "Book a call here now.")
    assert score.score_asset(soft, findings)[0] >= score.score_asset(hard, findings)[0]


def test_grounded_email_beats_generic():
    findings = [{"claim": "acme uses quote-based pricing with slow turnaround", "id": 1}]
    grounded = ("Your quote-based pricing likely means slow turnaround costs deals. "
                "Built an example. Send it over?")
    generic = "We help companies grow revenue with our platform. Interested?"
    assert score.score_asset(grounded, findings)[0] > score.score_asset(generic, findings)[0]
