from django.core.exceptions import ObjectDoesNotExist

from apps.accounts.models import SetorClassificacao, User, VinculoAuxiliar
from apps.core.exceptions import PermissaoNegada


def _eh_almoxarifado(usuario: User) -> bool:
    try:
        setor_chefiado = usuario.setor_chefiado
        if (
            setor_chefiado.classificacao == SetorClassificacao.ALMOXARIFADO
            and setor_chefiado.ativo
        ):
            return True
    except (AttributeError, ObjectDoesNotExist):
        pass
    return VinculoAuxiliar.objects.filter(
        usuario=usuario,
        ativo=True,
        setor__classificacao=SetorClassificacao.ALMOXARIFADO,
        setor__ativo=True,
    ).exists()


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
