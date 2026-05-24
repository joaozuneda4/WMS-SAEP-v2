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
def test_nova_requisicao_post_valido_cria_e_redireciona(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk)
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)

    req = Requisicao.objects.filter(criador=solicitante).first()
    assert req is not None
    assert req.estado == EstadoRequisicao.RASCUNHO
    assert resp.status_code == 302
    assert reverse('requisicoes:detalhe', kwargs={'pk': req.pk}) in resp['Location']


@pytest.mark.django_db
def test_nova_requisicao_post_acao_enviar_cria_e_envia(
    client, solicitante, material_disponivel
):
    """Botão 'Criar e enviar' cria rascunho + envia para autorização atomicamente."""
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk, extra={'acao': 'enviar'})
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)

    req = Requisicao.objects.filter(criador=solicitante).first()
    assert req is not None
    assert req.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    assert req.numero_publico is not None
    assert resp.status_code == 302
    assert reverse('requisicoes:detalhe', kwargs={'pk': req.pk}) in resp['Location']

    eventos = list(req.eventos.values_list('evento', flat=True))
    assert 'criacao' in eventos
    assert 'envio_autorizacao' in eventos


@pytest.mark.django_db
def test_nova_requisicao_post_acao_rascunho_explicito(
    client, solicitante, material_disponivel
):
    """acao='rascunho' redireciona para o detalhe do rascunho criado."""
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk, extra={'acao': 'rascunho'})
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)

    req = Requisicao.objects.filter(criador=solicitante).first()
    assert req.estado == EstadoRequisicao.RASCUNHO
    assert req.numero_publico is None
    assert resp.status_code == 302
    assert reverse('requisicoes:detalhe', kwargs={'pk': req.pk}) in resp['Location']


@pytest.mark.django_db
def test_nova_requisicao_post_sem_acao_default_eh_rascunho(
    client, solicitante, material_disponivel
):
    """Enter em campo → POST sem 'acao' → default seguro = rascunho.

    Guarda contra regressão: 'Criar e enviar' NÃO pode ser o default ao
    pressionar Enter em um input. View deve cair no ramo rascunho.
    """
    _login(client, solicitante)
    data = _formset_post(material_disponivel.pk)
    assert 'acao' not in data
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)

    req = Requisicao.objects.filter(criador=solicitante).first()
    assert req.estado == EstadoRequisicao.RASCUNHO
    assert req.numero_publico is None
    assert resp.status_code == 302
    assert reverse('requisicoes:detalhe', kwargs={'pk': req.pk}) in resp['Location']


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
def test_nova_requisicao_post_forjado_beneficiario_fora_escopo(
    client, solicitante, usuario_ti, material_disponivel
):
    """Solicitante com modo='proprio' não pode forjar beneficiario_id via POST.

    O form em modo 'proprio' remove os campos modo_criacao e beneficiario_id, de
    forma que dados extra no payload são silenciosamente ignorados. A view cria a
    requisição para o próprio solicitante e redireciona normalmente (302).
    """
    _login(client, solicitante)
    data = _formset_post(
        material_disponivel.pk,
        extra={
            'modo_criacao': 'outro',
            'beneficiario_id': str(usuario_ti.pk),
        },
    )
    resp = client.post(reverse('requisicoes:nova_requisicao'), data)
    assert resp.status_code == 302
    req = Requisicao.objects.get(criador=solicitante)
    assert req.beneficiario_id == solicitante.pk


@pytest.mark.django_db
def test_nova_requisicao_post_chefe_cria_para_outro_setor_falha(
    client, chefe_obras, usuario_ti, material_disponivel
):
    """Chefe de setor não pode criar para usuário de outro setor.

    O beneficiário fora do escopo é rejeitado no ChoiceField do form (não está nas
    choices geradas pelo escopo). O form fica inválido → re-renderiza com 200 e erros.
    Não há message pois o service não chegou a ser chamado.
    """
    _login(client, chefe_obras)
    data = _formset_post(
        material_disponivel.pk,
        extra={
            'modo_criacao': 'outro',
            'beneficiario_id': str(usuario_ti.pk),
        },
    )
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
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('3'),
            }
        ],
    )


@pytest.mark.django_db
def test_editar_rascunho_get_sem_login(client, rascunho_solicitante):
    url = reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk})
    resp = client.get(url)
    assert resp.status_code == 302
    assert '/login' in resp['Location'] or 'accounts' in resp['Location']


