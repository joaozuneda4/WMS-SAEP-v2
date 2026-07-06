"""Testes de contrato HTTP para views de rascunho (ADR-0010).

Verifica: auth, status codes, redirects, mutations mínimas, presença de messages.
Sem testar HTML detalhado ou texto completo de mensagens.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.requisicoes.models import (
    CancelamentoVariant,
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Requisicao,
    TimelineRequisicao,
)
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


# drift 1: PermissaoNegada no escopo de criação deve virar 403, não messages+redirect
@pytest.mark.django_db
def test_nova_requisicao_permissao_negada_retorna_403(client, solicitante):
    """Drift 1 (canônico): PermissaoNegada em resolver_escopo_criacao_requisicao deve
    retornar 403, nunca messages.error + redirect."""
    from unittest.mock import patch

    from apps.core.exceptions import PermissaoNegada

    _login(client, solicitante)
    with patch(
        'apps.requisicoes.views.resolver_escopo_criacao_requisicao',
        side_effect=PermissaoNegada('Sem papel de solicitante'),
    ):
        resp = client.get(reverse('requisicoes:nova_requisicao'))

    assert resp.status_code == 403


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


# drift 2: EstadoInvalido no editar_rascunho deve ser warning, não error
@pytest.mark.django_db
def test_editar_rascunho_estado_invalido_mostra_warning(
    client, solicitante, rascunho_solicitante, material_disponivel
):
    """Drift 2 (canônico): EstadoInvalido em editar_rascunho deve gerar
    messages.warning, nunca messages.error."""
    from unittest.mock import patch

    from django.contrib.messages import constants as message_constants

    from apps.core.exceptions import EstadoInvalido

    _login(client, solicitante)
    url = reverse('requisicoes:editar_rascunho', kwargs={'pk': rascunho_solicitante.pk})
    with patch(
        'apps.requisicoes.views.editar_rascunho',
        side_effect=EstadoInvalido('Rascunho não pode ser editado neste estado'),
    ):
        resp = client.post(
            url,
            _formset_post(material_disponivel.pk),
            follow=True,
        )

    assert resp.status_code == 200
    msgs = list(resp.context['messages'])
    assert any(m.level == message_constants.WARNING for m in msgs)
    assert not any(m.level == message_constants.ERROR for m in msgs)


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


# opt-out: PermissaoNegada → JsonResponse 403 (não messages+redirect)
@pytest.mark.django_db
def test_buscar_materiais_permissao_negada_retorna_json_403(client, solicitante):
    """Opt-out de buscar_materiais: PermissaoNegada deve retornar JsonResponse 403,
    não redirect com messages (ADR-0011 emenda 2026-06-26)."""
    from unittest.mock import patch

    from apps.core.exceptions import PermissaoNegada

    _login(client, solicitante)
    with patch(
        'apps.requisicoes.views.resolver_escopo_criacao_requisicao',
        side_effect=PermissaoNegada(),
    ):
        resp = client.get(reverse('requisicoes:buscar_materiais'))

    assert resp.status_code == 403
    assert resp['Content-Type'].startswith('application/json')
    assert 'error' in resp.json()


# ---------------------------------------------------------------------------
# buscar_beneficiarios
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_buscar_beneficiarios_sem_login(client):
    resp = client.get(reverse('requisicoes:buscar_beneficiarios'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_buscar_beneficiarios_chefe_setor_retorna_usuarios_do_setor(
    client, chefe_obras, outro_usuario_obras, usuario_ti
):
    _login(client, chefe_obras)
    resp = client.get(reverse('requisicoes:buscar_beneficiarios'), {'q': ''})
    assert resp.status_code == 200
    data = resp.json()
    ids = [r['id'] for r in data['resultados']]
    assert outro_usuario_obras.pk in ids
    assert usuario_ti.pk not in ids


@pytest.mark.django_db
def test_buscar_beneficiarios_filtra_por_nome(client, chefe_obras, outro_usuario_obras):
    _login(client, chefe_obras)
    resp = client.get(reverse('requisicoes:buscar_beneficiarios'), {'q': 'Maria'})
    assert resp.status_code == 200
    data = resp.json()
    nomes = [r['nome'] for r in data['resultados']]
    assert 'Maria Obras' in nomes


@pytest.mark.django_db
def test_buscar_beneficiarios_solicitante_puro_retorna_vazio(client, solicitante):
    _login(client, solicitante)
    resp = client.get(reverse('requisicoes:buscar_beneficiarios'), {'q': ''})
    assert resp.status_code == 200
    data = resp.json()
    assert data['resultados'] == []


@pytest.mark.django_db
def test_buscar_beneficiarios_shape(client, chefe_obras, outro_usuario_obras):
    _login(client, chefe_obras)
    resp = client.get(reverse('requisicoes:buscar_beneficiarios'), {'q': ''})
    assert resp.status_code == 200
    data = resp.json()
    assert 'resultados' in data
    for r in data['resultados']:
        assert 'id' in r
        assert 'nome' in r
        assert 'matricula' in r
        assert 'label' in r


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
def req_enviada_beneficiario(db, solicitante, outro_usuario_obras, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-0012',
        criador=solicitante,
        beneficiario=outro_usuario_obras,
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
    html = response.content.decode('utf-8')
    menu_html = html[
        html.index('aria-label="Navegação"') : html.index('app-bar__menu-divider')
    ]
    assert reverse('requisicoes:minhas') in menu_html
    assert 'aria-current="page"' in menu_html


@pytest.mark.django_db
def test_minhas_exibe_autorizacoes_para_chefe_ativo(client, chefe_obras):
    _login(client, chefe_obras)
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert reverse('requisicoes:autorizacoes') in html


@pytest.mark.django_db
def test_minhas_oculta_autorizacoes_para_chefe_inativo(client, chefe_obras):
    chefe_obras.setor.ativo = False
    chefe_obras.setor.save(update_fields=['ativo'])

    _login(client, chefe_obras)
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert reverse('requisicoes:autorizacoes') not in html


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


# ---------------------------------------------------------------------------
# Fila de autorização, retorno e recusa — TR-006 / TR-011
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fila_autorizacao_sem_login_redireciona(client):
    response = client.get(reverse('requisicoes:autorizacoes'))
    assert response.status_code == 302


@pytest.mark.django_db
def test_fila_autorizacao_chefe_renderiza_apenas_setor(
    client, chefe_obras, req_enviada_solicitante, req_outro_setor_view
):
    _login(client, chefe_obras)
    response = client.get(reverse('requisicoes:autorizacoes'))

    assert response.status_code == 200
    requisicoes = list(response.context['requisicoes'])
    assert req_enviada_solicitante in requisicoes
    assert req_outro_setor_view not in requisicoes
    html = response.content.decode('utf-8')
    assert 'Fila de autorização' in html
    assert 'Analisar' in html
    assert 'Enviada em' in html


@pytest.mark.django_db
def test_fila_autorizacao_superuser_ve_todos_setores(
    client, superuser, req_enviada_solicitante, req_outro_setor_view
):
    _login(client, superuser)
    response = client.get(reverse('requisicoes:autorizacoes'))

    assert response.status_code == 200
    requisicoes = list(response.context['requisicoes'])
    assert req_enviada_solicitante in requisicoes
    assert req_outro_setor_view in requisicoes
    html = response.content.decode('utf-8')
    assert 'Fila de autorização' in html
    assert 'Analisar' in html
    assert 'Enviada em' in html


@pytest.mark.django_db
def test_fila_autorizacao_ator_sem_permissao_retorna_403(client, solicitante):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:autorizacoes'))
    assert response.status_code == 403


@pytest.mark.django_db
def test_retornar_rascunho_post_criador_redireciona_e_muda_estado(
    client, solicitante, req_enviada_solicitante
):
    _login(client, solicitante)
    response = client.post(
        reverse(
            'requisicoes:retornar_rascunho', kwargs={'pk': req_enviada_solicitante.pk}
        ),
        {'observacao': 'Corrigir item.'},
    )

    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk}
    )
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_retornar_rascunho_post_respeita_next_seguro(
    client, outro_usuario_obras, req_enviada_beneficiario
):
    _login(client, outro_usuario_obras)
    response = client.post(
        reverse(
            'requisicoes:retornar_rascunho', kwargs={'pk': req_enviada_beneficiario.pk}
        ),
        {
            'observacao': 'Corrigir item.',
            'next': reverse('requisicoes:minhas'),
        },
    )

    assert response.status_code == 302
    assert response.url == reverse('requisicoes:minhas')
    req_enviada_beneficiario.refresh_from_db()
    assert req_enviada_beneficiario.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_retornar_rascunho_beneficiario_redireciona_e_muda_estado(
    client, outro_usuario_obras, req_enviada_beneficiario
):
    _login(client, outro_usuario_obras)
    response = client.post(
        reverse(
            'requisicoes:retornar_rascunho', kwargs={'pk': req_enviada_beneficiario.pk}
        ),
        {'observacao': 'Corrigir item.'},
    )

    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_beneficiario.pk}
    )
    req_enviada_beneficiario.refresh_from_db()
    assert req_enviada_beneficiario.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_retornar_rascunho_chefe_nao_pode_retornar(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.post(
        reverse(
            'requisicoes:retornar_rascunho', kwargs={'pk': req_enviada_solicitante.pk}
        )
    )
    assert response.status_code == 403
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO


@pytest.mark.django_db
def test_retornar_rascunho_post_superuser_redireciona_e_muda_estado(
    client, superuser, req_enviada_solicitante
):
    _login(client, superuser)
    response = client.post(
        reverse(
            'requisicoes:retornar_rascunho', kwargs={'pk': req_enviada_solicitante.pk}
        ),
        {'observacao': 'Corrigir item.'},
    )

    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk}
    )
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_recusar_requisicao_post_chefe_redireciona_e_muda_estado(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': 'Necessário revisar quantidades.'},
    )

    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk}
    )
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.RECUSADA


@pytest.mark.django_db
def test_recusar_requisicao_post_respeita_next_seguro(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {
            'motivo': 'Necessário revisar quantidades.',
            'next': reverse('requisicoes:autorizacoes'),
        },
    )

    assert response.status_code == 302
    assert response.url == reverse('requisicoes:autorizacoes')
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.RECUSADA


@pytest.mark.django_db
def test_recusar_requisicao_post_superuser_redireciona_e_muda_estado(
    client, superuser, req_enviada_solicitante
):
    _login(client, superuser)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': 'Necessário revisar quantidades.'},
    )

    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk}
    )
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.RECUSADA


@pytest.mark.django_db
def test_recusar_requisicao_sem_motivo_retorna_erro_inline(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': ' '},
    )

    assert response.status_code == 200
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    html = response.content.decode('utf-8')
    assert 'modal-recusar-motivo' in html
    assert 'aria-invalid="true"' in html
    assert 'Informe o motivo da recusa.' in html


@pytest.mark.django_db
def test_recusar_requisicao_sem_motivo_via_htmx_retorna_422_fragment(
    client, chefe_obras, req_enviada_solicitante
):
    """HTMX request com motivo vazio retorna 422 + fragment do modal."""
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': ' '},
        HTTP_HX_REQUEST='true',
    )

    assert response.status_code == 422
    html = response.content.decode('utf-8')
    assert 'data-modal-body="confirmar-recusar"' in html
    assert 'data-modal-erro' in html
    assert 'Informe o motivo da recusa.' in html
    assert 'modal-recusar-motivo' in html
    assert '<!DOCTYPE html>' not in html
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO


@pytest.mark.django_db
def test_recusar_requisicao_sucesso_via_htmx_retorna_hx_redirect(
    client, chefe_obras, req_enviada_solicitante
):
    """HTMX request com motivo válido retorna 204 + HX-Redirect."""
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': 'Sem orçamento aprovado.'},
        HTTP_HX_REQUEST='true',
    )

    assert response.status_code == 204
    assert 'HX-Redirect' in response.headers
    req_enviada_solicitante.refresh_from_db()
    assert req_enviada_solicitante.estado == EstadoRequisicao.RECUSADA


@pytest.mark.django_db
def test_recusar_requisicao_outro_setor_retorna_403(
    client, chefe_almoxarifado, req_enviada_solicitante
):
    _login(client, chefe_almoxarifado)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': 'Não aprovado.'},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_detalhe_exibe_recusa_para_chefe_e_nao_exibe_retorno(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response.context['pode_recusar'] is True
    assert response.context['pode_retornar'] is False
    assert 'Confirmar recusa' in html
    assert 'Confirmar retorno' not in html
    assert 'data-modal-trigger="confirmar-recusar"' in html
    assert 'window.confirm' not in html
    assert html.count('id="decisao-autorizacao-titulo"') == 1


@pytest.mark.django_db
def test_detalhe_exibe_autorizar_para_chefe_e_nao_exibe_para_outro_papel(
    client, chefe_obras, aux_almoxarifado, material_disponivel
):
    from apps.requisicoes.services import enviar_para_autorizacao

    _login(client, chefe_obras)
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    req = enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response.context['pode_autorizar'] is True
    assert 'Autorizar' in html
    assert 'Analisar' not in html

    _login(client, aux_almoxarifado)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response.context['pode_autorizar'] is False
    assert 'Autorizar' not in html
    assert 'Analisar' not in html


@pytest.mark.django_db
def test_autorizar_requisicao_post_chefe_redireciona_e_muda_estado(
    client, chefe_obras, material_disponivel
):
    from apps.requisicoes.services import enviar_para_autorizacao

    _login(client, chefe_obras)
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    req = enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    response = client.post(reverse('requisicoes:autorizar', kwargs={'pk': req.pk}))

    assert response.status_code == 302
    assert response.url == reverse('requisicoes:detalhe', kwargs={'pk': req.pk})
    req.refresh_from_db()
    item = req.itens.get()
    assert req.estado == EstadoRequisicao.AUTORIZADA
    assert item.quantidade_autorizada == item.quantidade_solicitada


@pytest.mark.django_db
def test_autorizar_requisicao_htmx_retorna_hx_redirect(
    client, chefe_obras, material_disponivel
):
    from apps.requisicoes.services import enviar_para_autorizacao

    _login(client, chefe_obras)
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    req = enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    response = client.post(
        reverse('requisicoes:autorizar', kwargs={'pk': req.pk}),
        HTTP_HX_REQUEST='true',
    )

    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': req.pk}
    )


@pytest.mark.django_db
def test_autorizar_requisicao_post_estado_invalido_redireciona(
    client, chefe_obras, material_disponivel
):
    _login(client, chefe_obras)
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )

    response = client.post(reverse('requisicoes:autorizar', kwargs={'pk': req.pk}))

    assert response.status_code == 302
    assert response.url == reverse('requisicoes:detalhe', kwargs={'pk': req.pk})
    req.refresh_from_db()
    assert req.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_autorizar_requisicao_post_sem_permissao_retorna_403(
    client, chefe_almoxarifado, req_enviada_solicitante
):
    _login(client, chefe_almoxarifado)
    response = client.post(
        reverse('requisicoes:autorizar', kwargs={'pk': req_enviada_solicitante.pk})
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_detalhe_exibe_retorno_para_criador_e_nao_exibe_recusa(
    client, solicitante, req_enviada_solicitante
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response.context['pode_retornar'] is True
    assert response.context['pode_recusar'] is False
    assert 'Confirmar retorno' in html
    assert 'Confirmar recusa' not in html


@pytest.mark.django_db
def test_detalhe_autorizar_card_e_modal_tem_copy_diferenciada(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    html = response.content.decode('utf-8')

    modal_copy = (
        'Reserva o saldo necessário para todos os itens sem alterar o saldo físico.'
    )

    assert response.context['pode_autorizar'] is True
    assert html.count(modal_copy) == 1


@pytest.mark.django_db
def test_detalhe_exibe_descartar_rascunho_para_criador_em_rascunho(
    client, solicitante, rascunho_solicitante
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': rascunho_solicitante.pk})
    )
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response.context['pode_cancelar'] is True
    assert (
        response.context['cancelamento_info'].variante == CancelamentoVariant.DESCARTE
    )
    assert response.context['cancelamento_requer_justificativa'] is False
    assert 'role="dialog"' in html
    assert 'Descartar rascunho' in html


@pytest.mark.django_db
def test_detalhe_exibe_cancelar_com_justificativa_para_autorizada(
    client, solicitante, req_autorizada_view
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_autorizada_view.pk})
    )
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response.context['pode_cancelar'] is True
    assert (
        response.context['cancelamento_info'].variante
        == CancelamentoVariant.CANCELAMENTO
    )
    assert response.context['cancelamento_requer_justificativa'] is True
    assert 'Justificativa do cancelamento' in html
    assert 'role="dialog"' in html


@pytest.mark.django_db
def test_descartar_rascunho_post_redireciona_para_lista(
    client, solicitante, rascunho_solicitante
):
    _login(client, solicitante)
    response = client.post(
        reverse('requisicoes:cancelar', kwargs={'pk': rascunho_solicitante.pk})
    )

    assert response.status_code == 302
    assert response.url == reverse('requisicoes:minhas')
    assert not Requisicao.objects.filter(pk=rascunho_solicitante.pk).exists()


@pytest.mark.django_db
def test_cancelar_requisicao_post_autorizada_sem_justificativa_renderiza_modal_com_erro(
    client, solicitante, req_autorizada_view
):
    _login(client, solicitante)
    response = client.post(
        reverse('requisicoes:cancelar', kwargs={'pk': req_autorizada_view.pk}),
        {'justificativa': ' '},
    )

    assert response.status_code == 200
    assert response.context['cancelamento_modal_aberto'] is True
    assert (
        response.context['cancelamento_erro']
        == 'Informe a justificativa do cancelamento.'
    )
    assert response.context['cancelamento_requer_justificativa'] is True
    req_autorizada_view.refresh_from_db()
    assert req_autorizada_view.estado == EstadoRequisicao.AUTORIZADA
    html = response.content.decode('utf-8')
    assert 'modal-cancelar-justificativa' in html
    assert 'aria-invalid="true"' in html


@pytest.mark.django_db
def test_cancelar_requisicao_sem_justificativa_via_htmx_retorna_422_fragment(
    client, solicitante, req_autorizada_view
):
    """HTMX request com justificativa vazia em autorizada retorna 422 + fragment."""
    _login(client, solicitante)
    response = client.post(
        reverse('requisicoes:cancelar', kwargs={'pk': req_autorizada_view.pk}),
        {'justificativa': ' '},
        HTTP_HX_REQUEST='true',
    )

    assert response.status_code == 422
    html = response.content.decode('utf-8')
    assert 'data-modal-body="confirmar-cancelar"' in html
    assert 'data-modal-erro' in html
    assert 'Informe a justificativa do cancelamento.' in html
    assert 'modal-cancelar-justificativa' in html
    assert '<!DOCTYPE html>' not in html
    req_autorizada_view.refresh_from_db()
    assert req_autorizada_view.estado == EstadoRequisicao.AUTORIZADA


@pytest.mark.django_db
def test_cancelar_requisicao_post_autorizada_403_para_nao_autorizado(
    client, chefe_obras, req_autorizada_view
):
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:cancelar', kwargs={'pk': req_autorizada_view.pk})
    )

    assert response.status_code == 403
    req_autorizada_view.refresh_from_db()
    assert req_autorizada_view.estado == EstadoRequisicao.AUTORIZADA
    assert req_autorizada_view.numero_publico == 'REQ-2026-9001'


@pytest.mark.django_db
def test_cancelar_requisicao_post_autorizada_redireciona_e_muda_estado(
    client, solicitante, chefe_obras, material_disponivel
):
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
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    req = enviar_para_autorizacao(
        ator_id=solicitante.pk,
        requisicao_id=req.pk,
    )
    req = autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=req.pk,
    )

    _login(client, solicitante)
    response = client.post(
        reverse('requisicoes:cancelar', kwargs={'pk': req.pk}),
        {'justificativa': 'Revisão interna do pedido.'},
    )

    assert response.status_code == 302
    assert response.url == reverse('requisicoes:detalhe', kwargs={'pk': req.pk})
    req.refresh_from_db()
    assert req.estado == EstadoRequisicao.CANCELADA


@pytest.mark.django_db
def test_recusar_requisicao_htmx_retorna_hx_redirect(
    client, chefe_obras, req_enviada_solicitante
):
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': 'Não aprovado.'},
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk}
    )


@pytest.mark.django_db
def test_recusar_requisicao_htmx_superuser_retorna_hx_redirect(
    client, superuser, req_enviada_solicitante
):
    _login(client, superuser)
    response = client.post(
        reverse('requisicoes:recusar', kwargs={'pk': req_enviada_solicitante.pk}),
        {'motivo': 'Não aprovado.'},
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk}
    )


# ---------------------------------------------------------------------------
# Fila de atendimento + separar para retirada (TR-009)
# ---------------------------------------------------------------------------


@pytest.fixture
def req_autorizada_view(db, solicitante, setor_obras, material_disponivel):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2026-9001',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=1,
        quantidade_autorizada=1,
    )
    return req


@pytest.fixture
def req_pronta_view(db, solicitante, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.PRONTA_PARA_RETIRADA,
        numero_publico='REQ-2026-9002',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.mark.django_db
def test_fila_atendimento_sem_login_redireciona(client):
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 302
    assert response.url.startswith(reverse('accounts:login'))


@pytest.mark.django_db
def test_fila_atendimento_aux_almox_renderiza_autorizada_e_pronta(
    client, aux_almoxarifado, req_autorizada_view, req_pronta_view
):
    _login(client, aux_almoxarifado)
    response = client.get(reverse('requisicoes:atendimentos'))

    assert response.status_code == 200
    requisicoes = list(response.context['requisicoes'])
    assert req_autorizada_view in requisicoes
    assert req_pronta_view in requisicoes
    html = response.content.decode('utf-8')
    assert 'Fila de atendimento' in html
    assert 'Atender' in html


@pytest.mark.django_db
def test_fila_atendimento_chefe_almox_200(
    client, chefe_almoxarifado, req_autorizada_view
):
    _login(client, chefe_almoxarifado)
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 200
    assert req_autorizada_view in list(response.context['requisicoes'])


@pytest.mark.django_db
def test_fila_atendimento_superuser_200(
    client, superuser, req_autorizada_view, req_pronta_view
):
    _login(client, superuser)
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 200
    requisicoes = list(response.context['requisicoes'])
    assert req_autorizada_view in requisicoes
    assert req_pronta_view in requisicoes


@pytest.mark.django_db
def test_fila_atendimento_chefe_setor_403(client, chefe_obras):
    _login(client, chefe_obras)
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 403


@pytest.mark.django_db
def test_fila_atendimento_solicitante_403(client, solicitante):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 403


@pytest.mark.django_db
def test_fila_atendimento_vazia_renderiza_empty_state(client, aux_almoxarifado):
    _login(client, aux_almoxarifado)
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Nenhuma requisição aguardando atendimento' in html


@pytest.mark.django_db
def test_separar_retirada_post_aux_almox_redireciona_e_muda_estado(
    client, aux_almoxarifado, req_autorizada_view
):
    _login(client, aux_almoxarifado)
    response = client.post(
        reverse('requisicoes:separar_retirada', kwargs={'pk': req_autorizada_view.pk})
    )

    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_autorizada_view.pk}
    )
    req_autorizada_view.refresh_from_db()
    assert req_autorizada_view.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA


@pytest.mark.django_db
def test_separar_retirada_post_mensagem_sucesso_com_numero(
    client, aux_almoxarifado, req_autorizada_view
):
    _login(client, aux_almoxarifado)
    response = client.post(
        reverse('requisicoes:separar_retirada', kwargs={'pk': req_autorizada_view.pk}),
        follow=True,
    )

    mensagens = [str(m) for m in response.context['messages']]
    assert any('REQ-2026-9001' in m and 'pronta para retirada' in m for m in mensagens)


@pytest.mark.django_db
def test_separar_retirada_htmx_retorna_hx_redirect(
    client, aux_almoxarifado, req_autorizada_view
):
    _login(client, aux_almoxarifado)
    response = client.post(
        reverse('requisicoes:separar_retirada', kwargs={'pk': req_autorizada_view.pk}),
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_autorizada_view.pk}
    )


@pytest.mark.django_db
def test_separar_retirada_get_retorna_405(
    client, aux_almoxarifado, req_autorizada_view
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:separar_retirada', kwargs={'pk': req_autorizada_view.pk})
    )
    assert response.status_code == 405


@pytest.mark.django_db
def test_separar_retirada_chefe_setor_403(client, chefe_obras, req_autorizada_view):
    _login(client, chefe_obras)
    response = client.post(
        reverse('requisicoes:separar_retirada', kwargs={'pk': req_autorizada_view.pk})
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_separar_retirada_estado_invalido_avisa(
    client, aux_almoxarifado, req_pronta_view
):
    _login(client, aux_almoxarifado)
    url = reverse('requisicoes:separar_retirada', kwargs={'pk': req_pronta_view.pk})
    # PRG: sem follow, deve retornar 302 para o detalhe
    response = client.post(url)
    assert response.status_code == 302
    assert response.url == reverse('requisicoes:detalhe', args=[req_pronta_view.pk])
    # Follow e verificar mensagem de warning com texto do EstadoInvalido
    response = client.post(url, follow=True)
    assert response.status_code == 200
    messages_list = list(response.context['messages'])
    assert any('warning' in m.tags and 'autorizada' in m.message for m in messages_list)


@pytest.mark.django_db
def test_separar_retirada_rascunho_404_pois_fora_de_escopo(
    client, aux_almoxarifado, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        numero_publico=None,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    _login(client, aux_almoxarifado)
    response = client.post(
        reverse('requisicoes:separar_retirada', kwargs={'pk': req.pk})
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_detalhe_exibe_botao_separar_para_aux_almox(
    client, aux_almoxarifado, req_autorizada_view
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_autorizada_view.pk})
    )
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Separar para retirada' in html
    assert response.context['pode_separar_retirada'] is True


@pytest.mark.django_db
def test_detalhe_nao_exibe_botao_separar_para_solicitante(
    client, solicitante, req_autorizada_view
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_autorizada_view.pk})
    )
    assert response.status_code == 200
    assert response.context['pode_separar_retirada'] is False
    html = response.content.decode('utf-8')
    assert 'Separar para retirada' not in html


@pytest.mark.django_db
def test_topbar_exibe_link_atendimento_para_almox(client, aux_almoxarifado):
    _login(client, aux_almoxarifado)
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Atendimento' in html


@pytest.mark.django_db
def test_topbar_nao_exibe_link_atendimento_para_solicitante(client, solicitante):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:minhas'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Fila de Atendimento' not in html


# ---------------------------------------------------------------------------
# registrar_atendimento_view (TR-016/017/018)
# ---------------------------------------------------------------------------


@pytest.fixture
def req_pronta_view_com_itens(db, solicitante, setor_obras, material_disponivel):
    from apps.estoque.models import SaldoEstoque

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.PRONTA_PARA_RETIRADA,
        numero_publico='REQ-2026-9100',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=Decimal('2'),
        quantidade_autorizada=Decimal('2'),
    )
    saldo = SaldoEstoque.objects.get(material=material_disponivel)
    saldo.saldo_reservado = (saldo.saldo_reservado or 0) + Decimal('2')
    saldo.save(update_fields=['saldo_reservado'])
    return req


def _post_atendimento(
    client, req, *, entregue, justificativa='', retirante='Carlos', observacao=''
):
    item = req.itens.first()
    return client.post(
        reverse('requisicoes:registrar_atendimento', kwargs={'pk': req.pk}),
        data={
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '1',
            'itens-MIN_NUM_FORMS': '0',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-item_id': str(item.id),
            'itens-0-quantidade_entregue': str(entregue),
            'itens-0-justificativa': justificativa,
            'retirante_nome': retirante,
            'observacao': observacao,
        },
    )


@pytest.mark.django_db
def test_atender_get_sem_login_redireciona(client, req_pronta_view_com_itens):
    response = client.get(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        )
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_atender_get_aux_almox_renderiza_form(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        )
    )
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Registrar atendimento' in html
    assert 'Retirante' in html


@pytest.mark.django_db
def test_atender_get_prepreenche_quantidade_decimal_com_ponto(
    client, aux_almoxarifado, solicitante, setor_obras, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.PRONTA_PARA_RETIRADA,
        numero_publico='REQ-2026-9101',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=Decimal('5.500'),
        quantidade_autorizada=Decimal('5.500'),
    )
    saldo = SaldoEstoque.objects.get(material=material_disponivel)
    saldo.saldo_reservado = (saldo.saldo_reservado or 0) + Decimal('5.500')
    saldo.save(update_fields=['saldo_reservado'])

    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:registrar_atendimento', kwargs={'pk': req.pk})
    )
    html = response.content.decode('utf-8')
    assert 'value="5.500"' in html
    assert 'value="5,500"' not in html


@pytest.mark.django_db
def test_atender_get_solicitante_403(client, solicitante, req_pronta_view_com_itens):
    _login(client, solicitante)
    response = client.get(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        )
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_atender_post_total_redireciona_e_muda_estado(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = _post_atendimento(
        client, req_pronta_view_com_itens, entregue=Decimal('2')
    )
    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_pronta_view_com_itens.pk}
    )
    req_pronta_view_com_itens.refresh_from_db()
    assert req_pronta_view_com_itens.estado == EstadoRequisicao.ATENDIDA


@pytest.mark.django_db
def test_atender_post_total_mensagem_sucesso(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = _post_atendimento(
        client, req_pronta_view_com_itens, entregue=Decimal('2')
    )
    response = client.get(response.url)
    mensagens = [str(m) for m in response.context['messages']]
    assert any(
        'REQ-2026-9100' in m and 'registrada com sucesso' in m for m in mensagens
    )


@pytest.mark.django_db
def test_atender_post_parcial_com_justificativa_ok(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = _post_atendimento(
        client,
        req_pronta_view_com_itens,
        entregue=Decimal('1'),
        justificativa='Falta de material no carrinho.',
    )
    assert response.status_code == 302
    req_pronta_view_com_itens.refresh_from_db()
    assert req_pronta_view_com_itens.estado == EstadoRequisicao.ATENDIDA


@pytest.mark.django_db
def test_atender_post_sem_entrega_avisa(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = _post_atendimento(
        client,
        req_pronta_view_com_itens,
        entregue=Decimal('0'),
        justificativa='Não compareceu',
    )
    assert response.status_code == 302
    req_pronta_view_com_itens.refresh_from_db()
    assert req_pronta_view_com_itens.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA
    response = client.get(response.url)
    mensagens = [str(m) for m in response.context['messages']]
    assert any('entregue maior que zero' in m for m in mensagens)


@pytest.mark.django_db
def test_atender_post_estado_origem_invalido_avisa(
    client, aux_almoxarifado, req_autorizada_view
):
    _login(client, aux_almoxarifado)
    response = client.post(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_autorizada_view.pk},
        ),
        data={
            'itens-TOTAL_FORMS': '0',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '0',
            'itens-MAX_NUM_FORMS': '1000',
            'retirante_nome': 'X',
        },
    )
    assert response.status_code == 302
    assert response.url == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_autorizada_view.pk}
    )


@pytest.mark.django_db
def test_atender_post_chefe_setor_403(client, chefe_obras, req_pronta_view_com_itens):
    _login(client, chefe_obras)
    response = client.post(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        ),
        data={
            'itens-TOTAL_FORMS': '0',
            'itens-INITIAL_FORMS': '0',
            'itens-MIN_NUM_FORMS': '0',
            'itens-MAX_NUM_FORMS': '1000',
            'retirante_nome': 'X',
        },
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_atender_post_form_invalido_renderiza_400(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    """Retirante vazio dispara cabecalho.is_valid()=False."""
    _login(client, aux_almoxarifado)
    item = req_pronta_view_com_itens.itens.first()
    response = client.post(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        ),
        data={
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '1',
            'itens-MIN_NUM_FORMS': '0',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-item_id': str(item.id),
            'itens-0-quantidade_entregue': '2',
            'itens-0-justificativa': '',
            'retirante_nome': '',
        },
    )
    assert response.status_code == 400
    html = response.content.decode('utf-8')
    assert 'Corrija os campos destacados' in html or 'obrigatório' in html.lower()


@pytest.mark.django_db
def test_atender_post_htmx_retorna_hx_redirect(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    item = req_pronta_view_com_itens.itens.first()
    response = client.post(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        ),
        data={
            'itens-TOTAL_FORMS': '1',
            'itens-INITIAL_FORMS': '1',
            'itens-MIN_NUM_FORMS': '0',
            'itens-MAX_NUM_FORMS': '1000',
            'itens-0-item_id': str(item.id),
            'itens-0-quantidade_entregue': '2',
            'itens-0-justificativa': '',
            'retirante_nome': 'Carlos',
            'observacao': '',
        },
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', kwargs={'pk': req_pronta_view_com_itens.pk}
    )


@pytest.mark.django_db
def test_detalhe_exibe_botao_registrar_retirada_para_aux_almox(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_pronta_view_com_itens.pk})
    )
    assert response.status_code == 200
    assert response.context['pode_atender_retirada'] is True
    html = response.content.decode('utf-8')
    assert 'Registrar retirada' in html


@pytest.mark.django_db
def test_detalhe_nao_exibe_botao_registrar_retirada_para_solicitante(
    client, solicitante, req_pronta_view_com_itens
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_pronta_view_com_itens.pk})
    )
    assert response.status_code == 200
    assert response.context['pode_atender_retirada'] is False
    html = response.content.decode('utf-8')
    assert 'Registrar retirada' not in html


# ---------------------------------------------------------------------------
# Issue #9 — Cabeçalho, colunas de data, botão primário, a11y (Batch D)
# ---------------------------------------------------------------------------


@pytest.fixture
def req_enviada_com_timeline(db, solicitante, setor_obras):
    """Requisição em aguardando_autorizacao com evento ENVIO_AUTORIZACAO na timeline."""
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-D001',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    TimelineRequisicao.objects.create(
        requisicao=req,
        evento=EventoTimeline.ENVIO_AUTORIZACAO,
        ator=solicitante,
        estado_resultante=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
    )
    return req


@pytest.fixture
def req_autorizada_com_timeline(db, solicitante, setor_obras, material_disponivel):
    """Requisição autorizada com eventos ENVIO_AUTORIZACAO e AUTORIZACAO_TOTAL."""
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2026-D002',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=1,
        quantidade_autorizada=1,
    )
    TimelineRequisicao.objects.create(
        requisicao=req,
        evento=EventoTimeline.ENVIO_AUTORIZACAO,
        ator=solicitante,
        estado_resultante=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
    )
    TimelineRequisicao.objects.create(
        requisicao=req,
        evento=EventoTimeline.AUTORIZACAO_TOTAL,
        ator=solicitante,
        estado_resultante=EstadoRequisicao.AUTORIZADA,
    )
    return req


@pytest.mark.django_db
def test_detalhe_exibe_enviada_em_em_aguardando_autorizacao(
    client, solicitante, req_enviada_com_timeline
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_com_timeline.pk})
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_detalhe_nao_exibe_enviada_em_em_rascunho(client, solicitante, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert response.context['enviada_em'] is None


@pytest.mark.django_db
def test_detalhe_nao_exibe_enviada_em_em_rascunho_retornado(
    client, solicitante, setor_obras
):
    """Rascunho com ENVIO_AUTORIZACAO na timeline (enviado e retornado) não exibe 'Enviada em'."""
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        numero_publico='REQ-2026-D099',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    TimelineRequisicao.objects.create(
        requisicao=req,
        evento=EventoTimeline.ENVIO_AUTORIZACAO,
        ator=solicitante,
        estado_resultante=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
    )
    TimelineRequisicao.objects.create(
        requisicao=req,
        evento=EventoTimeline.RETORNO_RASCUNHO,
        ator=solicitante,
        estado_resultante=EstadoRequisicao.RASCUNHO,
    )
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert response.context['enviada_em'] is None


@pytest.mark.django_db
def test_detalhe_titulo_rascunho_sem_pk(client, solicitante, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Rascunho' in html
    assert f'Rascunho #{req.pk}' not in html


@pytest.mark.django_db
def test_fila_autorizacao_coluna_enviada_em(
    client, chefe_obras, req_enviada_com_timeline
):
    _login(client, chefe_obras)
    response = client.get(reverse('requisicoes:autorizacoes'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Enviada em' in html
    assert 'Atualizada em' not in html


@pytest.mark.django_db
def test_fila_atendimento_coluna_autorizada_em(
    client, aux_almoxarifado, req_autorizada_com_timeline
):
    _login(client, aux_almoxarifado)
    response = client.get(reverse('requisicoes:atendimentos'))
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'Autorizada em' in html
    assert 'Atualizada em' not in html


@pytest.mark.django_db
def test_detalhe_registrar_retirada_botao_azul(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_pronta_view_com_itens.pk})
    )
    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'bg-blue-600' in html
    assert 'bg-emerald-600' not in html


def test_messages_html_aria_live_containers():
    """Partial _messages.html renderiza containers aria-live por nível de mensagem."""
    from django.contrib import messages as django_messages
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.template.loader import render_to_string
    from django.test import RequestFactory

    rf = RequestFactory()
    request = rf.get('/')
    request.session = {}
    storage = FallbackStorage(request)
    request._messages = storage
    django_messages.error(request, 'Erro de teste')
    django_messages.success(request, 'Sucesso de teste')

    html = render_to_string('core/partials/_messages.html', request=request)
    assert 'aria-live="assertive"' in html
    assert 'aria-live="polite"' in html
    assert 'Erro de teste' in html
    assert 'Sucesso de teste' in html


# ---------------------------------------------------------------------------
# copiar_requisicao_view
# ---------------------------------------------------------------------------


@pytest.fixture
def req_recusada_view(solicitante, material_disponivel, chefe_obras):
    from apps.requisicoes.services import enviar_para_autorizacao, recusar_requisicao

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
    req = enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)
    return recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=req.pk,
        motivo='Sem orçamento.',
    )


@pytest.mark.django_db
def test_copiar_requisicao_view_get_retorna_confirmacao(
    client, solicitante, req_recusada_view
):
    _login(client, solicitante)
    url = reverse('requisicoes:copiar', kwargs={'pk': req_recusada_view.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_copiar_requisicao_view_post_cria_rascunho_e_redireciona(
    client, solicitante, req_recusada_view
):
    from django.urls import resolve

    _login(client, solicitante)
    url = reverse('requisicoes:copiar', kwargs={'pk': req_recusada_view.pk})
    response = client.post(url, follow=True)

    assert response.redirect_chain
    redirect_url = response.redirect_chain[0][0]
    novo_pk = resolve(redirect_url).kwargs['pk']
    novo = Requisicao.objects.get(pk=novo_pk)
    assert novo.estado == EstadoRequisicao.RASCUNHO
    assert novo.itens.count() == req_recusada_view.itens.count()
    mensagens = [str(m) for m in response.context['messages']]
    assert any('Rascunho criado' in m for m in mensagens)


@pytest.mark.django_db
def test_copiar_requisicao_view_post_sem_login_redireciona(client, req_recusada_view):
    url = reverse('requisicoes:copiar', kwargs={'pk': req_recusada_view.pk})
    response = client.post(url)
    assert response.status_code == 302
    assert '/login/' in response['Location'] or 'next=' in response['Location']


@pytest.mark.django_db
def test_copiar_requisicao_view_post_estado_invalido_exibe_erro(
    client, solicitante, material_disponivel
):
    req_rascunho = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    _login(client, solicitante)
    url = reverse('requisicoes:copiar', kwargs={'pk': req_rascunho.pk})
    response = client.post(url)
    assert response.status_code == 200
    mensagens = [str(m) for m in response.context['messages']]
    assert any('atendidas ou recusadas' in m for m in mensagens)


# drift 3a: PermissaoNegada em copiar deve virar 403, não messages.error
@pytest.mark.django_db
def test_copiar_requisicao_view_permissao_negada_retorna_403(
    client, solicitante, material_disponivel
):
    """Drift 3a (canônico): PermissaoNegada em copiar_requisicao deve retornar 403."""
    from unittest.mock import patch

    from apps.core.exceptions import PermissaoNegada

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
    _login(client, solicitante)
    with patch(
        'apps.requisicoes.views.copiar_requisicao',
        side_effect=PermissaoNegada('Sem permissão'),
    ):
        resp = client.post(reverse('requisicoes:copiar', kwargs={'pk': req.pk}))

    assert resp.status_code == 403


# drift 3b: EstadoInvalido em copiar deve ser warning, não error
@pytest.mark.django_db
def test_copiar_requisicao_view_estado_invalido_mostra_warning(
    client, solicitante, material_disponivel
):
    """Drift 3b (canônico): EstadoInvalido em copiar_requisicao deve gerar
    messages.warning, nunca messages.error."""
    from unittest.mock import patch

    from django.contrib.messages import constants as message_constants

    from apps.core.exceptions import EstadoInvalido

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
    _login(client, solicitante)
    with patch(
        'apps.requisicoes.views.copiar_requisicao',
        side_effect=EstadoInvalido('Estado inválido para cópia'),
    ):
        resp = client.post(
            reverse('requisicoes:copiar', kwargs={'pk': req.pk}),
            follow=True,
        )

    assert resp.status_code == 200
    msgs = list(resp.context['messages'])
    assert any(m.level == message_constants.WARNING for m in msgs)
    assert not any(m.level == message_constants.ERROR for m in msgs)


# ---------------------------------------------------------------------------
# registrar_devolucao_view (TR-020)
# ---------------------------------------------------------------------------


@pytest.fixture
def req_atendida_view(
    db, solicitante, setor_obras, material_disponivel, aux_almoxarifado
):
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.services import registrar_atendimento
    from apps.requisicoes.types import LinhaAtendimento

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.PRONTA_PARA_RETIRADA,
        numero_publico='REQ-2026-9200',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    item = ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=Decimal('5'),
        quantidade_autorizada=Decimal('5'),
    )
    saldo = SaldoEstoque.objects.get(material=material_disponivel)
    saldo.saldo_reservado = (saldo.saldo_reservado or Decimal('0')) + Decimal('5')
    saldo.save(update_fields=['saldo_reservado'])
    return registrar_atendimento(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=req.pk,
        itens=[
            LinhaAtendimento(
                item_id=item.pk,
                quantidade_entregue=Decimal('5'),
                justificativa='',
            )
        ],
        retirante_nome='Carlos',
    )


@pytest.mark.django_db
def test_registrar_devolucao_view_post_valido_redireciona(
    client, aux_almoxarifado, req_atendida_view
):
    _login(client, aux_almoxarifado)
    item = req_atendida_view.itens.first()
    url = reverse(
        'requisicoes:registrar_devolucao',
        kwargs={'pk': req_atendida_view.pk, 'item_pk': item.pk},
    )
    response = client.post(url, {'quantidade': '1.000'}, follow=True)
    assert response.status_code == 200
    mensagens = [str(m) for m in response.context['messages']]
    assert any('sucesso' in m.lower() for m in mensagens)


@pytest.mark.django_db
def test_registrar_devolucao_view_htmx_retorna_hx_redirect(
    client, aux_almoxarifado, req_atendida_view
):
    _login(client, aux_almoxarifado)
    item = req_atendida_view.itens.first()
    url = reverse(
        'requisicoes:registrar_devolucao',
        kwargs={'pk': req_atendida_view.pk, 'item_pk': item.pk},
    )
    response = client.post(url, {'quantidade': '1.000'}, HTTP_HX_REQUEST='true')
    assert response.status_code == 204
    assert response['HX-Redirect'] == reverse(
        'requisicoes:detalhe', args=[req_atendida_view.pk]
    )


@pytest.mark.django_db
def test_registrar_devolucao_view_quantidade_excede_avisa(
    client, aux_almoxarifado, req_atendida_view
):
    _login(client, aux_almoxarifado)
    item = req_atendida_view.itens.first()
    url = reverse(
        'requisicoes:registrar_devolucao',
        kwargs={'pk': req_atendida_view.pk, 'item_pk': item.pk},
    )
    response = client.post(url, {'quantidade': '999.000'}, follow=True)
    mensagens = [str(m) for m in response.context['messages']]
    assert any('excede' in m for m in mensagens)


# drift 4: DadosInvalidos em devolucao deve ser error, não warning
@pytest.mark.django_db
def test_registrar_devolucao_view_dados_invalidos_mostra_error(
    client, aux_almoxarifado, req_atendida_view
):
    """Drift 4 (canônico): DadosInvalidos em registrar_devolucao deve gerar
    messages.error, nunca messages.warning."""
    from unittest.mock import patch

    from django.contrib.messages import constants as message_constants

    from apps.core.exceptions import DadosInvalidos

    _login(client, aux_almoxarifado)
    item = req_atendida_view.itens.first()
    url = reverse(
        'requisicoes:registrar_devolucao',
        kwargs={'pk': req_atendida_view.pk, 'item_pk': item.pk},
    )
    with patch(
        'apps.requisicoes.views.registrar_devolucao',
        side_effect=DadosInvalidos('Quantidade inválida'),
    ):
        resp = client.post(url, {'quantidade': '1.000'}, follow=True)

    assert resp.status_code == 200
    msgs = list(resp.context['messages'])
    assert any(m.level == message_constants.ERROR for m in msgs)
    assert not any(m.level == message_constants.WARNING for m in msgs)


@pytest.mark.django_db
def test_registrar_devolucao_view_sem_permissao_403(
    client, solicitante, req_atendida_view
):
    _login(client, solicitante)
    item = req_atendida_view.itens.first()
    url = reverse(
        'requisicoes:registrar_devolucao',
        kwargs={'pk': req_atendida_view.pk, 'item_pk': item.pk},
    )
    response = client.post(url, {'quantidade': '1.000'})
    assert response.status_code == 403


@pytest.mark.django_db
def test_registrar_devolucao_view_get_retorna_405(
    client, aux_almoxarifado, req_atendida_view
):
    _login(client, aux_almoxarifado)
    item = req_atendida_view.itens.first()
    url = reverse(
        'requisicoes:registrar_devolucao',
        kwargs={'pk': req_atendida_view.pk, 'item_pk': item.pk},
    )
    response = client.get(url)
    assert response.status_code == 405


# ---------------------------------------------------------------------------
# estornar_requisicao_view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_estornar_view_sucesso_redireciona(
    client, chefe_almoxarifado, req_atendida_view
):
    """POST válido → redirect para detalhe + mensagem success."""
    _login(client, chefe_almoxarifado)
    url = reverse('requisicoes:estornar', kwargs={'pk': req_atendida_view.pk})
    response = client.post(url, {'justificativa': 'Estorno por teste.'})
    assert response.status_code == 302
    assert response['Location'] == reverse(
        'requisicoes:detalhe', args=[req_atendida_view.pk]
    )
    req_atendida_view.refresh_from_db()
    assert req_atendida_view.estado == EstadoRequisicao.ESTORNADA


@pytest.mark.django_db
def test_estornar_view_htmx_retorna_hx_redirect(
    client, chefe_almoxarifado, req_atendida_view
):
    """HTMX POST → 204 + HX-Redirect."""
    _login(client, chefe_almoxarifado)
    url = reverse('requisicoes:estornar', kwargs={'pk': req_atendida_view.pk})
    response = client.post(
        url,
        {'justificativa': 'Estorno HTMX.'},
        HTTP_HX_REQUEST='true',
    )
    assert response.status_code == 204
    assert 'HX-Redirect' in response


@pytest.mark.django_db
def test_estornar_view_sem_justificativa_exibe_warning(
    client, chefe_almoxarifado, req_atendida_view
):
    """POST sem justificativa → redirect + mensagem warning (form inválido)."""
    _login(client, chefe_almoxarifado)
    url = reverse('requisicoes:estornar', kwargs={'pk': req_atendida_view.pk})
    response = client.post(url, {'justificativa': ''}, follow=True)
    assert response.status_code == 200
    msgs = [str(m) for m in response.context['messages']]
    assert any('justificativa' in m.lower() or 'obrigat' in m.lower() for m in msgs)
    req_atendida_view.refresh_from_db()
    assert req_atendida_view.estado == EstadoRequisicao.ATENDIDA


# drift 5: DadosInvalidos em estorno deve ser error, não warning
@pytest.mark.django_db
def test_estornar_view_dados_invalidos_mostra_error(
    client, chefe_almoxarifado, req_atendida_view
):
    """Drift 5 (canônico): DadosInvalidos em estornar_requisicao deve gerar
    messages.error, nunca messages.warning."""
    from unittest.mock import patch

    from django.contrib.messages import constants as message_constants

    from apps.core.exceptions import DadosInvalidos

    _login(client, chefe_almoxarifado)
    url = reverse('requisicoes:estornar', kwargs={'pk': req_atendida_view.pk})
    with patch(
        'apps.requisicoes.views.estornar_requisicao',
        side_effect=DadosInvalidos('Justificativa insuficiente'),
    ):
        resp = client.post(url, {'justificativa': 'motivo'}, follow=True)

    assert resp.status_code == 200
    msgs = list(resp.context['messages'])
    assert any(m.level == message_constants.ERROR for m in msgs)
    assert not any(m.level == message_constants.WARNING for m in msgs)


@pytest.mark.django_db
def test_estornar_view_sem_permissao_retorna_403(
    client, aux_almoxarifado, req_atendida_view
):
    """Auxiliar almox → 403."""
    _login(client, aux_almoxarifado)
    url = reverse('requisicoes:estornar', kwargs={'pk': req_atendida_view.pk})
    response = client.post(url, {'justificativa': 'Tentativa.'})
    assert response.status_code == 403


@pytest.mark.django_db
def test_estornar_view_get_nao_permitido(client, chefe_almoxarifado, req_atendida_view):
    """GET → 405."""
    _login(client, chefe_almoxarifado)
    url = reverse('requisicoes:estornar', kwargs={'pk': req_atendida_view.pk})
    response = client.get(url)
    assert response.status_code == 405


# ---------------------------------------------------------------------------
# historico_requisicoes_view
# ---------------------------------------------------------------------------

URL_HISTORICO_REQUISICOES = reverse('requisicoes:historico')


class TestHistoricoRequisicoesView:
    def test_chefe_almox_acessa(self, client, chefe_almoxarifado):
        _login(client, chefe_almoxarifado)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200

    def test_superuser_acessa(self, client, superuser):
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200

    def test_chefe_setor_acessa(self, client, chefe_obras):
        _login(client, chefe_obras)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200

    def test_solicitante_recebe_403(self, client, solicitante):
        _login(client, solicitante)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_contexto_tem_page_obj(self, client, superuser):
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert 'page_obj' in response.context

    def test_view_alimenta_page_obj_com_selector_escopado(
        self, client, chefe_obras, req_historico_obras, req_historico_ti
    ):
        from apps.requisicoes.selectors import historico_requisicoes_visiveis_para

        _login(client, chefe_obras)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200
        assert 'requisicoes/historico_requisicoes.html' in {
            t.name for t in response.templates
        }
        esperado = historico_requisicoes_visiveis_para(chefe_obras.pk).count()
        assert response.context['page_obj'].paginator.count == esperado

    def test_paginacao_server_side(self, client, superuser, setor_obras, solicitante):
        for i in range(30):
            Requisicao.objects.create(
                estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
                numero_publico=f'REQ-2026-1{i:03d}',
                criador=solicitante,
                beneficiario=solicitante,
                setor_beneficiario=setor_obras,
            )
        _login(client, superuser)
        page1 = client.get(URL_HISTORICO_REQUISICOES)
        assert len(page1.context['page_obj'].object_list) == 25
        assert page1.context['page_obj'].has_next() is True
        page2 = client.get(URL_HISTORICO_REQUISICOES, {'page': 2})
        assert page2.status_code == 200
        assert len(page2.context['page_obj'].object_list) >= 1

    def test_empty_state_quando_historico_vazio(self, client, chefe_almoxarifado):
        _login(client, chefe_almoxarifado)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.context['page_obj'].paginator.count == 0
        assert b'Nenhuma requisi' in response.content

    def test_rascunho_de_terceiro_nao_expoe_pk_para_superuser(
        self, client, superuser, solicitante, setor_obras
    ):
        rascunho = Requisicao.objects.create(
            estado=EstadoRequisicao.RASCUNHO,
            criador=solicitante,
            beneficiario=solicitante,
            setor_beneficiario=setor_obras,
        )
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert f'#{rascunho.pk}'.encode() not in response.content
        assert b'Rascunho' in response.content

    def test_requisicao_htmx_devolve_so_partial(self, client, superuser):
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES, HTTP_HX_REQUEST='true')
        assert response.status_code == 200
        nomes = {t.name for t in response.templates}
        assert 'requisicoes/partials/_tabela_historico_requisicoes.html' in nomes
        assert 'requisicoes/historico_requisicoes.html' not in nomes

    def test_requisicao_normal_devolve_template_completo(self, client, superuser):
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        nomes = {t.name for t in response.templates}
        assert 'requisicoes/historico_requisicoes.html' in nomes

    def test_coluna_material_resume_item_unico(
        self, client, superuser, req_historico_obras, material_disponivel
    ):
        ItemRequisicao.objects.create(
            requisicao=req_historico_obras,
            material=material_disponivel,
            quantidade_solicitada=3,
        )
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert material_disponivel.nome.encode() in response.content

    def test_coluna_material_resume_multiplos_itens(
        self,
        client,
        superuser,
        req_historico_obras,
        material_disponivel,
        material_disponivel_2,
    ):
        ItemRequisicao.objects.create(
            requisicao=req_historico_obras,
            material=material_disponivel,
            quantidade_solicitada=3,
        )
        ItemRequisicao.objects.create(
            requisicao=req_historico_obras,
            material=material_disponivel_2,
            quantidade_solicitada=1,
        )
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert b'2 itens' in response.content


class TestHistoricoRequisicoesFiltros:
    def test_filtro_texto_reduz_resultado(
        self, client, superuser, req_historico_obras, req_historico_ti
    ):
        _login(client, superuser)
        com = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'Solicitante'})
        sem = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'inexistente'})
        assert com.context['page_obj'].paginator.count == 1
        assert sem.context['page_obj'].paginator.count == 0

    def test_filtro_estado_reduz_resultado(
        self, client, superuser, req_historico_obras, req_historico_ti
    ):
        _login(client, superuser)
        response = client.get(URL_HISTORICO_REQUISICOES, {'estados': ['autorizada']})
        pks = {r.pk for r in response.context['page_obj'].object_list}
        assert pks == {req_historico_ti.pk}

    def test_ordenacao_asc_inverte_cronologia(
        self, client, superuser, setor_obras, solicitante
    ):
        for i in range(2):
            Requisicao.objects.create(
                estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
                numero_publico=f'REQ-2026-2{i:03d}',
                criador=solicitante,
                beneficiario=solicitante,
                setor_beneficiario=setor_obras,
            )
        _login(client, superuser)
        desc = client.get(URL_HISTORICO_REQUISICOES).context['page_obj'].object_list
        asc = (
            client.get(URL_HISTORICO_REQUISICOES, {'ordem': 'asc'})
            .context['page_obj']
            .object_list
        )
        assert [r.pk for r in asc] == [r.pk for r in reversed(list(desc))]

    def test_filtro_setor_visivel_so_para_almox(
        self, client, chefe_almoxarifado, chefe_obras
    ):
        _login(client, chefe_almoxarifado)
        assert (
            client.get(URL_HISTORICO_REQUISICOES).context['mostrar_filtro_setor']
            is True
        )
        _login(client, chefe_obras)
        assert (
            client.get(URL_HISTORICO_REQUISICOES).context['mostrar_filtro_setor']
            is False
        )

    def test_chefe_setor_nao_filtra_por_setor_via_querystring(
        self, client, chefe_obras, req_historico_obras, req_historico_ti, setor_ti
    ):
        _login(client, chefe_obras)
        response = client.get(URL_HISTORICO_REQUISICOES, {'setor': setor_ti.pk})
        assert response.status_code == 200
        pks = {r.pk for r in response.context['page_obj'].object_list}
        assert req_historico_ti.pk not in pks

    def test_querystring_invalida_nao_quebra(self, client, superuser):
        _login(client, superuser)
        response = client.get(
            URL_HISTORICO_REQUISICOES,
            {
                'data_ini': 'abc',
                'data_fim': '2026-13-99',
                'setor': 'xyz',
                'ordem': 'lixo',
                'estados': 'nao_existe',
                'page': 'foo',
            },
        )
        assert response.status_code == 200

    def test_flag_tem_filtro_ativo(self, client, superuser):
        _login(client, superuser)
        com = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'x'})
        sem = client.get(URL_HISTORICO_REQUISICOES)
        assert com.context['tem_filtro_ativo'] is True
        assert sem.context['tem_filtro_ativo'] is False

    def test_empty_state_contextual_distingue_filtro_de_historico_vazio(
        self, client, superuser, req_historico_obras
    ):
        _login(client, superuser)
        filtrado = client.get(
            URL_HISTORICO_REQUISICOES, {'texto': 'inexistente'}
        ).content
        assert 'Nenhum resultado para este filtro'.encode() in filtrado
        assert 'Nenhuma requisição encontrada'.encode() not in filtrado


class TestNavHistoricoRequisicoes:
    def test_menu_mostra_link_para_almox(self, client, chefe_almoxarifado):
        # Página 'minhas' (não a própria tela de histórico, que já contém sua
        # URL nos atributos hx-get do form de filtros) para isolar o link de nav.
        _login(client, chefe_almoxarifado)
        response = client.get(reverse('requisicoes:minhas'))
        assert 'Histórico de requisições'.encode() in response.content

    def test_menu_esconde_link_para_solicitante(self, client, solicitante):
        _login(client, solicitante)
        response = client.get(reverse('requisicoes:minhas'))
        assert 'Histórico de requisições'.encode() not in response.content


# ---------------------------------------------------------------------------
# Testes dos achados médios da auditoria UI/UX — issue #63
# M1: side nav lg+, M2: campo Atualizada em, M3: coluna Material histórico,
# M4: badge cancelada, M5: scroll shadow, M6: ordem cards pronta retirada
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_side_nav_renderiza_links_para_autenticado(client, solicitante):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:minhas'))
    html = response.content.decode('utf-8')
    assert 'hidden lg:flex' in html
    assert 'Navegação principal' in html


@pytest.mark.django_db
def test_hamburger_oculto_em_lg(client, solicitante):
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:minhas'))
    assert 'lg:hidden' in response.content.decode('utf-8')


@pytest.mark.django_db
def test_detalhe_nao_exibe_campo_atualizado_em(
    client, solicitante, req_enviada_solicitante
):
    _login(client, solicitante)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_enviada_solicitante.pk})
    )
    assert response.status_code == 200
    assert 'Atualizada em'.encode() not in response.content


@pytest.mark.django_db
def test_historico_material_mostra_contagem_para_multi_itens(
    client, superuser, setor_obras, material_disponivel, material_disponivel_2
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-M301',
        criador=superuser,
        beneficiario=superuser,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req, material=material_disponivel, quantidade_solicitada=1
    )
    ItemRequisicao.objects.create(
        requisicao=req, material=material_disponivel_2, quantidade_solicitada=2
    )
    _login(client, superuser)
    response = client.get(reverse('requisicoes:historico'))
    assert '2 itens'.encode() in response.content


@pytest.mark.django_db
def test_historico_material_mostra_nome_como_secundario_para_item_unico(
    client, superuser, setor_obras, material_disponivel
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-M302',
        criador=superuser,
        beneficiario=superuser,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req, material=material_disponivel, quantidade_solicitada=1
    )
    _login(client, superuser)
    response = client.get(reverse('requisicoes:historico'))
    html = response.content.decode('utf-8')
    assert '1 item' in html
    assert material_disponivel.nome in html


@pytest.mark.django_db
def test_badge_cancelada_usa_cor_laranja(client, solicitante, setor_obras):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.CANCELADA,
        numero_publico='REQ-2026-M401',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert 'bg-orange-100'.encode() in response.content


@pytest.mark.django_db
def test_badge_recusada_usa_cor_vermelha(
    client, solicitante, req_enviada_solicitante, chefe_obras
):
    from apps.requisicoes.services import recusar_requisicao

    req = recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=req_enviada_solicitante.pk,
        motivo='Sem orçamento.',
    )
    _login(client, solicitante)
    response = client.get(reverse('requisicoes:detalhe', kwargs={'pk': req.pk}))
    assert response.status_code == 200
    assert 'bg-red-200'.encode() in response.content


@pytest.mark.django_db
def test_atender_retirada_tabela_tem_scroll_shadow(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse(
            'requisicoes:registrar_atendimento',
            kwargs={'pk': req_pronta_view_com_itens.pk},
        )
    )
    assert response.status_code == 200
    assert 'scroll-shadow-x'.encode() in response.content


@pytest.mark.django_db
def test_detalhe_pronta_retirada_registrar_antes_cancelar(
    client, aux_almoxarifado, req_pronta_view_com_itens
):
    _login(client, aux_almoxarifado)
    response = client.get(
        reverse('requisicoes:detalhe', kwargs={'pk': req_pronta_view_com_itens.pk})
    )
    html = response.content.decode('utf-8')
    assert html.index('atender-retirada-titulo') < html.index('cancelamento-titulo')
