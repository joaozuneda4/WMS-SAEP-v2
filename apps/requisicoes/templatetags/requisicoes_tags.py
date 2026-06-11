from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

_UMA_DECIMAL = ('kg', 'l', 'm')


@register.filter
def get_choice_label(field, value):
    """Retorna o label de uma choice pelo value (para restaurar autocomplete)."""
    if not value:
        return ''
    str_value = str(value)
    for opt_value, opt_label in field.field.choices:
        if str(opt_value) == str_value:
            return opt_label
    return ''


@register.filter
def formatar_quantidade(qtd, unidade: str) -> str:
    """Formata quantidade conforme a unidade de medida do material.

    - 'un' → inteiro
    - 'kg', 'l', 'm' → 1 casa decimal
    - demais → strip trailing zeros (casas significativas)
    """
    if qtd is None:
        return '—'
    try:
        d = Decimal(str(qtd))
    except (InvalidOperation, TypeError, ValueError):
        return str(qtd)

    if unidade == 'un':
        return str(int(d))

    if unidade in _UMA_DECIMAL:
        return format(d.quantize(Decimal('0.1')), 'f')

    normalized = d.normalize()
    if normalized == normalized.to_integral_value():
        return str(int(normalized))
    return format(normalized, 'f')


@register.filter
def get_item(dictionary, key):
    """Retorna dictionary[key]; compatível com chaves string e int."""
    if not isinstance(dictionary, dict):
        return None
    return dictionary.get(str(key))
