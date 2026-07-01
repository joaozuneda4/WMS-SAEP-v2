"""Testes de services de notificações (ADR-0010)."""

from decimal import Decimal

import pytest

from apps.notificacoes.models import Notificacao, TipoNotificacao
from apps.notificacoes.services import criar_notificacoes_para


# ---------------------------------------------------------------------------
# criar_notificacoes_para — helper de deduplicação
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_notificacoes_criador_distinto_beneficiario(
    solicitante, outro_solicitante
):
    """criador ≠ beneficiário → 2 notificações."""
    criar_notificacoes_para(
        criador_id=solicitante.pk,
        beneficiario_id=outro_solicitante.pk,
        requisicao_id=10,
        tipo=TipoNotificacao.AUTORIZACAO,
    )
    notifs = Notificacao.objects.filter(requisicao_id=10)
    assert notifs.count() == 2
    destinatarios = set(notifs.values_list('destinatario_id', flat=True))
    assert destinatarios == {solicitante.pk, outro_solicitante.pk}


@pytest.mark.django_db
def test_criar_notificacoes_mesmo_usuario_uma_notificacao(solicitante):
    """criador == beneficiário → 1 notificação (deduplicação)."""
    criar_notificacoes_para(
        criador_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        requisicao_id=11,
        tipo=TipoNotificacao.AUTORIZACAO,
    )
    notifs = Notificacao.objects.filter(requisicao_id=11)
    assert notifs.count() == 1
    assert notifs.first().destinatario_id == solicitante.pk


# ---------------------------------------------------------------------------
# Hooks em requisicoes.services — autorizar, recusar, atendimento
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_autorizar_requisicao_gera_notificacoes(
    chefe_obras, outro_solicitante, material_disponivel
):
    """autorizar_requisicao dispara notificações para criador e beneficiário."""
    from apps.requisicoes.services import (
        autorizar_requisicao,
        criar_requisicao,
        enviar_para_autorizacao,
    )

    # chefe_obras cria para outro_solicitante (mesmo setor → permitido)
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=outro_solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)
    autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    notifs = Notificacao.objects.filter(
        requisicao_id=req.pk,
        tipo=TipoNotificacao.AUTORIZACAO,
    )
    assert notifs.count() == 2
    destinatarios = set(notifs.values_list('destinatario_id', flat=True))
    assert destinatarios == {chefe_obras.pk, outro_solicitante.pk}


@pytest.mark.django_db(transaction=True)
def test_recusar_requisicao_gera_notificacoes(
    chefe_obras, outro_solicitante, material_disponivel
):
    """recusar_requisicao dispara notificações para criador e beneficiário."""
    from apps.requisicoes.services import (
        criar_requisicao,
        enviar_para_autorizacao,
        recusar_requisicao,
    )

    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=outro_solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)
    recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=req.pk,
        motivo='Sem orçamento',
    )

    notifs = Notificacao.objects.filter(
        requisicao_id=req.pk,
        tipo=TipoNotificacao.RECUSA,
    )
    assert notifs.count() == 2
    destinatarios = set(notifs.values_list('destinatario_id', flat=True))
    assert destinatarios == {chefe_obras.pk, outro_solicitante.pk}


@pytest.mark.django_db(transaction=True)
def test_registrar_atendimento_gera_notificacoes(
    chefe_obras, chefe_almoxarifado, outro_solicitante, material_disponivel
):
    """registrar_atendimento dispara notificações para criador e beneficiário."""
    from apps.requisicoes.services import (
        autorizar_requisicao,
        criar_requisicao,
        enviar_para_autorizacao,
        registrar_atendimento,
        separar_para_retirada,
    )
    from apps.requisicoes.types import LinhaAtendimento

    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=outro_solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)
    autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)
    separar_para_retirada(ator_id=chefe_almoxarifado.pk, requisicao_id=req.pk)

    item = req.itens.first()
    registrar_atendimento(
        ator_id=chefe_almoxarifado.pk,
        requisicao_id=req.pk,
        itens=[
            LinhaAtendimento(
                item_id=item.pk,
                quantidade_entregue=Decimal('1'),
                justificativa='',
            )
        ],
        retirante_nome='Fulano',
    )

    notifs = Notificacao.objects.filter(
        requisicao_id=req.pk,
        tipo=TipoNotificacao.ATENDIMENTO,
    )
    assert notifs.count() == 2
    destinatarios = set(notifs.values_list('destinatario_id', flat=True))
    assert destinatarios == {chefe_obras.pk, outro_solicitante.pk}


@pytest.mark.django_db(transaction=True)
def test_autorizar_requisicao_criador_igual_beneficiario_uma_notificacao(
    chefe_obras, solicitante, material_disponivel
):
    """criador == beneficiário → 1 notificação."""
    from apps.requisicoes.services import (
        autorizar_requisicao,
        criar_requisicao,
        enviar_para_autorizacao,
    )

    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)
    autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    notifs = Notificacao.objects.filter(
        requisicao_id=req.pk,
        tipo=TipoNotificacao.AUTORIZACAO,
    )
    assert notifs.count() == 1


