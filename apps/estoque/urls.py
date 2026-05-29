from django.urls import path

from apps.estoque import views

app_name = 'estoque'

urlpatterns = [
    path(
        'saidas-excepcionais/',
        views.listar_saidas_excepcionais_view,
        name='listar_saidas_excepcionais',
    ),
]
