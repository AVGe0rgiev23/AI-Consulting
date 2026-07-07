from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).with_name("templates")


class _Templates(Jinja2Templates):
    def TemplateResponse(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.pop("context", {})
            request = context.get("request")
            extra = {k: v for k, v in kwargs.items() if k not in ("context",)}
            return super().TemplateResponse(
                request=request, name=name, context=context, **extra
            )
        return super().TemplateResponse(*args, **kwargs)


templates = _Templates(directory=str(TEMPLATE_DIR))


def score_class(score):
    if score >= 80:
        return "good"
    if score >= 60:
        return "warn"
    return "bad"


def confidence(quality):
    from app.services.research import confidence_label

    return confidence_label(quality)


def confidence_class(quality):
    return {"high": "good", "medium": "warn", "low": "bad"}[confidence(quality)]


templates.env.filters["score_class"] = score_class
templates.env.filters["confidence"] = confidence
templates.env.filters["confidence_class"] = confidence_class
