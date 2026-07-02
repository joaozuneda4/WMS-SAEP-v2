"""Testes de autorização contextual para requisições — PapelEfetivo puro (ADR-0010).

Policies não fazem IO. Requisicao é mockada com SimpleNamespace onde possível.
Apenas testes de queryset (resolver_escopo) mantêm acesso ao banco.
"""

from types import SimpleNamespace

import pytest

from apps.accounts.papeis import PapelEfetivo, papel_efetivo
from apps.core.exceptions import PermissaoNegada
from apps.requisicoes.models import EstadoRequisicao
from apps.requisicoes.policies import (
    exigir_pode_consultar_historico_requisicoes,
    exigir_pode_estornar_requisicao,
    pode_atender_retirada,
    pode_autorizar_requisicao,
    pode_cancelar_requisicao,
    pode_consultar_historico_requisicoes,
    pode_copiar_requisicao,
    pode_criar_para_beneficiario,
    pode_editar_rascunho,
    pode_enviar_rascunho,
    pode_estornar_requisicao,
    pode_recusar_requisicao,
    pode_registrar_devolucao,
    pode_retornar_para_rascunho,
    pode_separar_para_retirada,
    pode_ser_beneficiario,
    pode_ver_fila_atendimento,
    pode_ver_fila_autorizacao,
    resolver_escopo_criacao_requisicao,
)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

SETOR_ID = 10
SETOR_TI_ID = 20
SETOR_ALMOX_ID = 30
ATOR_ID = 1
OUTRO_ID = 2


def _papel(
    *,
    ativo: bool = True,
    eh_superusuario: bool = False,
    eh_almoxarifado: bool = False,
    eh_chefe_de_almoxarifado: bool = False,
    setores_em_escopo: tuple[int, ...] = (),
    setor_chefiado_ativo_id: int | None = None,
    pode_ser_beneficiario_flag: bool = True,
    ator_id: int = ATOR_ID,
) -> PapelEfetivo:
    return PapelEfetivo(
        ativo=ativo,
        eh_superusuario=eh_superusuario,
        eh_almoxarifado=eh_almoxarifado,
        eh_chefe_de_almoxarifado=eh_chefe_de_almoxarifado,
        setores_em_escopo=setores_em_escopo,
        setor_chefiado_ativo_id=setor_chefiado_ativo_id,
        pode_ser_beneficiario=pode_ser_beneficiario_flag,
        ator_id=ator_id,
    )


def _req(
    estado: str,
    criador_id: int = ATOR_ID,
    beneficiario_id: int = ATOR_ID,
    setor_beneficiario_id: int = SETOR_ID,
    beneficiario=None,
) -> SimpleNamespace:
    ns = SimpleNamespace(
        estado=estado,
        criador_id=criador_id,
        beneficiario_id=beneficiario_id,
        setor_beneficiario_id=setor_beneficiario_id,
    )
    if beneficiario is not None:
        ns.beneficiario = beneficiario
    return ns


def _user(
    pk: int = ATOR_ID,
    is_active: bool = True,
    setor_id: int | None = SETOR_ID,
    nome: str = 'Usuário',
) -> SimpleNamespace:
    return SimpleNamespace(pk=pk, is_active=is_active, setor_id=setor_id, nome=nome)


# Personas reutilizáveis
SOLICITANTE = _papel(ator_id=ATOR_ID, pode_ser_beneficiario_flag=True)
OUTRO = _papel(ator_id=OUTRO_ID, pode_ser_beneficiario_flag=True)
CHEFE_OBRAS = _papel(
    ator_id=ATOR_ID,
    setores_em_escopo=(SETOR_ID,),
    setor_chefiado_ativo_id=SETOR_ID,
    pode_ser_beneficiario_flag=True,
)
AUX_OBRAS = _papel(
    ator_id=ATOR_ID,
    setores_em_escopo=(SETOR_ID,),
    setor_chefiado_ativo_id=None,
    pode_ser_beneficiario_flag=True,
)
AUX_ALMOX = _papel(
    ator_id=ATOR_ID,
    eh_almoxarifado=True,
    eh_chefe_de_almoxarifado=False,
    pode_ser_beneficiario_flag=True,
)
CHEFE_ALMOX = _papel(
    ator_id=ATOR_ID,
    eh_almoxarifado=True,
    eh_chefe_de_almoxarifado=True,
    setor_chefiado_ativo_id=SETOR_ALMOX_ID,
    pode_ser_beneficiario_flag=True,
)
SUPERUSER = _papel(
    ator_id=ATOR_ID, eh_superusuario=True, pode_ser_beneficiario_flag=True
)
INATIVO = _papel(ator_id=ATOR_ID, ativo=False, pode_ser_beneficiario_flag=False)
SEM_SETOR = _papel(ator_id=ATOR_ID, pode_ser_beneficiario_flag=False)


