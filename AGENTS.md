# AGENTS.md — WMS-SAEP-v2

@/Users/jmzr/.codex/RTK.md

<!-- context7 -->
Use o Context7 MCP para buscar documentação atualizada sempre que o usuário perguntar sobre uma biblioteca, framework, SDK, API, CLI ou serviço de nuvem — mesmo os bem conhecidos, como Tailwind ou Django. Isso inclui sintaxe de API, configuração, migração de versão, debugging específico de biblioteca, instruções de setup e uso de CLI. Use mesmo quando achar que já sabe a resposta — seu treinamento pode não refletir mudanças recentes. Prefira isso a busca na web para documentação de bibliotecas.
<!-- context7 -->

## Referência rápida de IDs de biblioteca no Context7:
- Django 6: `/django/django/6_0a1`
- django-htmx: `/adamchainz/django-htmx`
- Tailwind CSS: `/tailwindlabs/tailwindcss.com`
- Alpine.js: `/websites/alpinejs_dev`

> Este projeto é server-rendered (Django + HTMX + Alpine.js, sem camada de API REST). `django-rest-framework` não é dependência — não busque a documentação dele a menos que a stack mude.

<!-- serena -->
Use o Serena MCP para entendimento semântico do código e navegação ciente de símbolos sempre que o usuário perguntar sobre um projeto, repositório, módulo, classe, função ou detalhe de implementação existente.
<!-- serena -->

## Skills de agente

### Rastreador de issues

Issues e PRDs são rastreados como GitHub Issues em `JMZR-SAEP/WMS-SAEP-v2`. Veja `docs/agents/issue-tracker.md`.

### Labels de triagem

Use o vocabulário padrão de triagem: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human` e `wontfix`. Veja `docs/agents/triage-labels.md`.

### Documentação de domínio

Repositório de contexto único. Use `docs/agents/domain.md` como guia de roteamento para a documentação de domínio.

Se a documentação e a memória divergirem, confie primeiro na documentação/código vivos e atualize a memória do Serena quando a decisão for durável.

### Handoff de design

Para trabalho de UI/frontend, use `.design/` como handoff de design obrigatório antes de implementar ou revisar telas.

Leia primeiro os arquivos aplicáveis:

- `.design/INFORMATION_ARCHITECTURE.md` para rotas, navegação, hierarquia de páginas, fluxos de usuário, labels e estratégia de URL.
- `.design/TASKS.md` para o breakdown atual de construção de UI gerado a partir dos briefs.
- `.design/<area>/DESIGN_BRIEF.md` para UX, layout, interação, responsividade, acessibilidade, copy e decisões de fora do escopo específicas de cada tela.

`.design/` orienta implementação e revisão, mas não sobrepõe ADRs aceitos, `docs/design-system.md`, `docs/CONVENTIONS.md`, regras de domínio, testes ou código vivo. Se `.design/` conflitar com essas fontes, exponha o conflito antes de implementar.

Ao implementar UI a partir de `.design/`, mantenha o escopo restrito ao brief/task referenciado, a menos que o usuário peça expansão explicitamente.

### Convenções de código

Não duplique regras do projeto aqui. Use estas fontes:

- Arquitetura em camadas e regras de implementação: `docs/CONVENTIONS.md` e ADR-0004.
- Contrato service/policy/exceção de domínio: ADR-0011.
- Estratégia de testes: ADR-0010.
- Frontend server-rendered e design system: `docs/design-system.md` e ADR-0008.
- Handoff de UI/frontend: `.design/`, especialmente `.design/INFORMATION_ARCHITECTURE.md`, `.design/TASKS.md` e o `.design/<area>/DESIGN_BRIEF.md` relevante.
- Contrato de dados de seed/dev: ADR-0009.

## Comandos do projeto

- Rodar testes: `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical` (bate com o CI; `-n logical` roda a suíte em paralelo via pytest-xdist)
- Formatar código: `uv run ruff format .`
- Checar formatação: `uv run ruff format --check .`
- Lint: `uv run ruff check .`
- Checagem de tipos: `uv run mypy apps`

> **Nunca use redirecionamentos, pipes, `tail`, `head`, `grep` ou truncamento de saída.** Quando um comando falhar, use o caminho `[full output: ...]` emitido pelo RTK Tee System para inspecionar a saída bruta completa sem reexecutar o comando.

## Ambiente de desenvolvimento efêmero

O ambiente local é descartável em dev.

- o banco de dados local pode ser apagado e recriado;
- o fluxo padrão é resetar banco -> aplicar migrations -> carregar dados mínimos, quando o comando correspondente existir;
- migrations locais não são versionadas e estão no `.gitignore`;
- `make init` deve ser usado no setup inicial do projeto para criar o .venv e instalar dependências;
- nesta fase do projeto, toda edição em `models` ou schema deve ser seguida de `make setup`, para que o fluxo não dependa de gerenciamento manual de migrations;
- migrations do app devem ser tratadas como artefatos efêmeros: antes de testar ou finalizar uma implementação que muda o schema, apague e recrie as migrations locais do zero, simulando uma execução inicial limpa do app;
- criar novos arquivos de migration não faz parte da entrega normal neste contexto efêmero;
- a fonte de verdade para mudanças estruturais são `models`, constraints, índices, regras de domínio e testes; migrations locais só materializam o banco local;
- tarefas sem mudança estrutural podem seguir um fluxo incremental; reset completo é obrigatório só para mudanças de schema/model ou quando o ambiente local está inconsistente;
- a ADR-0009 define `seed_dev`/`make seed-dev` como o contrato de seed local; o target existe no Makefile e pode ser executado diretamente.

## Convenção de idioma

- Identificadores de domínio usam PT-BR: models, fields, choices, services, policies, selectors e funções/variáveis de domínio. Isso mantém o código alinhado à linguagem ubíqua e ao glossário do `CONTEXT.md`.
- A superfície técnica/de framework permanece em inglês onde o framework impõe isso: nomes de pacote de app (ex. `accounts`), atributos herdados do Django (`is_active`, `is_staff`, `is_superuser`, `USERNAME_FIELD`) e hooks padrão.
- URLs usam slugs em PT-BR (ex. `/requisicoes/`, `/requisicoes/nova/`).
- Documentação e comentários de código devem usar PT-BR.
- Models do Django devem sempre definir `verbose_name` e `verbose_name_plural` em PT-BR.

## Fluxo de trabalho git

- **Nunca commitar direto na main** — sempre criar uma branch de feature primeiro.
- Confirmar a branch atual antes de qualquer operação de commit.
- Nomes de branch: `feat/{desc}`, `fix/{desc}`, `refactor/{desc}`, `test/{desc}`, `docs/{desc}`, `chore/{desc}`.
- Commits devem ser pequenos, coesos e reversíveis — uma unidade lógica por commit.
