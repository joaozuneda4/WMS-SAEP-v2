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
    pode_autorizar_requisicao,
    pode_recusar_requisicao,
    pode_retornar_para_rascunho,
    pode_atender_retirada,
    pode_separar_para_retirada,
    pode_ser_beneficiario,
    pode_ver_fila_atendimento,
    pode_ver_fila_autorizacao,
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


# ---------------------------------------------------------------------------
# Fila de autorização, retorno e recusa
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chefe_setor_pode_ver_fila_autorizacao(chefe_obras):
    assert pode_ver_fila_autorizacao(chefe_obras) is True


@pytest.mark.django_db
def test_auxiliar_almox_nao_pode_ver_fila_autorizacao(aux_almoxarifado):
    assert pode_ver_fila_autorizacao(aux_almoxarifado) is False


@pytest.mark.django_db
def test_criador_pode_retornar_para_rascunho(solicitante, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000101',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_retornar_para_rascunho(solicitante, req) is True


@pytest.mark.django_db
def test_terceiro_nao_pode_retornar_para_rascunho(
    outro_usuario_obras, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000102',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_retornar_para_rascunho(outro_usuario_obras, req) is False


@pytest.mark.django_db
def test_chefe_setor_pode_recusar_requisicao_do_setor(
    chefe_obras, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000103',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_recusar_requisicao(chefe_obras, req) is True


@pytest.mark.django_db
def test_chefe_setor_pode_autorizar_requisicao_do_setor(
    chefe_obras, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000105',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_autorizar_requisicao(chefe_obras, req) is True


@pytest.mark.django_db
def test_chefe_setor_nao_pode_autorizar_requisicao_de_outro_setor(
    chefe_obras, solicitante, setor_ti
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000106',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_ti,
    )
    assert pode_autorizar_requisicao(chefe_obras, req) is False


@pytest.mark.django_db
def test_chefe_almox_nao_pode_autorizar_requisicao_de_outro_setor(
    chefe_almoxarifado, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000107',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_autorizar_requisicao(chefe_almoxarifado, req) is False


@pytest.mark.django_db
def test_chefe_almox_nao_recusa_requisicao_de_outro_setor(
    chefe_almoxarifado, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000104',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    assert pode_recusar_requisicao(chefe_almoxarifado, req) is False


# ---------------------------------------------------------------------------
# pode_ver_fila_atendimento / pode_separar_para_retirada
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chefe_almox_pode_ver_fila_atendimento(chefe_almoxarifado):
    assert pode_ver_fila_atendimento(chefe_almoxarifado) is True


@pytest.mark.django_db
def test_aux_almox_pode_ver_fila_atendimento(aux_almoxarifado):
    assert pode_ver_fila_atendimento(aux_almoxarifado) is True


@pytest.mark.django_db
def test_chefe_setor_nao_pode_ver_fila_atendimento(chefe_obras):
    assert pode_ver_fila_atendimento(chefe_obras) is False


@pytest.mark.django_db
def test_aux_setor_nao_pode_ver_fila_atendimento(aux_obras):
    assert pode_ver_fila_atendimento(aux_obras) is False


@pytest.mark.django_db
def test_solicitante_nao_pode_ver_fila_atendimento(solicitante):
    assert pode_ver_fila_atendimento(solicitante) is False


@pytest.mark.django_db
def test_superuser_pode_ver_fila_atendimento(superuser):
    assert pode_ver_fila_atendimento(superuser) is True


@pytest.mark.django_db
def test_inativo_nao_pode_ver_fila_atendimento(usuario_inativo):
    assert pode_ver_fila_atendimento(usuario_inativo) is False


def _req_estado(estado, solicitante, setor_obras, numero):
    return Requisicao.objects.create(
        estado=estado,
        numero_publico=numero,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.mark.django_db
def test_aux_almox_pode_separar_requisicao_autorizada(
    aux_almoxarifado, solicitante, setor_obras
):
    req = _req_estado(
        EstadoRequisicao.AUTORIZADA, solicitante, setor_obras, 'REQ-2026-000200'
    )
    assert pode_separar_para_retirada(aux_almoxarifado, req) is True


@pytest.mark.django_db
def test_chefe_almox_pode_separar_requisicao_autorizada(
    chefe_almoxarifado, solicitante, setor_obras
):
    req = _req_estado(
        EstadoRequisicao.AUTORIZADA, solicitante, setor_obras, 'REQ-2026-000201'
    )
    assert pode_separar_para_retirada(chefe_almoxarifado, req) is True


@pytest.mark.django_db
def test_superuser_pode_separar(superuser, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.AUTORIZADA, solicitante, setor_obras, 'REQ-2026-000202'
    )
    assert pode_separar_para_retirada(superuser, req) is True


@pytest.mark.django_db
def test_chefe_setor_nao_pode_separar(chefe_obras, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.AUTORIZADA, solicitante, setor_obras, 'REQ-2026-000203'
    )
    assert pode_separar_para_retirada(chefe_obras, req) is False


@pytest.mark.django_db
def test_solicitante_nao_pode_separar(solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.AUTORIZADA, solicitante, setor_obras, 'REQ-2026-000204'
    )
    assert pode_separar_para_retirada(solicitante, req) is False


@pytest.mark.django_db
def test_inativo_nao_pode_separar(usuario_inativo, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.AUTORIZADA, solicitante, setor_obras, 'REQ-2026-000300'
    )
    assert pode_separar_para_retirada(usuario_inativo, req) is False


# ---------------------------------------------------------------------------
# pode_atender_retirada
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_aux_almox_pode_atender(aux_almoxarifado, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        solicitante,
        setor_obras,
        'REQ-2026-000400',
    )
    assert pode_atender_retirada(aux_almoxarifado, req) is True


@pytest.mark.django_db
def test_chefe_almox_pode_atender(chefe_almoxarifado, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        solicitante,
        setor_obras,
        'REQ-2026-000401',
    )
    assert pode_atender_retirada(chefe_almoxarifado, req) is True


@pytest.mark.django_db
def test_superuser_pode_atender(superuser, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        solicitante,
        setor_obras,
        'REQ-2026-000402',
    )
    assert pode_atender_retirada(superuser, req) is True


@pytest.mark.django_db
def test_chefe_setor_nao_pode_atender(chefe_obras, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        solicitante,
        setor_obras,
        'REQ-2026-000403',
    )
    assert pode_atender_retirada(chefe_obras, req) is False


@pytest.mark.django_db
def test_solicitante_nao_pode_atender(solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        solicitante,
        setor_obras,
        'REQ-2026-000404',
    )
    assert pode_atender_retirada(solicitante, req) is False


@pytest.mark.django_db
def test_inativo_nao_pode_atender(usuario_inativo, solicitante, setor_obras):
    req = _req_estado(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        solicitante,
        setor_obras,
        'REQ-2026-000405',
    )
    assert pode_atender_retirada(usuario_inativo, req) is False