# ---------------------------------------------------------------------------
# pode_ser_beneficiario
# ---------------------------------------------------------------------------


def test_pode_ser_beneficiario_ativo_com_setor():
    assert pode_ser_beneficiario(SOLICITANTE) is True


def test_pode_ser_beneficiario_inativo():
    assert pode_ser_beneficiario(INATIVO) is False


def test_pode_ser_beneficiario_sem_setor():
    assert pode_ser_beneficiario(SEM_SETOR) is False


# ---------------------------------------------------------------------------
# resolver_escopo_criacao_requisicao — modo (sem banco onde possível)
# ---------------------------------------------------------------------------


def test_escopo_solicitante_puro():
    escopo = resolver_escopo_criacao_requisicao(SOLICITANTE)
    assert escopo.modo_beneficiario == 'proprio'
    assert escopo.pode_criar_para_si is True
    assert escopo.setores_escopo_ids == []


def test_escopo_ator_sem_setor_levanta_permissao_negada():
    with pytest.raises(PermissaoNegada):
        resolver_escopo_criacao_requisicao(SEM_SETOR)


def test_escopo_chefe_setor_nao_almox():
    escopo = resolver_escopo_criacao_requisicao(CHEFE_OBRAS)
    assert escopo.modo_beneficiario == 'setor'
    assert SETOR_ID in escopo.setores_escopo_ids
    assert escopo.pode_criar_para_si is True


def test_escopo_aux_setor_nao_almox():
    escopo = resolver_escopo_criacao_requisicao(AUX_OBRAS)
    assert escopo.modo_beneficiario == 'setor'
    assert SETOR_ID in escopo.setores_escopo_ids


def test_escopo_aux_almoxarifado():
    escopo = resolver_escopo_criacao_requisicao(AUX_ALMOX)
    assert escopo.modo_beneficiario == 'qualquer'


def test_escopo_chefe_almoxarifado():
    escopo = resolver_escopo_criacao_requisicao(CHEFE_ALMOX)
    assert escopo.modo_beneficiario == 'qualquer'


def test_escopo_precedencia_chefe_setor_mais_aux_almox():
    """Papel com setor em escopo E almoxarifado → modo=qualquer."""
    papel = _papel(
        setores_em_escopo=(SETOR_ID,),
        eh_almoxarifado=True,
        setor_chefiado_ativo_id=SETOR_ID,
    )
    escopo = resolver_escopo_criacao_requisicao(papel)
    assert escopo.modo_beneficiario == 'qualquer'


def test_escopo_ator_almox_sem_setor_proprio_pode_criar_para_si_false():
    """Ator com papel de almox mas pode_ser_beneficiario=False → pode_criar_para_si=False."""
    papel = _papel(eh_almoxarifado=True, pode_ser_beneficiario_flag=False)
    escopo = resolver_escopo_criacao_requisicao(papel)
    assert escopo.modo_beneficiario == 'qualquer'
    assert escopo.pode_criar_para_si is False


def test_escopo_inativo_levanta_permissao_negada():
    with pytest.raises(PermissaoNegada):
        resolver_escopo_criacao_requisicao(INATIVO)


# Testes de queryset precisam de banco
@pytest.mark.django_db
def test_escopo_setor_exclui_proprio_ator(chefe_obras, outro_usuario_obras):
    papel = papel_efetivo(chefe_obras)
    escopo = resolver_escopo_criacao_requisicao(papel)
    ids = set(escopo.beneficiarios.values_list('pk', flat=True))
    assert chefe_obras.pk not in ids
    assert outro_usuario_obras.pk in ids


@pytest.mark.django_db
def test_escopo_setor_exclui_usuarios_de_outro_setor(chefe_obras, usuario_ti):
    papel = papel_efetivo(chefe_obras)
    escopo = resolver_escopo_criacao_requisicao(papel)
    ids = set(escopo.beneficiarios.values_list('pk', flat=True))
    assert usuario_ti.pk not in ids


