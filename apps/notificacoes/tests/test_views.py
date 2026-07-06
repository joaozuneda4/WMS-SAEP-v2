"""Testes de views de notificações (ADR-0010)."""

import pytest
from django.urls import reverse

from apps.notificacoes.models import Notificacao, TipoNotificacao
from apps.requisicoes.models import EstadoRequisicao, Requisicao


@pytest.fixture
def client_logado(client, solicitante):
    client.force_login(solicitante)
    return client


@pytest.mark.django_db
def test_lista_notificacoes_requer_login(client):
    resp = client.get('/notificacoes/')
    assert resp.status_code == 302
    assert '/login/' in resp['Location']


@pytest.mark.django_db
def test_lista_notificacoes_retorna_200(client_logado):
    resp = client_logado.get('/notificacoes/')
    assert resp.status_code == 200


@pytest.mark.django_db
def test_lista_notificacoes_exibe_proprias(
    client_logado, solicitante, outro_solicitante
):
    n_propria = Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.AUTORIZACAO,
        requisicao_id=1,
    )
    Notificacao.objects.create(
        destinatario=outro_solicitante,
        tipo=TipoNotificacao.RECUSA,
        requisicao_id=2,
    )
    resp = client_logado.get('/notificacoes/')
    assert resp.status_code == 200
    notifs = resp.context['notificacoes']
    pks = [n.pk for n in notifs]
    assert n_propria.pk in pks
    assert all(n.destinatario_id == solicitante.pk for n in notifs)


@pytest.mark.django_db
def test_lista_notificacoes_exibe_numero_publico_e_link(
    client_logado, solicitante, setor_obras
):
    requisicao = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000042',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.AUTORIZACAO,
        requisicao_id=requisicao.pk,
    )
    resp = client_logado.get('/notificacoes/')
    html = resp.content.decode('utf-8')
    assert 'REQ-2026-000042' in html
    assert f'Requisição #{requisicao.pk}' not in html
    assert reverse('requisicoes:detalhe', kwargs={'pk': requisicao.pk}) in html


@pytest.mark.django_db
def test_lista_notificacoes_requisicao_inexistente_mostra_fallback(
    client_logado, solicitante
):
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.ATENDIMENTO,
        requisicao_id=999999,
    )
    resp = client_logado.get('/notificacoes/')
    assert resp.status_code == 200
    html = resp.content.decode('utf-8')
    assert 'Rascunho' in html


@pytest.mark.django_db
def test_lista_notificacoes_rascunho_real_mostra_fallback(
    client_logado, solicitante, setor_obras
):
    requisicao = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.ATENDIMENTO,
        requisicao_id=requisicao.pk,
    )
    resp = client_logado.get('/notificacoes/')
    assert resp.status_code == 200
    html = resp.content.decode('utf-8')
    assert 'Rascunho' in html


@pytest.mark.django_db
def test_lista_notificacoes_sem_requisicao_preserva_altura_da_linha(
    client_logado, solicitante
):
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.ATENDIMENTO,
        requisicao_id=None,
    )
    resp = client_logado.get('/notificacoes/')
    html = resp.content.decode('utf-8')
    assert 'Requisição' not in html
    assert (
        '<span class="text-xs text-slate-500" aria-hidden="true">&nbsp;</span>' in html
    )


@pytest.mark.django_db
def test_marcar_lida_marca_notificacao(client_logado, notificacao_nao_lida):
    resp = client_logado.post(f'/notificacoes/{notificacao_nao_lida.pk}/lida/')
    assert resp.status_code in (200, 302, 204)
    notificacao_nao_lida.refresh_from_db()
    assert notificacao_nao_lida.lida is True


@pytest.mark.django_db
def test_marcar_lida_outro_usuario_retorna_404(
    client, outro_solicitante, notificacao_nao_lida
):
    """Query escopada por destinatario — notificação alheia não existe para este usuário."""
    client.force_login(outro_solicitante)
    resp = client.post(f'/notificacoes/{notificacao_nao_lida.pk}/lida/')
    assert resp.status_code == 404
    notificacao_nao_lida.refresh_from_db()
    assert notificacao_nao_lida.lida is False


@pytest.mark.django_db
def test_marcar_todas_lidas(client_logado, solicitante):
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.AUTORIZACAO,
        requisicao_id=10,
    )
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.RECUSA,
        requisicao_id=11,
    )
    resp = client_logado.post('/notificacoes/marcar-todas-lidas/')
    assert resp.status_code in (200, 302, 204)
    assert Notificacao.objects.filter(destinatario=solicitante, lida=False).count() == 0


@pytest.mark.django_db
def test_badge_reflete_contagem_nao_lidas(client_logado, solicitante):
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.AUTORIZACAO,
        requisicao_id=20,
        lida=False,
    )
    Notificacao.objects.create(
        destinatario=solicitante,
        tipo=TipoNotificacao.RECUSA,
        requisicao_id=21,
        lida=True,
    )
    resp = client_logado.get('/notificacoes/')
    assert resp.context['notificacoes_nao_lidas'] == 1
