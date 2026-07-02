"""Tabela declarativa de transições de estado da Requisicao, indexada por Operacao.

ADR-0011 (emenda 2026-06-26): a tabela responde só "operação permitida
**neste estado**?" — nunca autorização (isso é policy/papel, fatia separada).

TR-001 (N/A → rascunho) é criação e TR-003 (descarte de rascunho não enviado)
é DELETE — nenhum dos dois tem `Operacao` correspondente aqui porque nenhum
chama `verificar_transicao_valida` (sem estado de origem / sem transição de
estado).

Adicionar novas transições aqui somente quando o serviço correspondente for
implementado com policy, testes e timeline próprios.
"""

from dataclasses import dataclass

from apps.core.exceptions import EstadoInvalido
from apps.requisicoes.models import (
    CancelamentoVariant,
    EstadoRequisicao,
    EventoTimeline,
    Operacao,
    Requisicao,
)


@dataclass(frozen=True)
class TransicaoRequisicao:
    """Especificação de uma operação: de onde pode partir, para onde vai, o que registra."""

    operacao: Operacao
    estados_origem: frozenset[str]
    estado_destino: str
    eventos_timeline: frozenset[EventoTimeline]


TRANSICOES: dict[Operacao, TransicaoRequisicao] = {
    Operacao.EDITAR_RASCUNHO: TransicaoRequisicao(
        operacao=Operacao.EDITAR_RASCUNHO,
        estados_origem=frozenset({EstadoRequisicao.RASCUNHO}),
        estado_destino=EstadoRequisicao.RASCUNHO,
        eventos_timeline=frozenset(),
    ),
    Operacao.ENVIAR_PARA_AUTORIZACAO: TransicaoRequisicao(
        operacao=Operacao.ENVIAR_PARA_AUTORIZACAO,
        estados_origem=frozenset({EstadoRequisicao.RASCUNHO}),
        estado_destino=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        eventos_timeline=frozenset({EventoTimeline.ENVIO_AUTORIZACAO}),
    ),
    Operacao.RETORNAR_PARA_RASCUNHO: TransicaoRequisicao(
        operacao=Operacao.RETORNAR_PARA_RASCUNHO,
        estados_origem=frozenset({EstadoRequisicao.AGUARDANDO_AUTORIZACAO}),
        estado_destino=EstadoRequisicao.RASCUNHO,
        eventos_timeline=frozenset({EventoTimeline.RETORNO_RASCUNHO}),
    ),
    Operacao.RECUSAR: TransicaoRequisicao(
        operacao=Operacao.RECUSAR,
        estados_origem=frozenset({EstadoRequisicao.AGUARDANDO_AUTORIZACAO}),
        estado_destino=EstadoRequisicao.RECUSADA,
        eventos_timeline=frozenset({EventoTimeline.RECUSA}),
    ),
    Operacao.AUTORIZAR: TransicaoRequisicao(
        operacao=Operacao.AUTORIZAR,
        estados_origem=frozenset({EstadoRequisicao.AGUARDANDO_AUTORIZACAO}),
        estado_destino=EstadoRequisicao.AUTORIZADA,
        eventos_timeline=frozenset({EventoTimeline.AUTORIZACAO_TOTAL}),
    ),
    Operacao.CANCELAR: TransicaoRequisicao(
        operacao=Operacao.CANCELAR,
        estados_origem=frozenset(
            {
                EstadoRequisicao.RASCUNHO,
                EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
                EstadoRequisicao.AUTORIZADA,
                EstadoRequisicao.PRONTA_PARA_RETIRADA,
            }
        ),
        estado_destino=EstadoRequisicao.CANCELADA,
        eventos_timeline=frozenset({EventoTimeline.CANCELAMENTO}),
    ),
    Operacao.SEPARAR_PARA_RETIRADA: TransicaoRequisicao(
        operacao=Operacao.SEPARAR_PARA_RETIRADA,
        estados_origem=frozenset({EstadoRequisicao.AUTORIZADA}),
        estado_destino=EstadoRequisicao.PRONTA_PARA_RETIRADA,
        eventos_timeline=frozenset({EventoTimeline.SEPARACAO_RETIRADA}),
    ),
    Operacao.REGISTRAR_ATENDIMENTO: TransicaoRequisicao(
        operacao=Operacao.REGISTRAR_ATENDIMENTO,
        estados_origem=frozenset({EstadoRequisicao.PRONTA_PARA_RETIRADA}),
        estado_destino=EstadoRequisicao.ATENDIDA,
        eventos_timeline=frozenset(
            {
                EventoTimeline.ATENDIMENTO_TOTAL,
                EventoTimeline.ATENDIMENTO_PARCIAL,
                EventoTimeline.LIBERACAO_RESERVA,
            }
        ),
    ),
    Operacao.REGISTRAR_DEVOLUCAO: TransicaoRequisicao(
        operacao=Operacao.REGISTRAR_DEVOLUCAO,
        estados_origem=frozenset({EstadoRequisicao.ATENDIDA}),
        estado_destino=EstadoRequisicao.ATENDIDA,
        eventos_timeline=frozenset({EventoTimeline.DEVOLUCAO_REGISTRADA}),
    ),
    Operacao.ESTORNAR: TransicaoRequisicao(
        operacao=Operacao.ESTORNAR,
        estados_origem=frozenset({EstadoRequisicao.ATENDIDA}),
        estado_destino=EstadoRequisicao.ESTORNADA,
        eventos_timeline=frozenset({EventoTimeline.ESTORNO}),
    ),
}