@pytest.mark.django_db
def test_escopo_qualquer_exclui_proprio_ator(aux_almoxarifado, solicitante):
    papel = papel_efetivo(aux_almoxarifado)
    escopo = resolver_escopo_criacao_requisicao(papel)
    ids = set(escopo.beneficiarios.values_list('pk', flat=True))
    assert aux_almoxarifado.pk not in ids
    assert solicitante.pk in ids


# ---------------------------------------------------------------------------
# pode_criar_para_beneficiario
# ---------------------------------------------------------------------------


def test_pode_criar_para_si():
    user = _user(pk=ATOR_ID)
    assert pode_criar_para_beneficiario(SOLICITANTE, user) is True


def test_solicitante_nao_pode_criar_para_terceiro():
    outro = _user(pk=OUTRO_ID)
    assert pode_criar_para_beneficiario(SOLICITANTE, outro) is False


def test_chefe_setor_pode_criar_para_membro_do_setor():
    membro = _user(pk=OUTRO_ID, setor_id=SETOR_ID)
    assert pode_criar_para_beneficiario(CHEFE_OBRAS, membro) is True


def test_chefe_setor_nao_pode_criar_para_outro_setor():
    ti = _user(pk=OUTRO_ID, setor_id=SETOR_TI_ID)
    assert pode_criar_para_beneficiario(CHEFE_OBRAS, ti) is False


def test_aux_almox_pode_criar_para_qualquer_setor():
    ti = _user(pk=OUTRO_ID, setor_id=SETOR_TI_ID)
    assert pode_criar_para_beneficiario(AUX_ALMOX, ti) is True


def test_nao_pode_criar_para_beneficiario_inativo():
    inativo = _user(pk=OUTRO_ID, is_active=False)
    assert pode_criar_para_beneficiario(SOLICITANTE, inativo) is False


def test_nao_pode_criar_para_beneficiario_sem_setor():
    sem_setor = _user(pk=OUTRO_ID, setor_id=None)
    assert pode_criar_para_beneficiario(AUX_ALMOX, sem_setor) is False


# ---------------------------------------------------------------------------
# pode_editar_rascunho
# ---------------------------------------------------------------------------


def test_criador_pode_editar_rascunho():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=ATOR_ID)
    assert pode_editar_rascunho(SOLICITANTE, req) is True


def test_nao_criador_nao_pode_editar():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=ATOR_ID)
    assert pode_editar_rascunho(OUTRO, req) is False


def test_criador_retorna_true_independente_do_estado():
    """pode_editar_rascunho verifica apenas criador; estado é validado pelo service."""
    req = _req(EstadoRequisicao.AGUARDANDO_AUTORIZACAO, criador_id=ATOR_ID)
    assert pode_editar_rascunho(SOLICITANTE, req) is True


def test_superusuario_pode_editar_rascunho_de_terceiro():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=OUTRO_ID)
    assert pode_editar_rascunho(SUPERUSER, req) is True


# ---------------------------------------------------------------------------
# pode_enviar_rascunho
# ---------------------------------------------------------------------------


def test_criador_pode_enviar_rascunho():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=ATOR_ID)
    assert pode_enviar_rascunho(SOLICITANTE, req) is True


def test_nao_criador_nao_pode_enviar():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=ATOR_ID)
    assert pode_enviar_rascunho(OUTRO, req) is False


def test_criador_inativo_nao_pode_enviar():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=ATOR_ID)
    assert pode_enviar_rascunho(INATIVO, req) is False


def test_superusuario_pode_enviar_rascunho_de_terceiro():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=OUTRO_ID)
    assert pode_enviar_rascunho(SUPERUSER, req) is True


# ---------------------------------------------------------------------------
# Fila de autorização
# ---------------------------------------------------------------------------


def test_chefe_setor_pode_ver_fila_autorizacao():
    assert pode_ver_fila_autorizacao(CHEFE_OBRAS) is True


def test_auxiliar_almox_nao_pode_ver_fila_autorizacao():
    assert pode_ver_fila_autorizacao(AUX_ALMOX) is False


def test_superuser_pode_ver_fila_autorizacao():
    assert pode_ver_fila_autorizacao(SUPERUSER) is True


def test_inativo_nao_pode_ver_fila_autorizacao():
    assert pode_ver_fila_autorizacao(INATIVO) is False


# ---------------------------------------------------------------------------
# pode_retornar_para_rascunho
# ---------------------------------------------------------------------------


def test_criador_pode_retornar_para_rascunho():
    req = _req(
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        criador_id=ATOR_ID,
        beneficiario_id=ATOR_ID,
    )
    assert pode_retornar_para_rascunho(SOLICITANTE, req) is True


