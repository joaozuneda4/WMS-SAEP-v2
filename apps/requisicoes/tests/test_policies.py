"""Testes de autorização contextual para requisições (ADR-0010).

Chamada direta às funções de policy — sem view, sem form.
"""

import pytest

from apps.accounts.models import VinculoAuxiliar
from apps.core.exceptions import PermissaoNegada
from apps.requisicoes.models import EstadoRequisicao, Requisicao
from apps.requisicoes.policies import (
    pode_criar_para_beneficiario,
    pode_editar_rascunho,
    pode_ser_beneficiario,
    resolver_escopo_criacao_requisicao,
)


# ---------------------------------------------------------------------------
# pode_ser_beneficiario
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pode_ser_beneficiario_ativo_com_setor(solicitante):
    assert pode_ser_beneficiario(solicitante) is True


@pytest.mark.django_db
def test_pode_ser_beneficiario_inativo(usuario_inativo):
    assert pode_ser_beneficiario(usuario_inativo) is False


@pytest.mark.django_db
def test_pode_ser_beneficiario_sem_setor(usuario_sem_setor):
    assert pode_ser_beneficiario(usuario_sem_setor) is False


# ---------------------------------------------------------------------------
# resolver_escopo_criacao_requisicao — modo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_escopo_solicitante_puro(solicitante):
    escopo = resolver_escopo_criacao_requisicao(solicitante)
    assert escopo.modo_beneficiario == 'proprio'
    assert escopo.pode_criar_para_si is True
    assert escopo.setores_escopo_ids == []


@pytest.mark.django_db
def test_escopo_ator_sem_setor_levanta_permissao_negada(usuario_sem_setor):
    with pytest.raises(PermissaoNegada):
        resolver_escopo_criacao_requisicao(usuario_sem_setor)


@pytest.mark.django_db
def test_escopo_chefe_setor_nao_almox(chefe_obras, setor_obras):
    escopo = resolver_escopo_criacao_requisicao(chefe_obras)
    assert escopo.modo_beneficiario == 'setor'
    assert setor_obras.pk in escopo.setores_escopo_ids
    assert escopo.pode_criar_para_si is True


@pytest.mark.django_db
def test_escopo_aux_setor_nao_almox(aux_obras, setor_obras):
    escopo = resolver_escopo_criacao_requisicao(aux_obras)
    assert escopo.modo_beneficiario == 'setor'
    assert setor_obras.pk in escopo.setores_escopo_ids


@pytest.mark.django_db
def test_escopo_aux_almoxarifado(aux_almoxarifado):
    escopo = resolver_escopo_criacao_requisicao(aux_almoxarifado)
    assert escopo.modo_beneficiario == 'qualquer'


@pytest.mark.django_db
def test_escopo_chefe_almoxarifado(chefe_almoxarifado):
    escopo = resolver_escopo_criacao_requisicao(chefe_almoxarifado)
    assert escopo.modo_beneficiario == 'qualquer'


@pytest.mark.django_db
def test_escopo_precedencia_chefe_setor_mais_aux_almox(
    db, setor_obras, setor_almoxarifado
):
    """Usuário com papel de chefe em setor comum E auxiliar de almox → modo=qualquer."""
    u = __import__('apps.accounts.models', fromlist=['User']).User.objects.create_user(
        matricula='DUP01', nome='Duplo Papel', password='senha', setor=setor_obras
    )
    setor_obras.chefe = u
    setor_obras.save(update_fields=['chefe'])
    VinculoAuxiliar.objects.create(usuario=u, setor=setor_almoxarifado, ativo=True)

    escopo = resolver_escopo_criacao_requisicao(u)
    assert escopo.modo_beneficiario == 'qualquer'


@pytest.mark.django_db
def test_escopo_ator_com_papel_funcional_sem_setor_pode_criar_para_si_false(
    db, setor_almoxarifado
):
    """Ator com vínculo de almox mas setor=None → pode_criar_para_si=False."""
    u = __import__('apps.accounts.models', fromlist=['User']).User.objects.create_user(
        matricula='NST01', nome='Sem Setor Almox', password='senha', setor=None
    )
    VinculoAuxiliar.objects.create(usuario=u, setor=setor_almoxarifado, ativo=True)

    escopo = resolver_escopo_criacao_requisicao(u)
    assert escopo.modo_beneficiario == 'qualquer'
    assert escopo.pode_criar_para_si is False