def verificar_transicao_valida(
    operacao: Operacao, requisicao: Requisicao
) -> TransicaoRequisicao:
    """Lança EstadoInvalido se `operacao` não puder partir do estado atual."""
    transicao = TRANSICOES[operacao]
    if requisicao.estado not in transicao.estados_origem:
        raise EstadoInvalido(
            f"Transição '{operacao.label}' não é permitida no estado atual "
            f"('{requisicao.get_estado_display()}').",
            code='estado_origem_invalido',
        )
    return transicao


@dataclass(frozen=True)
class CancelamentoInfo:
    """Metadados de execução da capability Operacao.CANCELAR — zero strings de apresentação.

    `variante` só classifica o caso (CONTEXT.md, "Variante de cancelamento");
    quem decide os efeitos são as flags, nunca `if variante == X` em services
    ou templates (ADR-0011, emenda 2026-06-26).
    """

    variante: CancelamentoVariant
    requer_justificativa: bool
    libera_reserva: bool


def cancelamento_info(requisicao: Requisicao) -> CancelamentoInfo:
    """Classifica o cancelamento de `requisicao`, derivado do TransitionSpec de CANCELAR.

    Assume que o chamador já verificou `Operacao.CANCELAR in
    acoes_disponiveis(...)` — mesmo contrato de uso de
    `verificar_transicao_valida`. Descarte (TR-003) não tem `Operacao`
    correspondente em `TRANSICOES`, então é tratado como um caso adicional
    antes da checagem de `estados_origem`.
    """
    eh_descarte = (
        requisicao.estado == EstadoRequisicao.RASCUNHO
        and requisicao.numero_publico is None
    )
    if eh_descarte:
        return CancelamentoInfo(
            variante=CancelamentoVariant.DESCARTE,
            requer_justificativa=False,
            libera_reserva=False,
        )

    transicao = TRANSICOES[Operacao.CANCELAR]
    if requisicao.estado not in transicao.estados_origem:
        raise EstadoInvalido(
            'Cancelamento não é permitido no estado atual '
            f"('{requisicao.get_estado_display()}').",
            code='estado_origem_invalido',
        )

    pos_autorizacao = requisicao.estado in (
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    )
    return CancelamentoInfo(
        variante=CancelamentoVariant.CANCELAMENTO,
        requer_justificativa=pos_autorizacao,
        libera_reserva=pos_autorizacao,
    )
