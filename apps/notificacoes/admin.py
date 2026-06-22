from django.contrib import admin

from apps.notificacoes.models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'tipo', 'requisicao_id', 'lida', 'criado_em')
    list_filter = ('tipo', 'lida')
    search_fields = ('destinatario__matricula', 'destinatario__nome')
    readonly_fields = ('criado_em',)
