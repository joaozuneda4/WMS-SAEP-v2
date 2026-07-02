"""Context processors do app de requisições.

Expõem flags de capacidade do usuário autenticado para uso no chrome
compartilhado (topbar), evitando duplicação de policy em templates.
"""

from apps.accounts.papeis import papel_efetivo
from apps.estoque.policies import (
    pode_consultar_catalogo_estoque,
    pode_consultar_historico_scpi,
    pode_consultar_movimentacoes_estoque,
    pode_consultar_saidas_excepcionais,
    pode_visualizar_preview_scpi,
)
from apps.requisicoes.policies import (
    pode_consultar_historico_requisicoes,
    pode_ver_fila_atendimento,
    pode_ver_fila_autorizacao,
)


def flags_de_papel(request):
    """Adiciona flags de capacidade ao contexto para o chrome global."""
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {
            'pode_ver_fila_autorizacao': False,
            'pode_ver_fila_atendimento': False,
            'pode_consultar_saidas_excepcionais': False,
            'pode_visualizar_preview_scpi': False,
            'pode_consultar_historico_scpi': False,
            'pode_consultar_catalogo_estoque': False,
            'pode_consultar_movimentacoes_estoque': False,
            'pode_consultar_historico_requisicoes': False,
        }
    papel = papel_efetivo(usuario)
    return {
        'pode_ver_fila_autorizacao': pode_ver_fila_autorizacao(papel),
        'pode_ver_fila_atendimento': pode_ver_fila_atendimento(papel),
        'pode_consultar_saidas_excepcionais': pode_consultar_saidas_excepcionais(papel),
        'pode_visualizar_preview_scpi': pode_visualizar_preview_scpi(papel),
        'pode_consultar_historico_scpi': pode_consultar_historico_scpi(papel),
        'pode_consultar_catalogo_estoque': pode_consultar_catalogo_estoque(papel),
        'pode_consultar_movimentacoes_estoque': pode_consultar_movimentacoes_estoque(
            papel
        ),
        'pode_consultar_historico_requisicoes': pode_consultar_historico_requisicoes(
            papel
        ),
    }
