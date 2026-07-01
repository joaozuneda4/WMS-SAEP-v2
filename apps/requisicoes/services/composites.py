"""Services compostos de requisições (ADR-0004, emenda 2026-06-26).

Um composto orquestra 2+ atômicos existentes e é dono da fronteira
transacional de nível mais alto quando as transições precisam ser
all-or-nothing. Padrão: View → Composto → Atômicos → Domínio.
"""

from django.db import transaction

from apps.requisicoes.models import Requisicao
from apps.requisicoes.services.ciclo_vida import (
    ItemInput,
    criar_requisicao,
    enviar_para_autorizacao,
)


def criar_e_enviar_requisicao(
    *,
    ator_id: int,
    beneficiario_id: int,
    itens: list[ItemInput],
    observacao_geral: str = '',
) -> Requisicao:
    """Cria uma requisição e a envia para autorização em uma única transação.

    Orquestra `criar_requisicao` + `enviar_para_autorizacao` sem duplicar suas
    regras. Se qualquer um dos dois falhar, nada é persistido.
    """
    with transaction.atomic():
        requisicao = criar_requisicao(
            ator_id=ator_id,
            beneficiario_id=beneficiario_id,
            itens=itens,
            observacao_geral=observacao_geral,
        )
        return enviar_para_autorizacao(
            ator_id=ator_id,
            requisicao_id=requisicao.pk,
        )