def test_terceiro_nao_pode_retornar_para_rascunho():
    req = _req(
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        criador_id=ATOR_ID,
        beneficiario_id=ATOR_ID,
    )
    assert pode_retornar_para_rascunho(OUTRO, req) is False


# ---------------------------------------------------------------------------
# pode_cancelar_requisicao
# ---------------------------------------------------------------------------


def test_criador_pode_cancelar_rascunho():
    req = _req(EstadoRequisicao.RASCUNHO, criador_id=ATOR_ID)
    assert pode_cancelar_requisicao(SOLICITANTE, req) is True


def test_beneficiario_pode_cancelar_aguardando_autorizacao():
    req = _req(
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        criador_id=OUTRO_ID,
        beneficiario_id=ATOR_ID,
    )
    assert pode_cancelar_requisicao(SOLICITANTE, req) is True


def test_aux_almox_pode_cancelar_autorizada():
    req = _req(
        EstadoRequisicao.AUTORIZADA, criador_id=OUTRO_ID, beneficiario_id=OUTRO_ID
    )
    assert pode_cancelar_requisicao(AUX_ALMOX, req) is True


def test_criador_pode_cancelar_pronta_para_retirada():
    req = _req(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        criador_id=ATOR_ID,
        beneficiario_id=OUTRO_ID,
    )
    assert pode_cancelar_requisicao(SOLICITANTE, req) is True


def test_beneficiario_pode_cancelar_pronta_para_retirada():
    req = _req(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        criador_id=OUTRO_ID,
        beneficiario_id=ATOR_ID,
    )
    assert pode_cancelar_requisicao(SOLICITANTE, req) is True


def test_almox_pode_cancelar_pronta_para_retirada():
    req = _req(
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
        criador_id=OUTRO_ID,
        beneficiario_id=OUTRO_ID,
    )
    assert pode_cancelar_requisicao(AUX_ALMOX, req) is True


@pytest.mark.parametrize(
    'estado',
    [
        EstadoRequisicao.ATENDIDA,
        EstadoRequisicao.CANCELADA,
        EstadoRequisicao.RECUSADA,
        EstadoRequisicao.ESTORNADA,
    ],
)
def test_cancelamento_negado_em_estados_finais(estado):
    req = _req(estado, criador_id=ATOR_ID, beneficiario_id=ATOR_ID)
    assert pode_cancelar_requisicao(SOLICITANTE, req) is False
    assert pode_cancelar_requisicao(AUX_ALMOX, req) is False
    assert pode_cancelar_requisicao(SUPERUSER, req) is False


def test_chefe_setor_nao_pode_cancelar_autorizada_de_outro_setor():
    req = _req(
        EstadoRequisicao.AUTORIZADA,
        criador_id=OUTRO_ID,
        beneficiario_id=OUTRO_ID,
        setor_beneficiario_id=SETOR_TI_ID,
    )
    assert pode_cancelar_requisicao(CHEFE_OBRAS, req) is False


# ---------------------------------------------------------------------------
# pode_recusar_requisicao / pode_autorizar_requisicao
# ---------------------------------------------------------------------------


def test_chefe_setor_pode_recusar_requisicao_do_setor():
    req = _req(EstadoRequisicao.AGUARDANDO_AUTORIZACAO, setor_beneficiario_id=SETOR_ID)
    assert pode_recusar_requisicao(CHEFE_OBRAS, req) is True


def test_chefe_setor_pode_autorizar_requisicao_do_setor():
    req = _req(EstadoRequisicao.AGUARDANDO_AUTORIZACAO, setor_beneficiario_id=SETOR_ID)
    assert pode_autorizar_requisicao(CHEFE_OBRAS, req) is True


def test_chefe_setor_nao_pode_autorizar_requisicao_de_outro_setor():
    req = _req(
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO, setor_beneficiario_id=SETOR_TI_ID
    )
    assert pode_autorizar_requisicao(CHEFE_OBRAS, req) is False


def test_chefe_almox_nao_pode_autorizar_requisicao_de_outro_setor():
    """Chefe de almox não é chefe de setor de obras → não pode autorizar."""
    req = _req(EstadoRequisicao.AGUARDANDO_AUTORIZACAO, setor_beneficiario_id=SETOR_ID)
    assert pode_autorizar_requisicao(CHEFE_ALMOX, req) is False


