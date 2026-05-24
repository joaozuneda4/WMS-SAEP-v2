from django.urls import path

from apps.requisicoes import views

app_name = 'requisicoes'

urlpatterns = [
    path('minhas/', views.minhas_requisicoes_view, name='minhas'),
    path('nova/', views.nova_requisicao, name='nova_requisicao'),
    path('<int:pk>/', views.detalhe_requisicao_view, name='detalhe'),
    path('<int:pk>/editar/', views.editar_rascunho_view, name='editar_rascunho'),
    path('<int:pk>/enviar/', views.enviar_rascunho_view, name='enviar_rascunho'),
    path('itens/nova-linha/', views.nova_linha_item, name='nova_linha_item'),
    path('materiais/busca/', views.buscar_materiais, name='buscar_materiais'),
]
