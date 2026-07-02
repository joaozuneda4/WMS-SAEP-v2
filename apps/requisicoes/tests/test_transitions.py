"""Testes da tabela de transições indexada por Operacao (#53, ADR-0011 emenda)."""

import dataclasses

import pytest

from apps.core.exceptions import EstadoInvalido
from apps.requisicoes.models import (
    CancelamentoVariant,
    EstadoRequisicao,
    EventoTimeline,
    Operacao,
    Requisicao,
)
from apps.requisicoes.transitions import (
    TRANSICOES,
    cancelamento_info,
    verificar_transicao_valida,
)


def test_verificar_transicao_valida_retorna_especificacao_no_caminho_feliz():
    requisicao = Requisicao(estado=EstadoRequisicao.RASCUNHO)

    transicao = verificar_transicao_valida(Operacao.ENVIAR_PARA_AUTORIZACAO, requisicao)

    assert transicao.estado_destino == EstadoRequisicao.AGUARDANDO_AUTORIZACAO


def test_verificar_transicao_valida_estado_origem_invalido():
    requisicao = Requisicao(estado=EstadoRequisicao.AUTORIZADA)

    with pytest.raises(EstadoInvalido) as excinfo:
        verificar_transicao_valida(Operacao.ENVIAR_PARA_AUTORIZACAO, requisicao)

    assert excinfo.value.code == 'estado_origem_invalido'
    assert 'não é permitida' in str(excinfo.value)


@pytest.mark.parametrize(
    'estado_origem',
    [
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    ],
)
def test_cancelar_aceita_multiplos_estados_origem(estado_origem):
    requisicao = Requisicao(estado=estado_origem)

    transicao = verificar_transicao_valida(Operacao.CANCELAR, requisicao)

    assert transicao.estado_destino == EstadoRequisicao.CANCELADA


@pytest.mark.parametrize(
    'estado_origem',
    [
        EstadoRequisicao.RECUSADA,
        EstadoRequisicao.ATENDIDA,
        EstadoRequisicao.ESTORNADA,
    ],
)
def test_cancelar_rejeita_estados_fora_do_conjunto(estado_origem):
    requisicao = Requisicao(estado=estado_origem)

    with pytest.raises(EstadoInvalido) as excinfo:
        verificar_transicao_valida(Operacao.CANCELAR, requisicao)

    assert excinfo.value.code == 'estado_origem_invalido'


def test_transicoes_tem_uma_entrada_por_operacao():
    assert set(TRANSICOES.keys()) == set(Operacao)


@pytest.mark.parametrize('operacao', list(Operacao))
def test_estados_origem_e_sempre_frozenset(operacao):
    assert isinstance(TRANSICOES[operacao].estados_origem, frozenset)


@pytest.mark.parametrize('operacao', list(Operacao))
def test_eventos_timeline_e_sempre_frozenset(operacao):
    assert isinstance(TRANSICOES[operacao].eventos_timeline, frozenset)


def test_editar_rascunho_nao_declara_evento_de_timeline():
    assert TRANSICOES[Operacao.EDITAR_RASCUNHO].eventos_timeline == frozenset()


def test_registrar_atendimento_declara_os_tres_eventos_possiveis():
    assert TRANSICOES[Operacao.REGISTRAR_ATENDIMENTO].eventos_timeline == frozenset(
        {
            EventoTimeline.ATENDIMENTO_TOTAL,
            EventoTimeline.ATENDIMENTO_PARCIAL,
            EventoTimeline.LIBERACAO_RESERVA,
        }
    )


# ---------------------------------------------------------------------------
# cancelamento_info (#57, ADR-0011 emenda — CancelamentoInfo/CancelamentoVariant)
# ---------------------------------------------------------------------------


def test_cancelamento_info_rascunho_sem_numero_publico_e_descarte():
    requisicao = Requisicao(estado=EstadoRequisicao.RASCUNHO, numero_publico=None)

    info = cancelamento_info(requisicao)

    assert info.variante == CancelamentoVariant.DESCARTE
    assert info.requer_justificativa is False
    assert info.libera_reserva is False


def test_cancelamento_info_rascunho_com_numero_publico_e_cancelamento_sem_reserva():
    requisicao = Requisicao(
        estado=EstadoRequisicao.RASCUNHO, numero_publico='REQ-2026-000001'
    )

    info = cancelamento_info(requisicao)

    assert info.variante == CancelamentoVariant.CANCELAMENTO
    assert info.requer_justificativa is False
    assert info.libera_reserva is False


def test_cancelamento_info_aguardando_autorizacao_e_cancelamento_sem_reserva():
    requisicao = Requisicao(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000001',
    )

    info = cancelamento_info(requisicao)

    assert info.variante == CancelamentoVariant.CANCELAMENTO
    assert info.requer_justificativa is False
    assert info.libera_reserva is False


@pytest.mark.parametrize(
    'estado_origem',
    [EstadoRequisicao.AUTORIZADA, EstadoRequisicao.PRONTA_PARA_RETIRADA],
)
def test_cancelamento_info_pos_autorizacao_exige_justificativa_e_libera_reserva(
    estado_origem,
):
    requisicao = Requisicao(estado=estado_origem, numero_publico='REQ-2026-000001')

    info = cancelamento_info(requisicao)

    assert info.variante == CancelamentoVariant.CANCELAMENTO
    assert info.requer_justificativa is True
    assert info.libera_reserva is True


@pytest.mark.parametrize(
    'estado_origem',
    [
        EstadoRequisicao.RECUSADA,
        EstadoRequisicao.ATENDIDA,
        EstadoRequisicao.ESTORNADA,
    ],
)
def test_cancelamento_info_rejeita_estados_fora_do_conjunto_de_cancelar(
    estado_origem,
):
    requisicao = Requisicao(estado=estado_origem, numero_publico='REQ-2026-000001')

    with pytest.raises(EstadoInvalido) as excinfo:
        cancelamento_info(requisicao)

    assert excinfo.value.code == 'estado_origem_invalido'


def test_cancelamento_info_e_imutavel():
    requisicao = Requisicao(estado=EstadoRequisicao.RASCUNHO, numero_publico=None)

    info = cancelamento_info(requisicao)

    with pytest.raises(dataclasses.FrozenInstanceError):
        info.requer_justificativa = True