def test_chefe_almox_nao_recusa_requisicao_de_outro_setor():
    req = _req(EstadoRequisicao.AGUARDANDO_AUTORIZACAO, setor_beneficiario_id=SETOR_ID)
    assert pode_recusar_requisicao(CHEFE_ALMOX, req) is False


def test_superuser_pode_autorizar_qualquer_requisicao():
    req = _req(
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO, setor_beneficiario_id=SETOR_TI_ID
    )
    assert pode_autorizar_requisicao(SUPERUSER, req) is True


# ---------------------------------------------------------------------------
# pode_ver_fila_atendimento
# ---------------------------------------------------------------------------


def test_chefe_almox_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(CHEFE_ALMOX) is True


def test_aux_almox_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(AUX_ALMOX) is True


def test_chefe_setor_nao_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(CHEFE_OBRAS) is False


def test_aux_setor_nao_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(AUX_OBRAS) is False


def test_solicitante_nao_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(SOLICITANTE) is False


def test_superuser_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(SUPERUSER) is True


def test_inativo_nao_pode_ver_fila_atendimento():
    assert pode_ver_fila_atendimento(INATIVO) is False


# ---------------------------------------------------------------------------
# pode_separar_para_retirada
# ---------------------------------------------------------------------------


def test_aux_almox_pode_separar_requisicao_autorizada():
    req = _req(EstadoRequisicao.AUTORIZADA)
    assert pode_separar_para_retirada(AUX_ALMOX, req) is True


def test_chefe_almox_pode_separar_requisicao_autorizada():
    req = _req(EstadoRequisicao.AUTORIZADA)
    assert pode_separar_para_retirada(CHEFE_ALMOX, req) is True


def test_superuser_pode_separar():
    req = _req(EstadoRequisicao.AUTORIZADA)
    assert pode_separar_para_retirada(SUPERUSER, req) is True


def test_chefe_setor_nao_pode_separar():
    req = _req(EstadoRequisicao.AUTORIZADA)
    assert pode_separar_para_retirada(CHEFE_OBRAS, req) is False


def test_solicitante_nao_pode_separar():
    req = _req(EstadoRequisicao.AUTORIZADA)
    assert pode_separar_para_retirada(SOLICITANTE, req) is False


def test_inativo_nao_pode_separar():
    req = _req(EstadoRequisicao.AUTORIZADA)
    assert pode_separar_para_retirada(INATIVO, req) is False


# ---------------------------------------------------------------------------
# pode_atender_retirada
# ---------------------------------------------------------------------------


def test_aux_almox_pode_atender():
    req = _req(EstadoRequisicao.PRONTA_PARA_RETIRADA)
    assert pode_atender_retirada(AUX_ALMOX, req) is True


def test_chefe_almox_pode_atender():
    req = _req(EstadoRequisicao.PRONTA_PARA_RETIRADA)
    assert pode_atender_retirada(CHEFE_ALMOX, req) is True


def test_superuser_pode_atender():
    req = _req(EstadoRequisicao.PRONTA_PARA_RETIRADA)
    assert pode_atender_retirada(SUPERUSER, req) is True


def test_chefe_setor_nao_pode_atender():
    req = _req(EstadoRequisicao.PRONTA_PARA_RETIRADA)
    assert pode_atender_retirada(CHEFE_OBRAS, req) is False


def test_solicitante_nao_pode_atender():
    req = _req(EstadoRequisicao.PRONTA_PARA_RETIRADA)
    assert pode_atender_retirada(SOLICITANTE, req) is False


def test_inativo_nao_pode_atender():
    req = _req(EstadoRequisicao.PRONTA_PARA_RETIRADA)
    assert pode_atender_retirada(INATIVO, req) is False


@pytest.mark.parametrize(
    'estado',
    [
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.ATENDIDA,
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        EstadoRequisicao.CANCELADA,
    ],
)
def test_aux_almox_nao_pode_atender_fora_de_pronta_para_retirada(estado):
    req = _req(estado)
    assert pode_atender_retirada(AUX_ALMOX, req) is False, (
        f'estado={estado} não deveria permitir atendimento'
    )


# ---------------------------------------------------------------------------
# pode_copiar_requisicao
# ---------------------------------------------------------------------------


def test_solicitante_pode_copiar_propria_req():
    beneficiario = _user(pk=ATOR_ID, setor_id=SETOR_ID)
    req = _req(
        EstadoRequisicao.RECUSADA,
        criador_id=ATOR_ID,
        beneficiario_id=ATOR_ID,
        beneficiario=beneficiario,
    )
    assert pode_copiar_requisicao(SOLICITANTE, req) is True