@pytest.mark.django_db(transaction=True)
def test_on_commit_nao_dispara_em_rollback(solicitante, outro_solicitante):
    """on_commit registrado dentro de atomic que faz rollback não persiste notificações."""
    from django.db import transaction

    from apps.notificacoes.services import criar_notificacoes_para

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            transaction.on_commit(
                lambda: criar_notificacoes_para(
                    criador_id=solicitante.pk,
                    beneficiario_id=outro_solicitante.pk,
                    requisicao_id=999,
                    tipo=TipoNotificacao.AUTORIZACAO,
                )
            )
            raise RuntimeError('forçar rollback')

    assert Notificacao.objects.count() == 0


# ---------------------------------------------------------------------------
# Hook em estoque.services — _registrar_atualizacao_estoque_relevante
# ---------------------------------------------------------------------------


def _criar_material_critico(estoque):
    """Material com saldo_fisico < saldo_reservado (divergência pré-existente)."""
    from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida

    m = Material.objects.create(
        codigo='000.001.001',
        nome='Material Crítico Teste',
        unidade=UnidadeMedida.UNIDADE,
        ativo=True,
    )
    SaldoEstoque.objects.create(
        estoque=estoque,
        material=m,
        saldo_fisico=2,
        saldo_reservado=5,
    )
    return m


def _criar_requisicao_autorizada(criador, beneficiario, setor, material):
    """Requisição em estado AUTORIZADA com item do material dado."""
    from decimal import Decimal

    from apps.requisicoes.models import EstadoRequisicao, ItemRequisicao, Requisicao

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2099-000001',
        criador=criador,
        beneficiario=beneficiario,
        setor_beneficiario=setor,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material,
        quantidade_solicitada=Decimal('3'),
        quantidade_autorizada=Decimal('3'),
    )
    return req


@pytest.mark.django_db(transaction=True)
def test_divergencia_estoque_gera_notificacoes_para_requisicao_afetada(
    chefe_obras, superuser, setor_obras, outro_solicitante, estoque_principal
):
    """Importação SCPI com divergência crítica → notifica criador e beneficiário."""
    from apps.estoque.services import confirmar_importacao_scpi
    from apps.requisicoes.services.ciclo_vida import (
        registrar_timeline_divergencia_importacao,
    )

    material = _criar_material_critico(estoque_principal)
    req = _criar_requisicao_autorizada(
        criador=chefe_obras,
        beneficiario=outro_solicitante,
        setor=setor_obras,
        material=material,
    )

    csv_bytes = (
        f'CADPRO;DENOMINACAO;QUAN3\n{material.codigo};Material Critico;001.000\n'
    ).encode('utf-8')
    confirmar_importacao_scpi(
        ator_id=superuser.pk,
        conteudo_bytes=csv_bytes,
        arquivo_nome='import_critico.csv',
        estoque_id=estoque_principal.pk,
        _pos_importacao_hook=registrar_timeline_divergencia_importacao,
    )

    notifs = Notificacao.objects.filter(
        requisicao_id=req.pk,
        tipo=TipoNotificacao.DIVERGENCIA_ESTOQUE,
    )
    assert notifs.count() == 2
    destinatarios = set(notifs.values_list('destinatario_id', flat=True))
    assert destinatarios == {chefe_obras.pk, outro_solicitante.pk}


@pytest.mark.django_db(transaction=True)
def test_divergencia_estoque_deduplica_criador_igual_beneficiario(
    chefe_obras, superuser, setor_obras, solicitante, estoque_principal
):
    """Divergência com criador == beneficiário → 1 notificação."""
    from apps.estoque.services import confirmar_importacao_scpi
    from apps.requisicoes.services.ciclo_vida import (
        registrar_timeline_divergencia_importacao,
    )

    material = _criar_material_critico(estoque_principal)
    # força codigo único para não colidir com outro teste
    material.codigo = '000.001.002'
    material.save(update_fields=['codigo'])
    req = _criar_requisicao_autorizada(
        criador=solicitante,
        beneficiario=solicitante,
        setor=setor_obras,
        material=material,
    )

    csv_bytes = (
        f'CADPRO;DENOMINACAO;QUAN3\n{material.codigo};Material Critico 2;001.000\n'
    ).encode('utf-8')
    confirmar_importacao_scpi(
        ator_id=superuser.pk,
        conteudo_bytes=csv_bytes,
        arquivo_nome='import_dedup.csv',
        estoque_id=estoque_principal.pk,
        _pos_importacao_hook=registrar_timeline_divergencia_importacao,
    )

    notifs = Notificacao.objects.filter(
        requisicao_id=req.pk,
        tipo=TipoNotificacao.DIVERGENCIA_ESTOQUE,
    )
    assert notifs.count() == 1
