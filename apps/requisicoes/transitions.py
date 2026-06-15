"""Tabela declarativa de transições de estado da Requisicao.

TR-001 (N/A → rascunho) é criação — não chama verificar_transicao_valida porque
não há estado de origem. As demais transições passam por esta função antes de
qualquer efeito de domínio.

Adicionar novas transições aqui somente quando o service correspondente for
implementado com policy, testes e timeline próprios.
"""

from apps.core.exceptions import EstadoInvalido
from apps.requisicoes.models import EstadoRequisicao

# Transições declaradas: estado_origem → conjunto de estados_destino permitidos.
# Atualizar incrementalmente conforme cada TR-* for implementada.
TRANSICOES_VALIDAS: dict[str, set[str]] = {
    EstadoRequisicao.RASCUNHO: {
        EstadoRequisicao.RASCUNHO,  # TR-002: editar rascunho
        EstadoRequisicao.CANCELADA,  # TR-004: cancelar rascunho numerado
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,  # TR-005: enviar para autorização
    },
    EstadoRequisicao.AGUARDANDO_AUTORIZACAO: {
        EstadoRequisicao.RASCUNHO,  # TR-006: retornar para rascunho
        EstadoRequisicao.CANCELADA,  # TR-012: cancelar antes da autorização
        EstadoRequisicao.AUTORIZADA,  # TR-008: autorizar integralmente
        EstadoRequisicao.RECUSADA,  # TR-011: recusar inteira
    },
    EstadoRequisicao.AUTORIZADA: {
        EstadoRequisicao.CANCELADA,  # TR-013: cancelar autorizada
        EstadoRequisicao.PRONTA_PARA_RETIRADA,  # TR-015: separar para retirada
    },
    EstadoRequisicao.PRONTA_PARA_RETIRADA: {
        EstadoRequisicao.CANCELADA,  # TR-014: cancelar pronta para retirada
        EstadoRequisicao.ATENDIDA,  # TR-016/TR-017: registrar atendimento total/parcial
    },
    EstadoRequisicao.ATENDIDA: {
        EstadoRequisicao.ATENDIDA,  # TR-020: registrar devolução
    },
}


def verificar_transicao_valida(de: str, para: str) -> None:
    """Lança EstadoInvalido se a transição de→para não estiver declarada."""
    destinos_permitidos = TRANSICOES_VALIDAS.get(de, set())
    if para not in destinos_permitidos:
        raise EstadoInvalido(
            f"Transição de '{de}' para '{para}' não é permitida.",
            code='transicao_invalida',
        )