def test_usuario_outro_setor_nao_pode_copiar():
    beneficiario = _user(pk=ATOR_ID, setor_id=SETOR_ID)
    req = _req(
        EstadoRequisicao.RECUSADA,
        criador_id=ATOR_ID,
        beneficiario_id=ATOR_ID,
        beneficiario=beneficiario,
    )
    outro_setor = _papel(ator_id=OUTRO_ID, setores_em_escopo=(SETOR_TI_ID,))
    assert pode_copiar_requisicao(outro_setor, req) is False


def test_superuser_pode_copiar():
    beneficiario = _user(pk=ATOR_ID, setor_id=SETOR_ID)
    req = _req(
        EstadoRequisicao.RECUSADA,
        criador_id=ATOR_ID,
        beneficiario_id=ATOR_ID,
        beneficiario=beneficiario,
    )
    assert pode_copiar_requisicao(SUPERUSER, req) is True


def test_inativo_nao_pode_copiar():
    beneficiario = _user(pk=ATOR_ID, setor_id=SETOR_ID)
    req = _req(
        EstadoRequisicao.RECUSADA,
        criador_id=ATOR_ID,
        beneficiario_id=ATOR_ID,
        beneficiario=beneficiario,
    )
    assert pode_copiar_requisicao(INATIVO, req) is False


# ---------------------------------------------------------------------------
# pode_registrar_devolucao
# ---------------------------------------------------------------------------


def test_aux_almoxarifado_pode_registrar_devolucao():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_registrar_devolucao(AUX_ALMOX, req) is True


def test_chefe_almoxarifado_pode_registrar_devolucao():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_registrar_devolucao(CHEFE_ALMOX, req) is True


def test_superuser_pode_registrar_devolucao():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_registrar_devolucao(SUPERUSER, req) is True


def test_solicitante_nao_pode_registrar_devolucao():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_registrar_devolucao(SOLICITANTE, req) is False


def test_inativo_nao_pode_registrar_devolucao():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_registrar_devolucao(INATIVO, req) is False


# ---------------------------------------------------------------------------
# pode_estornar_requisicao
# ---------------------------------------------------------------------------


def test_chefe_almoxarifado_pode_estornar():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_estornar_requisicao(CHEFE_ALMOX, req) is True


def test_aux_almox_nao_pode_estornar():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_estornar_requisicao(AUX_ALMOX, req) is False


def test_superuser_pode_estornar():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_estornar_requisicao(SUPERUSER, req) is True


def test_inativo_nao_pode_estornar():
    req = _req(EstadoRequisicao.ATENDIDA)
    assert pode_estornar_requisicao(INATIVO, req) is False


def test_exigir_pode_estornar_levanta_permissao_negada():
    req = _req(EstadoRequisicao.ATENDIDA)
    with pytest.raises(PermissaoNegada) as excinfo:
        exigir_pode_estornar_requisicao(AUX_ALMOX, req)
    assert excinfo.value.code == 'estornar_requisicao_negada'


# ---------------------------------------------------------------------------
# pode_consultar_historico_requisicoes / exigir_
# ---------------------------------------------------------------------------


class TestPodeConsultarHistoricoRequisicoes:
    def test_superuser_pode(self):
        assert pode_consultar_historico_requisicoes(SUPERUSER) is True

    def test_chefe_almoxarifado_pode(self):
        assert pode_consultar_historico_requisicoes(CHEFE_ALMOX) is True

    def test_aux_almoxarifado_pode(self):
        assert pode_consultar_historico_requisicoes(AUX_ALMOX) is True

    def test_chefe_setor_nao_almox_pode(self):
        assert pode_consultar_historico_requisicoes(CHEFE_OBRAS) is True

    def test_solicitante_puro_nao_pode(self):
        assert pode_consultar_historico_requisicoes(SOLICITANTE) is False

    def test_inativo_nao_pode(self):
        assert pode_consultar_historico_requisicoes(INATIVO) is False


class TestExigirPodeConsultarHistoricoRequisicoes:
    def test_superuser_nao_lanca(self):
        exigir_pode_consultar_historico_requisicoes(SUPERUSER)

    def test_solicitante_lanca(self):
        with pytest.raises(PermissaoNegada):
            exigir_pode_consultar_historico_requisicoes(SOLICITANTE)
