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
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,  # TR-005: enviar para autorização
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
