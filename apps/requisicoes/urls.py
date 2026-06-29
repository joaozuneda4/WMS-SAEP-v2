from django.urls import path

from apps.requisicoes import views

app_name = 'requisicoes'

urlpatterns = [
    path('minhas/', views.minhas_requisicoes_view, name='minhas'),
    path('autorizacoes/', views.fila_autorizacao_view, name='autorizacoes'),
    path('atendimentos/', views.fila_atendimento_view, name='atendimentos'),
    path('nova/', views.nova_requisicao, name='nova_requisicao'),
    path('<int:pk>/', views.detalhe_requisicao_view, name='detalhe'),
    path('<int:pk>/autorizar/', views.autorizar_requisicao_view, name='autorizar'),
    path('<int:pk>/cancelar/', views.cancelar_requisicao_view, name='cancelar'),
    path(
        '<int:pk>/separar-retirada/',
        views.separar_retirada_view,
        name='separar_retirada',
    ),
    path(
        '<int:pk>/atender/',
        views.registrar_atendimento_view,
        name='registrar_atendimento',
    ),
    path('<int:pk>/editar/', views.editar_rascunho_view, name='editar_rascunho'),
    path('<int:pk>/enviar/', views.enviar_rascunho_view, name='enviar_rascunho'),
    path(
        '<int:pk>/retornar-rascunho/',
        views.retornar_rascunho_view,
        name='retornar_rascunho',
    ),
    path('<int:pk>/recusar/', views.recusar_requisicao_view, name='recusar'),
    path('<int:pk>/copiar/', views.copiar_requisicao_view, name='copiar'),
    path('<int:pk>/estornar/', views.estornar_requisicao_view, name='estornar'),
    path(
        '<int:pk>/devolver/<int:item_pk>/',
        views.registrar_devolucao_view,
        name='registrar_devolucao',
    ),
    path('itens/nova-linha/', views.nova_linha_item, name='nova_linha_item'),
    path(
        'importacao-scpi/confirmar/',
        views.confirmar_importacao_scpi_view,
        name='confirmar_importacao_scpi',
    ),
    path('materiais/busca/', views.buscar_materiais, name='buscar_materiais'),
    path(
        'beneficiarios/busca/', views.buscar_beneficiarios, name='buscar_beneficiarios'
    ),
]