@pytest.mark.django_db
def test_editar_rascunho_get_nao_criador_retorna_403(
    client, outro_usuario_obras, rascunho_solicitante
):
    _login(client, outro_usuario_obras)
    resp = client.get(
        reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk})
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_editar_rascunho_get_estado_diferente_retorna_403(
    client, solicitante, setor_obras
):
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
def test_editar_rascunho_get_criador_retorna_200(
    client, solicitante, rascunho_solicitante
):
    _login(client, solicitante)
    resp = client.get(
        reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk})
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /requisicoes/<pk>/editar/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_editar_rascunho_post_valido_salva_e_redireciona(
    client, solicitante, rascunho_solicitante, material_disponivel
):
    _login(client, solicitante)
    data = _formset_post(
        material_disponivel.pk,
        quantidade='10',
        extra={'observacao_geral': 'Obs editada'},
    )
    resp = client.post(
        reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk}),
        data,
    )
    assert resp.status_code == 302
    assert resp['Location'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': rascunho_solicitante.pk}
    )
    rascunho_solicitante.refresh_from_db()
    assert rascunho_solicitante.observacao_geral == 'Obs editada'


@pytest.mark.django_db
def test_editar_rascunho_post_material_inativo_retorna_200_com_erro(
    client, solicitante, rascunho_solicitante, material_inativo
):
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
def test_buscar_materiais_shape(client, solicitante, material_disponivel):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:buscar_materiais'), {'q': 'Para'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'resultados' in data
    assert len(data['resultados']) > 0
    for r in data['resultados']:
        assert 'id' in r
        assert 'nome' in r
        assert 'codigo' in r
        assert 'saldo_disponivel' in r


# ---------------------------------------------------------------------------
# Minhas requisições — lista
# ---------------------------------------------------------------------------


@pytest.fixture
def req_rascunho_solicitante(db, solicitante, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.fixture
def req_enviada_solicitante(db, solicitante, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-0010',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.fixture
def req_rascunho_aux_para_solicitante(db, aux_obras, solicitante, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=aux_obras,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.fixture
def req_outro_setor_view(db, usuario_ti, setor_ti):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-0011',
        criador=usuario_ti,
        beneficiario=usuario_ti,
        setor_beneficiario=setor_ti,
    )


@pytest.mark.django_db
def test_minhas_get_sem_login_redireciona(client):
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 302
    assert '/entrar' in response['Location'] or '/login' in response['Location']


@pytest.mark.django_db
def test_minhas_get_autenticado_200(client, solicitante, req_enviada_solicitante):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 200
    requisicoes = list(response.context['requisicoes'])
    assert req_enviada_solicitante in requisicoes


@pytest.mark.django_db
def test_minhas_exclui_rascunho_de_terceiro(
    client, solicitante, req_rascunho_aux_para_solicitante
):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 200
    assert req_rascunho_aux_para_solicitante not in list(
        response.context['requisicoes']
    )


@pytest.mark.django_db
def test_minhas_renderiza_numero_publico_e_fallback_rascunho(
    client, solicitante, req_rascunho_solicitante, req_enviada_solicitante
):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:minhas'))
    html = response.content.decode()
    assert 'REQ-2026-0010' in html
    assert 'Rascunho' in html


# ---------------------------------------------------------------------------
# Detalhe da requisição
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_detalhe_sem_login_redireciona(client, req_enviada_solicitante):
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_detalhe_criador_200(client, solicitante, req_enviada_solicitante):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    assert response.status_code == 200
    assert response.context['requisicao'].pk == req_enviada_solicitante.pk


@pytest.mark.django_db
def test_detalhe_rascunho_de_terceiro_para_beneficiario_404(
    client, solicitante, req_rascunho_aux_para_solicitante
):
    _login(client, solicitante)
    response = client.get(
        reverse(
            'requisicoes:detalhe',
            kwargs={'pk': req_rascunho_aux_para_solicitante.pk},
        )
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_detalhe_outro_setor_sem_papel_404(client, solicitante, req_outro_setor_view):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_outro_setor_view.pk})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_detalhe_chefe_setor_ve_requisicao_do_setor(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_detalhe_chefe_setor_nao_ve_rascunho_de_terceiro(
    client, chefe_obras, req_rascunho_solicitante
):
    _login(client, chefe_obras)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_rascunho_solicitante.pk})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_detalhe_almox_ve_outro_setor(client, aux_almoxarifado, req_outro_setor_view):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_outro_setor_view.pk})
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_detalhe_renderiza_timeline_e_itens(
    client, solicitante, material_disponivel, setor_obras
):
    _login(client, solicitante)
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('3'),
            }
        ],
    )
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert list(response.context['itens'])
    assert list(response.context['eventos'])


