# Checklist de go-live

Conferências a fazer no ambiente de produção **antes** de liberar o sistema aos
usuários, e a cada retomada após manutenção que toque dados de estoque.

Cada item registra o que conferir, como conferir e o que fazer quando a
conferência falha.

## Estoque

### GL-01 — Existe exatamente um `Estoque`

**Por quê.** Os services de estoque assumem um único `Estoque` nesta fase
(ADR-0017): localizam saldo apenas por `material_id`, sem `estoque_id`, e
tratam "mais de um `SaldoEstoque` para o mesmo material" como erro. Um segundo
estoque com saldo para um material já usado quebra **globalmente** autorização,
separação, atendimento e cancelamento de qualquer setor, com uma mensagem
(`saldo_ambiguo` / `separacao_bloqueada`) que não indica a causa.

`EstoqueAdmin.has_add_permission` barra a criação de um segundo estoque pela
interface do admin, mas **não** cobre criação por shell, `seed_dev` ou
migration — daí este item de checklist.

**Como conferir.**

```sql
SELECT id, codigo, nome, ativo FROM estoque_estoque;
```

Esperado: exatamente uma linha, com `ativo = true`.

**Detecção do sintoma** — materiais com saldo em mais de um estoque:

```sql
SELECT material_id, count(*)
FROM estoque_saldoestoque
GROUP BY material_id
HAVING count(*) > 1;
```

Esperado: nenhuma linha. Qualquer linha retornada é um material cuja
autorização, separação e atendimento já estão quebrados.

**Se falhar.** Não libere o sistema. Consolide os saldos em um único `Estoque`
antes de seguir — apagar um `Estoque` com `SaldoEstoque` e
`MovimentacaoEstoque` associados é operação destrutiva e não há service que a
suporte; a consolidação precisa de runbook próprio, com backup e migração de
saldos e do ledger.

Se o segundo estoque foi criado por engano e ainda **não** tem saldos nem
movimentações, apagá-lo resolve o item.
