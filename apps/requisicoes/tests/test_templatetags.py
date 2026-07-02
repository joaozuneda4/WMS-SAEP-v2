"""Testes unitários dos template tags/filters de requisicoes."""

from decimal import Decimal

import pytest

from apps.requisicoes.models import CancelamentoVariant, EstadoRequisicao
from apps.requisicoes.templatetags.requisicoes_tags import (
    cancelamento_copy,
    formatar_quantidade,
    get_choice_label,
)
from apps.requisicoes.transitions import CancelamentoInfo


# ---------------------------------------------------------------------------
# Helpers para testar get_choice_label sem instanciar Form completo
# ---------------------------------------------------------------------------


class _FakeInnerField:
    def __init__(self, choices):
        self.choices = choices


class _FakeField:
    """Simula um BoundField com atributo .field.choices."""

    def __init__(self, choices):
        self.field = _FakeInnerField(choices)


_CHOICES = [('a', 'Label A'), ('b', 'Label B'), (1, 'Um')]


@pytest.mark.parametrize(
    'value, esperado',
    [
        # Match por string
        ('a', 'Label A'),
        ('b', 'Label B'),
        # Match com chave inteira (conversão str)
        ('1', 'Um'),
        # Valor ausente → string vazia
        ('z', ''),
        # Valor vazio → string vazia (guard)
        ('', ''),
        # None → string vazia (guard)
        (None, ''),
    ],
)
def test_get_choice_label(value, esperado):
    field = _FakeField(_CHOICES)
    assert get_choice_label(field, value) == esperado


@pytest.mark.parametrize(
    'qtd, unidade, esperado',
    [
        # Unidade → inteiro
        (Decimal('5.000'), 'un', '5'),
        (Decimal('1.000'), 'un', '1'),
        (Decimal('100.000'), 'un', '100'),
        # kg → 1 decimal
        (Decimal('2.500'), 'kg', '2.5'),
        (Decimal('10.000'), 'kg', '10.0'),
        (Decimal('0.100'), 'kg', '0.1'),
        # l → 1 decimal
        (Decimal('3.000'), 'l', '3.0'),
        (Decimal('1.500'), 'l', '1.5'),
        # m → 1 decimal
        (Decimal('4.200'), 'm', '4.2'),
        (Decimal('10.000'), 'm', '10.0'),
        # m2 → strip trailing zeros (casas significativas)
        (Decimal('2.000'), 'm2', '2'),
        (Decimal('1.500'), 'm2', '1.5'),
        (Decimal('1.230'), 'm2', '1.23'),
        # cx, pct, par, rolo → strip trailing zeros
        (Decimal('3.000'), 'cx', '3'),
        (Decimal('2.500'), 'pct', '2.5'),
        (Decimal('1.000'), 'par', '1'),
        (Decimal('6.000'), 'rolo', '6'),
        # None → fallback
        (None, 'un', '—'),
        (None, 'kg', '—'),
    ],
)
def test_formatar_quantidade(qtd, unidade, esperado):
    assert formatar_quantidade(qtd, unidade) == esperado


# ---------------------------------------------------------------------------
# cancelamento_copy (#57) — lookup de copy do modal por (variante, estado)
# ---------------------------------------------------------------------------


def test_cancelamento_copy_descarte():
    info = CancelamentoInfo(
        variante=CancelamentoVariant.DESCARTE,
        requer_justificativa=False,
        libera_reserva=False,
    )

    copy = cancelamento_copy(info, EstadoRequisicao.RASCUNHO)

    assert copy['titulo'] == 'Descartar rascunho'
    assert copy['trigger'] == 'Descartar rascunho'
    assert copy['confirmar'] == 'Descartar'
    assert 'não consome número público' in copy['descricao']


def test_cancelamento_copy_cancelamento_rascunho_numerado():
    info = CancelamentoInfo(
        variante=CancelamentoVariant.CANCELAMENTO,
        requer_justificativa=False,
        libera_reserva=False,
    )

    copy = cancelamento_copy(info, EstadoRequisicao.RASCUNHO)

    assert copy['titulo'] == 'Cancelar rascunho'
    assert copy['trigger'] == 'Cancelar rascunho'
    assert copy['confirmar'] == 'Confirmar cancelamento'
    assert 'preserva o número público' in copy['descricao']


def test_cancelamento_copy_cancelamento_aguardando_autorizacao():
    info = CancelamentoInfo(
        variante=CancelamentoVariant.CANCELAMENTO,
        requer_justificativa=False,
        libera_reserva=False,
    )

    copy = cancelamento_copy(info, EstadoRequisicao.AGUARDANDO_AUTORIZACAO)

    assert copy['titulo'] == 'Cancelar requisição'
    assert copy['trigger'] == 'Cancelar requisição'
    assert copy['confirmar'] == 'Confirmar cancelamento'
    assert 'justificativa é opcional' in copy['descricao']


@pytest.mark.parametrize(
    'estado',
    [EstadoRequisicao.AUTORIZADA, EstadoRequisicao.PRONTA_PARA_RETIRADA],
)
def test_cancelamento_copy_cancelamento_pos_autorizacao(estado):
    info = CancelamentoInfo(
        variante=CancelamentoVariant.CANCELAMENTO,
        requer_justificativa=True,
        libera_reserva=True,
    )

    copy = cancelamento_copy(info, estado)

    assert copy['titulo'] == 'Cancelar requisição'
    assert copy['trigger'] == 'Cancelar requisição'
    assert copy['confirmar'] == 'Confirmar cancelamento'
    assert 'reservas voltam ao saldo disponível' in copy['descricao']


def test_cancelamento_copy_none_retorna_dict_vazio():
    assert cancelamento_copy(None, EstadoRequisicao.RASCUNHO) == {}
