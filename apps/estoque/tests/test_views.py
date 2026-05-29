"""Testes de view para estoque.saidas_excepcionais."""

from django.urls import reverse


URL = reverse('estoque:listar_saidas_excepcionais')


class TestListarSaidasExcepcionaisView:
    def test_chefe_almox_acessa_lista(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        assert response.status_code == 200

    def test_aux_almox_acessa_lista(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL)
        assert response.status_code == 200

    def test_superuser_acessa_lista(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL)
        assert response.status_code == 200

    def test_solicitante_recebe_403(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(URL)
        assert response.status_code == 403

    def test_usuario_inativo_redirecionado_para_login(self, client, usuario_inativo):
        # Django ModelBackend trata is_active=False como não-autenticado;
        # @login_required redireciona para login (USR-01).
        client.force_login(usuario_inativo)
        response = client.get(URL)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL)
        assert response.status_code == 302
        assert (
            '/login' in response['Location'] or 'accounts/login' in response['Location']
        )

    def test_contexto_contem_saidas(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        assert 'saidas' in response.context

    def test_pode_registrar_verdadeiro_para_chefe(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        assert response.context['pode_registrar'] is True

    def test_pode_registrar_falso_para_aux(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL)
        assert response.context['pode_registrar'] is False

    def test_pode_registrar_verdadeiro_para_superuser(self, client, superuser):
        # Superuser tem override técnico para registrar (matriz-permissoes.md linha 78)
        client.force_login(superuser)
        response = client.get(URL)
        assert response.context['pode_registrar'] is True


URL_NOVA = reverse('estoque:nova_saida_excepcional')
URL_BUSCAR = reverse('estoque:buscar_materiais_saida_excepcional')


class TestNovaSaidaExcepcionalView:
    def test_chefe_acessa_formulario(
        self, client, chefe_almoxarifado, estoque_principal
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_NOVA)
        assert response.status_code == 200

    def test_superuser_acessa_formulario(self, client, superuser, estoque_principal):
        client.force_login(superuser)
        response = client.get(URL_NOVA)
        assert response.status_code == 200

    def test_aux_recebe_403(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL_NOVA)
        assert response.status_code == 403

    def test_solicitante_recebe_403(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(URL_NOVA)
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL_NOVA)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_post_valido_cria_saida_e_redireciona(
        self, client, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Caixas molhadas',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 302
        from apps.estoque.models import SaidaExcepcional

        assert SaidaExcepcional.objects.count() == 1
        saida = SaidaExcepcional.objects.get()
        assert saida.numero_publico.startswith('SXP-')

    def test_post_sem_motivo_retorna_form_com_erro(
        self, client, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': '',
                'observacao': 'obs válida',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 200
        assert 'motivo' in response.context['erros']

    def test_post_sem_itens_retorna_form_com_erro(
        self, client, chefe_almoxarifado, estoque_principal
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'obs válida',
                'itens-TOTAL_FORMS': '0',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
            },
        )
        assert response.status_code == 200
        assert 'itens' in response.context['erros']

    def test_post_aux_recebe_403_sem_persistencia(
        self, client, aux_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.estoque.models import SaidaExcepcional

        client.force_login(aux_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Teste',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 403
        assert SaidaExcepcional.objects.count() == 0

    def test_post_solicitante_recebe_403_sem_persistencia(
        self, client, solicitante, estoque_principal, material_disponivel
    ):
        from apps.estoque.models import SaidaExcepcional

        client.force_login(solicitante)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Teste',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 403
        assert SaidaExcepcional.objects.count() == 0

    def test_post_anonimo_redireciona_sem_persistencia(
        self, client, material_disponivel
    ):
        from apps.estoque.models import SaidaExcepcional

        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Teste',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 302
        assert 'login' in response['Location']
        assert SaidaExcepcional.objects.count() == 0


class TestBuscarMateriasSaidaExcepcionalView:
    def test_chefe_recebe_json(self, client, chefe_almoxarifado, material_disponivel):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_BUSCAR, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert response.status_code == 200
        data = response.json()
        assert 'resultados' in data

    def test_filtra_por_q(self, client, chefe_almoxarifado, material_disponivel):
        client.force_login(chefe_almoxarifado)
        response = client.get(
            URL_BUSCAR + '?q=Parafuso', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert response.status_code == 200
        data = response.json()
        assert any('Parafuso' in r['nome'] for r in data['resultados'])

    def test_aux_recebe_403(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL_BUSCAR, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert response.status_code == 403

    def test_anonimo_redirecionado(self, client):
        response = client.get(URL_BUSCAR)
        assert response.status_code == 302
