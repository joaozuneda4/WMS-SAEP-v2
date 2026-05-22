"""Testes de contrato HTTP para views de rascunho (ADR-0010).

Verifica: auth, status codes, redirects, mutations mínimas, presença de messages.
Sem testar HTML detalhado ou texto completo de mensagens.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.requisicoes.models import EstadoRequisicao, Requisicao
from apps.requisicoes.services import criar_requisicao


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, user, password='senha'):
    client.login(username=user.matricula, password=password)


def _formset_post(material_id, quantidade='5', extra=None):
    data = {
        'observacao_geral': '',
        'itens-TOTAL_FORMS': '1',
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
        'itens-0-material_id': str(material_id),
        'itens-0-material_label': 'Material Teste',
        'itens-0-quantidade_solicitada': quantidade,
    }
    if extra:
        data.update(extra)
    return data


# ---------------------------------------------------------------------------
# GET /requisicoes/nova/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_nova_requisicao_get_sem_login(client):
    url = reverse('requisicoes:nova_requisicao')
    resp = client.get(url)
    assert resp.status_code == 302
    assert '/login' in resp['Location'] or 'accounts' in resp['Location']


@pytest.mark.django_db
def test_nova_requisicao_get_com_login(client, solicitante):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:nova_requisicao'))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /requisicoes/nova/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_nova_requisicao_post_valido_cria_e_redireciona(client, solicitante, material_disponivel):
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk)
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)

    req = Requisicao.objects.filter(criador=solicitante).first()
    assert req is not None
    assert req.estado == EstadoRequisicao.RASCUNHO
    assert resp.status_code == 302
    assert reverse('requisicoes:editar_rascunho', kwargs={'pk': req.pk}) in resp['Location']


@pytest.mark.django_db
def test_nova_requisicao_post_sem_itens_retorna_form(client, solicitante):
    _login(client, solicitante)
    data = {
        'observacao_geral': '',
        'itens-TOTAL_FORMS': '1',
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
        'itens-0-material_id': '',
        'itens-0-material_label': '',
        'itens-0-quantidade_solicitada': '',
    }
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)
    assert resp.status_code == 200
    assert not Requisicao.objects.filter(criador=solicitante).exists()


@pytest.mark.django_db
def test_nova_requisicao_post_forjado_beneficiario_fora_escopo(client, solicitante, usuario_ti, material_disponivel):
    """Solicitante com modo='proprio' não pode forjar beneficiario_id via POST.

    O form em modo 'proprio' remove os campos modo_criacao e beneficiario_id, de
    forma que dados extra no payload são silenciosamente ignorados. A view cria a
    requisição para o próprio solicitante e redireciona normalmente (302).
    """
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk, extra={
        'modo_criacao': 'other',
        'beneficiario_id': str(usuario_ti.pk),
    })
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)
    assert resp.status_code == 302
    req = Requisicao.objects.get(criador=solicitante)
    assert req.beneficiario_id == solicitante.pk


@pytest.mark.django_db
def test_nova_requisicao_post_chefe_cria_para_outro_setor_falha(client, chefe_obras, usuario_ti, material_disponivel):
    """Chefe de setor não pode criar para usuário de outro setor.

    O beneficiário fora do escopo é rejeitado no ChoiceField do form (não está nas
    choices geradas pelo escopo). O form fica inválido → re-renderiza com 200 e erros.
    Não há message pois o service não chegou a ser chamado.
    """
    _login(client, chefe_obras)
    data = _formset_post(material_disponivel.pk, extra={
        'modo_criacao': 'other',
        'beneficiario_id': str(usuario_ti.pk),
    })
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)
    # Form inválido (beneficiário fora do escopo) → 200 sem redirect
    assert resp.status_code == 200
    assert not Requisicao.objects.filter(criador=chefe_obras).exists()


# ---------------------------------------------------------------------------
# GET /requisicoes/<pk>/editar/
# ---------------------------------------------------------------------------

@pytest.fixture
def rascunho_solicitante(db, solicitante, material_disponivel):
    return criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[{'material_id': material_disponivel.pk, 'quantidade_solicitada': Decimal('3')}],
    )


@pytest.mark.django_db
def test_editar_rascunho_get_sem_login(client, rascunho_solicitante):
    url = reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk})
    resp = client.get(url)
    assert resp.status_code == 302
    assert '/login' in resp['Location'] or 'accounts' in resp['Location']


@pytest.mark.django_db
def test_editar_rascunho_get_nao_criador_retorna_403(client, outro_usuario_obras, rascunho_solicitante):
    _login(client, outro_usuario_obras)
    resp = client.get(reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk}))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_editar_rascunho_get_estado_diferente_retorna_403(client, solicitante, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000099',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:editar_rascunho', kwargs={'pk': req.pk}))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_editar_rascunho_get_pk_inexistente_retorna_404(client, solicitante):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:editar_rascunho', kwargs={'pk': 99999}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_editar_rascunho_get_criador_retorna_200(client, solicitante, rascunho_solicitante):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk}))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /requisicoes/<pk>/editar/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_editar_rascunho_post_valido_salva_e_redireciona(client, solicitante, rascunho_solicitante, material_disponivel):
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk, quantidade='10', extra={'observacao_geral': 'Obs editada'})
    resp = client.post(
        reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk}),
        data,
    )
    assert resp.status_code == 302
    rascunho_solicitante.refresh_from_db()
    assert rascunho_solicitante.observacao_geral == 'Obs editada'


@pytest.mark.django_db
def test_editar_rascunho_post_material_inativo_retorna_200_com_erro(client, solicitante, rascunho_solicitante, material_inativo):
    _login(client, solicitante)
    data = _formset_post(material_inativo.pk)
    resp = client.post(
        reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk}),
        data,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /requisicoes/materiais/busca/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_buscar_materiais_sem_login(client):
    resp = client.get(reverse('requisicoes:buscar_materiais'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_buscar_materiais_retorna_json(client, solicitante, material_disponivel):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:buscar_materiais'), {'q': 'Para'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'resultados' in data


@pytest.mark.django_db
def test_buscar_materiais_nao_retorna_inativo(client, solicitante, material_inativo):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:buscar_materiais'), {'q': 'Descontinuado'})
    data = resp.json()
    ids = [r['id'] for r in data['resultados']]
    assert material_inativo.pk not in ids


@pytest.mark.django_db
def test_buscar_materiais_nao_retorna_sem_saldo(client, solicitante, material_sem_saldo):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:buscar_materiais'), {'q': 'Prego'})
    data = resp.json()
    ids = [r['id'] for r in data['resultados']]
    assert material_sem_saldo.pk not in ids
