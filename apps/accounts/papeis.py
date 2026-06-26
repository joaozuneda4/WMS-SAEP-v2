"""Papel efetivo de um usuário — value object puro e resolver de IO."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist

from apps.accounts.models import SetorClassificacao, User, VinculoAuxiliar


@dataclass(frozen=True)
class PapelEfetivo:
    """Snapshot do papel efetivo de um usuário; dado puro, sem referência viva de ORM."""

    eh_almoxarifado: bool
    eh_chefe_de_almoxarifado: bool
    setores_em_escopo: tuple[int, ...]
    setor_chefiado_ativo_id: int | None
    pode_ser_beneficiario: bool


def papel_efetivo(usuario: User) -> PapelEfetivo:
    """Único boundary de IO para derivação de papel efetivo."""
    if not usuario.is_active:
        return PapelEfetivo(
            eh_almoxarifado=False,
            eh_chefe_de_almoxarifado=False,
            setores_em_escopo=(),
            setor_chefiado_ativo_id=None,
            pode_ser_beneficiario=False,
        )
    setor_chefiado = None
    try:
        setor_chefiado = usuario.setor_chefiado
    except (AttributeError, ObjectDoesNotExist):
        pass

    setor_ativo = (
        setor_chefiado
        if (setor_chefiado is not None and setor_chefiado.ativo)
        else None
    )
    setor_chefiado_ativo_id = setor_ativo.pk if setor_ativo is not None else None
    eh_chefe_de_almoxarifado = (
        setor_ativo is not None
        and setor_ativo.classificacao == SetorClassificacao.ALMOXARIFADO
    )

    vinculos = list(
        VinculoAuxiliar.objects.filter(
            usuario=usuario, ativo=True, setor__ativo=True
        ).values('setor_id', 'setor__classificacao')
    )

    eh_auxiliar_de_almoxarifado = any(
        v['setor__classificacao'] == SetorClassificacao.ALMOXARIFADO for v in vinculos
    )
    setores_nao_almox: set[int] = {
        v['setor_id']
        for v in vinculos
        if v['setor__classificacao'] != SetorClassificacao.ALMOXARIFADO
    }
    if setor_chefiado_ativo_id is not None and not eh_chefe_de_almoxarifado:
        setores_nao_almox.add(setor_chefiado_ativo_id)

    return PapelEfetivo(
        eh_almoxarifado=eh_chefe_de_almoxarifado or eh_auxiliar_de_almoxarifado,
        eh_chefe_de_almoxarifado=eh_chefe_de_almoxarifado,
        setores_em_escopo=tuple(setores_nao_almox),
        setor_chefiado_ativo_id=setor_chefiado_ativo_id,
        pode_ser_beneficiario=bool(usuario.is_active and usuario.setor_id is not None),
    )
