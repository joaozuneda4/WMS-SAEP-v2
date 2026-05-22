from django.urls import path

from apps.requisicoes import views

app_name = 'requisicoes'

urlpatterns = [
    path('nova/', views.nova_requisicao, name='nova_requisicao'),
    path('<int:pk>/editar/', views.editar_rascunho_view, name='editar_rascunho'),
    path('itens/nova-linha/', views.nova_linha_item, name='nova_linha_item'),
    path('materiais/busca/', views.buscar_materiais, name='buscar_materiais'),
]
