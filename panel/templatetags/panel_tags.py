from django import template

register = template.Library()


@register.filter
def num(value):
    """1234567 -> '1 234 567'"""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return value


@register.filter
def som(value):
    formatted = num(value)
    return f"{formatted} so'm" if formatted != value else value


@register.filter
def money(value, currency="UZS"):
    """Foydalanuvchi valyutasida: '8 000 000 so'm' yoki '$800'."""
    formatted = num(value)
    if formatted == value:
        return value
    if currency == "USD":
        return f"-${formatted.lstrip('-')}" if str(formatted).startswith("-") else f"${formatted}"
    return f"{formatted} so'm"


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if hasattr(mapping, "get") else None


@register.filter
def pct(part, whole):
    try:
        return round(int(part) * 100 / int(whole)) if int(whole) else 0
    except (TypeError, ValueError):
        return 0
