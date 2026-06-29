from django.urls import path

from apps.estoque import views

app_name = 'estoque'

urlpatterns = [
    path(
        'materiais/',
        views.lista_materiais_view,
        name='lista_materiais',
    ),
    path(
        'movimentacoes/',
        views.historico_movimentacoes_view,
        name='historico_movimentacoes',
    ),
    path(
        'saidas-excepcionais/',
        views.listar_saidas_excepcionais_view,
        name='listar_saidas_excepcionais',
    ),
    path(
        'saidas-excepcionais/nova/',
        views.nova_saida_excepcional_view,
        name='nova_saida_excepcional',
    ),
    path(
        'saidas-excepcionais/buscar-materiais/',
        views.buscar_materiais_saida_excepcional_view,
        name='buscar_materiais_saida_excepcional',
    ),
    path(
        'saidas-excepcionais/<int:pk>/',
        views.detalhe_saida_excepcional_view,
        name='detalhe_saida_excepcional',
    ),
    path(
        'saidas-excepcionais/<int:pk>/estornar/',
        views.estornar_saida_excepcional_view,
        name='estornar_saida_excepcional',
    ),
    path(
        'importacao-scpi/pre-visualizacao/',
        views.preview_importacao_scpi_view,
        name='preview_importacao_scpi',
    ),
    path(
        'importacao-scpi/confirmada/<int:pk>/',
        views.sucesso_importacao_scpi_view,
        name='sucesso_importacao_scpi',
    ),
    path(
        'importacao-scpi/historico/',
        views.historico_importacoes_scpi_view,
        name='historico_importacoes_scpi',
    ),
]