# ---------------------------------------------------------------------------
# Enviar rascunho — TR-005
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_enviar_rascunho_get_retorna_405(client, solicitante, setor_obras):
    _login(client, solicitante)
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    response = client.get(reverse('requisicoes:enviar_rascunho', kwargs={'pk': req.pk}))
    assert response.status_code == 405


@pytest.mark.django_db
def test_enviar_rascunho_post_sem_login_redireciona(client, solicitante, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    response = client.post(
        reverse('requisicoes:enviar_rascunho', kwargs={'pk': req.pk})
    )
    assert response.status_code == 302
    assert '/login' in response.url or '/accounts/login' in response.url


@pytest.mark.django_db
def test_enviar_rascunho_post_nao_criador_retorna_403(
    client, solicitante, outro_usuario_obras, setor_obras
):
    _login(client, outro_usuario_obras)
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    response = client.post(
        reverse('requisicoes:enviar_rascunho', kwargs={'pk': req.pk})
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_enviar_rascunho_post_criador_redireciona_detalhe(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
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
    response = client.post(
        reverse('requisicoes:enviar_rascunho', kwargs={'pk': req.pk})
    )
    assert response.status_code == 302
    assert response.url == reverse('requisicoes:detalhe', kwargs={'pk': req.pk})
    req.refresh_from_db()
    assert req.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    assert req.numero_publico is not None


@pytest.mark.django_db
def test_enviar_rascunho_post_estado_invalido_mostra_warning(
    client, solicitante, setor_obras, material_disponivel
):
    """EstadoInvalido vira messages.warning (contrato de mensagens)."""
    from django.contrib.messages import constants as message_constants

    _login(client, solicitante)
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
    req.estado = EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    req.numero_publico = 'REQ-2026-000777'
    req.save(update_fields=['estado', 'numero_publico'])

    response = client.post(
        reverse('requisicoes:enviar_rascunho', kwargs={'pk': req.pk}),
        follow=True,
    )
    assert response.status_code == 200
    msgs = list(response.context['messages'])
    assert any(
        m.level == message_constants.WARNING and 'não é permitida' in str(m)
        for m in msgs
    )


@pytest.mark.django_db
def test_enviar_rascunho_htmx_retorna_hx_redirect(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
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
    response = client.post(
        reverse('requisicoes:enviar_rascunho', kwargs={'pk': req.pk}),
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': req.pk}
    )


@pytest.mark.django_db
def test_detalhe_exibe_botao_enviar_para_criador_em_rascunho(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
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
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert response.context['pode_enviar'] is True
    assert 'Enviar para autorização' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_detalhe_nao_exibe_botao_enviar_em_estado_nao_rascunho(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
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
    req.estado = EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    req.numero_publico = 'REQ-2026-000888'
    req.save(update_fields=['estado', 'numero_publico'])

    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert response.context['pode_enviar'] is False


@pytest.mark.django_db
def test_detalhe_exibe_link_editar_para_criador_em_rascunho(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
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
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert response.context['pode_editar'] is True
    url_editar = reverse('requisicoes:editar_rascunho', kwargs={'pk': req.pk})
    assert url_editar in response.content.decode('utf-8')


@pytest.mark.django_db
def test_detalhe_nao_exibe_link_editar_para_nao_criador(
    client, solicitante, outro_usuario_obras, material_disponivel, setor_obras
):
    """Outro usuário do mesmo setor não vê rascunho de terceiro — nem o link."""
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
    _login(client, outro_usuario_obras)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    # rascunho de terceiro → 404 (selector unifica visibilidade)
    assert response.status_code == 404


@pytest.mark.django_db
def test_detalhe_nao_exibe_link_editar_em_estado_nao_rascunho(
    client, solicitante, material_disponivel
):
    _login(client, solicitante)
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
    req.estado = EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    req.numero_publico = 'REQ-2026-000555'
    req.save(update_fields=['estado', 'numero_publico'])

    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert response.context['pode_editar'] is False
