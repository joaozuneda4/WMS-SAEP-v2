from django.core.exceptions import ObjectDoesNotExist

from apps.accounts.models import SetorClassificacao, User
from apps.accounts.papeis import papel_efetivo
from apps.core.exceptions import PermissaoNegada


def _eh_almoxarifado(usuario: User) -> bool:
    return papel_efetivo(usuario).eh_almoxarifado


def pode_consultar_saidas_excepcionais(ator: User) -> bool:
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    return _eh_almoxarifado(ator)


def exigir_pode_consultar_saidas_excepcionais(ator: User) -> None:
    if not pode_consultar_saidas_excepcionais(ator):
        raise PermissaoNegada('Apenas almoxarifado pode consultar saídas excepcionais.')


def pode_registrar_saida_excepcional(ator: User) -> bool:
    """Apenas chefe de almoxarifado e superuser podem registrar."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    try:
        setor_chefiado = ator.setor_chefiado
        if (
            setor_chefiado.classificacao == SetorClassificacao.ALMOXARIFADO
            and setor_chefiado.ativo
        ):
            return True
    except (AttributeError, ObjectDoesNotExist):
        pass
    return False


def exigir_pode_registrar_saida_excepcional(ator: User) -> None:
    if not pode_registrar_saida_excepcional(ator):
        raise PermissaoNegada(
            'Apenas chefe de almoxarifado pode registrar saídas excepcionais.'
        )


def pode_estornar_saida_excepcional(ator: User) -> bool:
    """Apenas chefe de almoxarifado e superuser podem estornar."""
    return pode_registrar_saida_excepcional(ator)


def exigir_pode_estornar_saida_excepcional(ator: User) -> None:
    if not pode_estornar_saida_excepcional(ator):
        raise PermissaoNegada(
            'Apenas chefe de almoxarifado pode estornar saídas excepcionais.'
        )


def pode_visualizar_preview_scpi(ator: 'User') -> bool:
    if not ator.is_active:
        return False
    return ator.is_superuser


def exigir_pode_visualizar_preview_scpi(ator: 'User') -> None:
    if not pode_visualizar_preview_scpi(ator):
        from apps.core.exceptions import PermissaoNegada

        raise PermissaoNegada(
            'Apenas superusuários podem visualizar pré-visualizações de importação SCPI.',
            code='permissao_negada',
        )


def pode_confirmar_importacao_scpi(ator: 'User') -> bool:
    return ator.is_active and ator.is_superuser


def exigir_pode_confirmar_importacao_scpi(ator: 'User') -> None:
    if not pode_confirmar_importacao_scpi(ator):
        from apps.core.exceptions import PermissaoNegada

        raise PermissaoNegada(
            'Apenas superusuários podem confirmar importações SCPI.',
            code='permissao_negada',
        )


def pode_consultar_historico_scpi(ator: 'User') -> bool:
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    try:
        setor = ator.setor_chefiado
        return setor.classificacao == SetorClassificacao.ALMOXARIFADO and setor.ativo
    except (AttributeError, ObjectDoesNotExist):
        return False


def exigir_pode_consultar_historico_scpi(ator: 'User') -> None:
    if not pode_consultar_historico_scpi(ator):
        from apps.core.exceptions import PermissaoNegada

        raise PermissaoNegada(
            'Apenas superusuários e chefes de almoxarifado podem consultar o histórico de importações SCPI.',
            code='permissao_negada',
        )


def pode_consultar_catalogo_estoque(usuario: 'User') -> bool:
    return usuario.is_active


def exigir_pode_consultar_catalogo_estoque(usuario: 'User') -> None:
    if not pode_consultar_catalogo_estoque(usuario):
        from apps.core.exceptions import PermissaoNegada

        raise PermissaoNegada(
            'Apenas usuários ativos podem consultar o catálogo de estoque.',
            code='permissao_negada',
        )


def pode_gerir_catalogo(ator: 'User') -> bool:
    """Superusuário pode gerir (ativar/desativar) materiais do catálogo."""
    return bool(ator.is_active and ator.is_superuser)


def exigir_pode_gerir_catalogo(ator: 'User') -> None:
    from apps.core.exceptions import PermissaoNegada

    if not pode_gerir_catalogo(ator):
        raise PermissaoNegada(
            'Apenas superusuários podem gerir o catálogo de materiais.'
        )


def _eh_chefe_ou_aux_setor_nao_almox(ator: 'User') -> bool:
    return bool(papel_efetivo(ator).setores_em_escopo)


def pode_consultar_movimentacoes_estoque(ator: 'User') -> bool:
    """Pode navegar o ledger de movimentações = tem visibilidade por papel.

    Espelha o universo de ``movimentacoes_visiveis_para``: superuser, almoxarifado
    (chefe/aux) ou chefe/aux de setor não-almox. Solicitante puro e inativo: não.
    """
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    papel = papel_efetivo(ator)
    return papel.eh_almoxarifado or bool(papel.setores_em_escopo)


def exigir_pode_consultar_movimentacoes_estoque(ator: 'User') -> None:
    if not pode_consultar_movimentacoes_estoque(ator):
        raise PermissaoNegada(
            'Você não tem permissão para consultar movimentações de estoque.',
            code='permissao_negada',
        )
