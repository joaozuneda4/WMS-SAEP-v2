from django.contrib import admin

from apps.requisicoes.models import (
    Requisicao,
    ItemRequisicao,
    SequenciaRequisicao,
    TimelineRequisicao,
)


class ItemRequisicaoInline(admin.TabularInline):
    model = ItemRequisicao
    extra = 1


@admin.register(Requisicao)
class RequisicaoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_publico',
        'beneficiario',
        'criador',
        'setor_beneficiario',
        'estado',
        'criado_em',
    )
    list_filter = ('estado', 'setor_beneficiario', 'criado_em')
    search_fields = ('numero_publico', 'beneficiario__nome', 'criador__nome')
    ordering = ('-criado_em',)
    inlines = [ItemRequisicaoInline]
    fieldsets = (
        ('Informações Gerais', {'fields': ('numero_publico', 'estado')}),
        ('Pessoas', {'fields': ('criador', 'beneficiario', 'setor_beneficiario')}),
        ('Observações', {'fields': ('observacao_geral',)}),
        ('Datas', {'fields': ('criado_em', 'atualizado_em'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('numero_publico', 'criado_em', 'atualizado_em')


@admin.register(ItemRequisicao)
class ItemRequisicaoAdmin(admin.ModelAdmin):
    list_display = (
        'requisicao',
        'material',
        'quantidade_solicitada',
        'quantidade_autorizada',
        'quantidade_entregue',
    )
    list_filter = ('requisicao__estado', 'material')
    search_fields = ('requisicao__numero_publico', 'material__nome', 'material__codigo')
    ordering = ('requisicao', 'id')


@admin.register(SequenciaRequisicao)
class SequenciaRequisicaoAdmin(admin.ModelAdmin):
    list_display = ('ano', 'ultimo_numero')
    ordering = ('-ano',)


@admin.register(TimelineRequisicao)
class TimelineRequisicaoAdmin(admin.ModelAdmin):
    list_display = ('requisicao', 'evento', 'ator', 'estado_resultante', 'criado_em')
    list_filter = ('evento', 'estado_resultante', 'criado_em')
    search_fields = ('requisicao__numero_publico', 'ator__nome')
    ordering = ('-criado_em',)
    readonly_fields = ('criado_em',)
