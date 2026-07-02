from decimal import Decimal, InvalidOperation

from django import template

from apps.requisicoes.models import CancelamentoVariant, EstadoRequisicao

register = template.Library()

_UMA_DECIMAL = ('kg', 'l', 'm')

_CANCELAMENTO_COPY = {
    (CancelamentoVariant.DESCARTE, EstadoRequisicao.RASCUNHO): {
        'titulo': 'Descartar rascunho',
        'descricao': (
            'Este rascunho ainda não foi enviado. O descarte remove o registro '
            'definitivamente e não consome número público nem reserva de estoque.'
        ),
        'trigger': 'Descartar rascunho',
        'confirmar': 'Descartar',
    },
    (CancelamentoVariant.CANCELAMENTO, EstadoRequisicao.RASCUNHO): {
        'titulo': 'Cancelar rascunho',
        'descricao': (
            'Este rascunho já foi enviado alguma vez. O cancelamento encerra '
            'a requisição sem nova reserva e preserva o número público.'
        ),
        'trigger': 'Cancelar rascunho',
        'confirmar': 'Confirmar cancelamento',
    },
    (CancelamentoVariant.CANCELAMENTO, EstadoRequisicao.AGUARDANDO_AUTORIZACAO): {
        'titulo': 'Cancelar requisição',
        'descricao': (
            'A requisição será encerrada antes da autorização. Não há reserva '
            'de estoque a liberar e a justificativa é opcional.'
        ),
        'trigger': 'Cancelar requisição',
        'confirmar': 'Confirmar cancelamento',
    },
    (CancelamentoVariant.CANCELAMENTO, EstadoRequisicao.AUTORIZADA): {
        'titulo': 'Cancelar requisição',
        'descricao': (
            'A requisição será encerrada e as reservas voltam ao saldo '
            'disponível. O saldo físico permanece inalterado.'
        ),
        'trigger': 'Cancelar requisição',
        'confirmar': 'Confirmar cancelamento',
    },
}
_CANCELAMENTO_COPY[
    (CancelamentoVariant.CANCELAMENTO, EstadoRequisicao.PRONTA_PARA_RETIRADA)
] = _CANCELAMENTO_COPY[(CancelamentoVariant.CANCELAMENTO, EstadoRequisicao.AUTORIZADA)]


@register.simple_tag
def cancelamento_copy(info, estado):
    """Lookup de copy do modal de cancelamento por (variante, estado) — presentation-only.

    `info` é `CancelamentoInfo | None`; `estado` é `requisicao.estado`. Não
    reimplementa regra de domínio — só projeta a classificação já feita por
    `apps.requisicoes.transitions.cancelamento_info` em texto de UI.
    """
    if info is None:
        return {}
    return _CANCELAMENTO_COPY[(info.variante, estado)]


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
