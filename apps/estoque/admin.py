from django.contrib import admin

from apps.estoque.models import (
    Material,
    Estoque,
    SaldoEstoque,
    SaidaExcepcional,
    ItemSaidaExcepcional,
    SequenciaSaidaExcepcional,
    ImportacaoSCPI,
    MovimentacaoEstoque,
)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'unidade', 'ativo')
    list_filter = ('unidade', 'ativo')
    search_fields = ('codigo', 'nome')
    ordering = ('nome',)


@admin.register(Estoque)
class EstoqueAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'ativo')
    list_filter = ('ativo',)
    search_fields = ('codigo', 'nome')
    ordering = ('nome',)


@admin.register(SaldoEstoque)
class SaldoEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        'estoque',
        'material',
        'saldo_fisico',
        'saldo_reservado',
        'saldo_disponivel',
        'divergente',
    )
    list_filter = ('estoque', 'material')
    search_fields = ('estoque__nome', 'material__nome', 'material__codigo')
    ordering = ('estoque', 'material')
    readonly_fields = ('saldo_disponivel', 'divergente')


class ItemSaidaExcepcionalInline(admin.TabularInline):
    model = ItemSaidaExcepcional
    extra = 1


@admin.register(SaidaExcepcional)
class SaidaExcepcionalAdmin(admin.ModelAdmin):
    list_display = (
        'numero_publico',
        'estoque',
        'registrado_por',
        'criado_em',
        'estado',
    )
    list_filter = ('estado', 'estoque', 'criado_em')
    search_fields = ('numero_publico', 'estoque__nome')
    ordering = ('-criado_em',)
    inlines = [ItemSaidaExcepcionalInline]


@admin.register(SequenciaSaidaExcepcional)
class SequenciaSaidaExcepcionalAdmin(admin.ModelAdmin):
    list_display = ('ano', 'ultimo_numero')
    ordering = ('-ano',)


@admin.register(ImportacaoSCPI)
class ImportacaoSCPIAdmin(admin.ModelAdmin):
    list_display = (
        'arquivo_nome',
        'estoque',
        'importado_por',
        'importado_em',
        'status',
        'total_novos',
    )
    list_filter = ('status', 'estoque', 'importado_em')
    search_fields = ('arquivo_nome', 'estoque__nome')
    ordering = ('-importado_em',)
    readonly_fields = ('arquivo_hash', 'importado_em')


@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        'tipo',
        'material',
        'estoque',
        'delta_fisico',
        'delta_reservado',
        'criado_em',
    )
    list_filter = ('tipo', 'estoque', 'criado_em')
    search_fields = ('material__nome', 'material__codigo')
    ordering = ('-criado_em',)
    readonly_fields = ('criado_em',)
