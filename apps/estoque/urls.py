from django.urls import path

from apps.estoque import views

app_name = 'estoque'

urlpatterns = [
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
]