# ---------------------------------------------------------------------------
# Queryset de beneficiários por modo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_escopo_setor_exclui_proprio_ator(
    chefe_obras, setor_obras, outro_usuario_obras
):
    escopo = resolver_escopo_criacao_requisicao(chefe_obras)
    ids = set(escopo.beneficiarios.values_list('pk', flat=True))
    assert chefe_obras.pk not in ids
    assert outro_usuario_obras.pk in ids


@pytest.mark.django_db
def test_escopo_setor_exclui_usuarios_de_outro_setor(chefe_obras, usuario_ti):
    escopo = resolver_escopo_criacao_requisicao(chefe_obras)
    ids = set(escopo.beneficiarios.values_list('pk', flat=True))
    assert usuario_ti.pk not in ids


@pytest.mark.django_db
def test_escopo_qualquer_exclui_proprio_ator(aux_almoxarifado, solicitante):
    escopo = resolver_escopo_criacao_requisicao(aux_almoxarifado)
    ids = set(escopo.beneficiarios.values_list('pk', flat=True))
    assert aux_almoxarifado.pk not in ids
    assert solicitante.pk in ids


# ---------------------------------------------------------------------------
# pode_criar_para_beneficiario
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pode_criar_para_si(solicitante):
    assert pode_criar_para_beneficiario(solicitante, solicitante) is True


@pytest.mark.django_db
def test_solicitante_nao_pode_criar_para_terceiro(solicitante, outro_usuario_obras):
    assert pode_criar_para_beneficiario(solicitante, outro_usuario_obras) is False


@pytest.mark.django_db
def test_chefe_setor_pode_criar_para_membro_do_setor(chefe_obras, outro_usuario_obras):
    assert pode_criar_para_beneficiario(chefe_obras, outro_usuario_obras) is True


@pytest.mark.django_db
def test_chefe_setor_nao_pode_criar_para_outro_setor(chefe_obras, usuario_ti):
    assert pode_criar_para_beneficiario(chefe_obras, usuario_ti) is False


@pytest.mark.django_db
def test_aux_almox_pode_criar_para_qualquer_setor(aux_almoxarifado, usuario_ti):
    assert pode_criar_para_beneficiario(aux_almoxarifado, usuario_ti) is True


@pytest.mark.django_db
def test_nao_pode_criar_para_beneficiario_inativo(solicitante, usuario_inativo):
    assert pode_criar_para_beneficiario(solicitante, usuario_inativo) is False


@pytest.mark.django_db
def test_nao_pode_criar_para_beneficiario_sem_setor(
    aux_almoxarifado, usuario_sem_setor
):
    assert pode_criar_para_beneficiario(aux_almoxarifado, usuario_sem_setor) is False


# ---------------------------------------------------------------------------
# pode_editar_rascunho
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criador_pode_editar_rascunho(solicitante, setor_obras, material_disponivel):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_editar_rascunho(solicitante, req) is True


@pytest.mark.django_db
def test_nao_criador_nao_pode_editar(solicitante, outro_usuario_obras, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_editar_rascunho(outro_usuario_obras, req) is False


@pytest.mark.django_db
def test_criador_retorna_true_independente_do_estado(solicitante, setor_obras):
    """pode_editar_rascunho verifica apenas criador; estado é validado pelo service."""
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000001',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_editar_rascunho(solicitante, req) is True


# ---------------------------------------------------------------------------
# pode_enviar_rascunho
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criador_pode_enviar_rascunho(solicitante, setor_obras):
    from apps.requisicoes.policies import pode_enviar_rascunho

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_enviar_rascunho(solicitante, req) is True


@pytest.mark.django_db
def test_nao_criador_nao_pode_enviar(solicitante, outro_usuario_obras, setor_obras):
    from apps.requisicoes.policies import pode_enviar_rascunho

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_enviar_rascunho(outro_usuario_obras, req) is False


@pytest.mark.django_db
def test_criador_inativo_nao_pode_enviar(solicitante, setor_obras):
    from apps.requisicoes.policies import pode_enviar_rascunho

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    solicitante.is_active = False
    solicitante.save(update_fields=['is_active'])
    assert pode_enviar_rascunho(solicitante, req) is False
