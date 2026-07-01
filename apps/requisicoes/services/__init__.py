"""Services de domínio para requisições.

Único ponto de mutação de estado das requisições. Cada service:
- assinatura keyword-only com ator_id (nunca instância User)
- abre transaction.atomic para toda escrita de domínio
- chama exigir_pode_* antes de qualquer efeito
- registra eventos de TimelineRequisicao
- retorna a entidade principal alterada
- lança exceções de apps.core.exceptions, nunca exceções HTTP
"""

from apps.requisicoes.services.atendimento import (
    registrar_atendimento,
    registrar_devolucao,
    separar_para_retirada,
)
from apps.requisicoes.services.cancelamento import (
    cancelar_ou_descartar_requisicao,
    cancelar_requisicao,
    descartar_rascunho,
)
from apps.requisicoes.services.ciclo_vida import (
    ItemInput,
    autorizar_requisicao,
    criar_requisicao,
    editar_rascunho,
    enviar_para_autorizacao,
    estornar_requisicao,
    recusar_requisicao,
    retornar_para_rascunho,
)
from apps.requisicoes.services.composites import criar_e_enviar_requisicao
from apps.requisicoes.services.copia import copiar_requisicao

__all__ = [
    'ItemInput',
    'criar_e_enviar_requisicao',
    'criar_requisicao',
    'editar_rascunho',
    'enviar_para_autorizacao',
    'retornar_para_rascunho',
    'recusar_requisicao',
    'autorizar_requisicao',
    'estornar_requisicao',
    'descartar_rascunho',
    'cancelar_ou_descartar_requisicao',
    'cancelar_requisicao',
    'separar_para_retirada',
    'registrar_atendimento',
    'registrar_devolucao',
    'copiar_requisicao',
]
