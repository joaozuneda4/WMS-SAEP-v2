/**
 * autocomplete — Alpine factory para combobox ARIA com busca remota (debounce 300ms).
 *
 * Cobre o contrato comum às buscas de beneficiário/material do projeto:
 * digitar invalida a seleção anterior; foco com campo vazio lista tudo;
 * Enter confirma o item ativo; Esc/blur fecham o dropdown.
 *
 * O componente NÃO renderiza o hidden input do valor selecionado — isso fica
 * a cargo do template chamador, que deve declarar um elemento com
 * `x-ref="hiddenInput"` dentro do mesmo escopo `x-data`.
 *
 * Config aceito por `autocomplete(config)`:
 *   endpoint       (obrigatório) URL do JSON de busca (?q=)
 *   minChars       (opcional, default 2) abaixo disso a busca não dispara
 *   campoDisplay   (opcional, default 'label') campo do item usado para
 *                  preencher o texto exibido após seleção
 *   initialId      (opcional) valor inicial do hidden input (edição)
 *   initialLabel   (opcional) texto inicial exibido (edição)
 *   onSelect(item) (opcional) callback; retornar `false` veta a seleção —
 *                  nesse caso o componente não altera query/hidden/dropdown
 *   onInvalidate() (opcional) callback chamado quando a edição invalida a
 *                  seleção anterior (hidden zerado) — usar para sincronizar
 *                  estado externo (ex. guarda de duplicidade por linha)
 *
 * Uso no template chamador:
 *   <div x-data="autocomplete({ endpoint: '{% url ... %}', minChars: 2 })">
 *     <input type="hidden" x-ref="hiddenInput" name="...">
 *     {% include "components/autocomplete.html" with ... %}
 *   </div>
 */
(function () {
  'use strict';

  function factory(config = {}) {
    return {
      endpoint: config.endpoint,
      minChars: config.minChars ?? 2,
      campoDisplay: config.campoDisplay || 'label',
      onSelect: typeof config.onSelect === 'function' ? config.onSelect : null,
      onInvalidate: typeof config.onInvalidate === 'function' ? config.onInvalidate : null,

      idBase: '',
      query: '',
      resultados: [],
      aberto: false,
      buscando: false,
      ativo: -1,
      _debounceTimer: null,
      _abortController: null,

      init() {
        this.idBase = 'autocomplete-' + proximoId();
        if (config.initialId) {
          if (this.$refs.hiddenInput) {
            this.$refs.hiddenInput.value = config.initialId;
          }
          this.query = (config.initialLabel || '').trim();
        }
      },

      buscarComDebounce() {
        this._abortController?.abort();
        this._abortController = null;
        this.buscando = false;
        this.resultados = [];
        this.fecharDropdown();

        if (this.$refs.hiddenInput) {
          this.$refs.hiddenInput.value = '';
        }
        if (this.onInvalidate) {
          this.onInvalidate();
        }
        clearTimeout(this._debounceTimer);
        const query = this.query;
        this._debounceTimer = setTimeout(() => this._buscarComGate(query), 300);
      },

      async buscarTodos() {
        if (!this.query) {
          await this.buscar('');
        } else if (this.resultados.length > 0) {
          this.aberto = true;
        } else {
          await this._buscarComGate(this.query);
        }
      },

      async _buscarComGate(q) {
        if (this.minChars > 0 && q.length > 0 && q.length < this.minChars) {
          this.resultados = [];
          this.fecharDropdown();
          return;
        }
        await this.buscar(q);
      },

      async buscar(q) {
        this._abortController?.abort();
        const controller = new AbortController();
        this._abortController = controller;

        this.buscando = true;
        try {
          const res = await fetch(`${this.endpoint}?q=${encodeURIComponent(q ?? '')}`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            signal: controller.signal,
          });
          const data = await res.json();
          if (this._abortController !== controller) return;
          this.resultados = data.resultados || [];
          this.aberto = true;
          this.ativo = -1;
        } catch (e) {
          if (e.name === 'AbortError') return;
          this.resultados = [];
        } finally {
          if (this._abortController === controller) {
            this.buscando = false;
            this._abortController = null;
          }
        }
      },

      selecionar(item) {
        const aceito = this.onSelect ? this.onSelect(item) !== false : true;
        if (!aceito) {
          // Veto não destrutivo: query/hidden/dropdown ficam como estavam.
          return;
        }
        this.query = item[this.campoDisplay] ?? item.label ?? '';
        if (this.$refs.hiddenInput) {
          this.$refs.hiddenInput.value = item.id;
        }
        this.fecharDropdown();
        this.$nextTick(() => this.$refs.displayInput?.blur());
      },

      limpar() {
        this.query = '';
        this.resultados = [];
        if (this.$refs.hiddenInput) {
          this.$refs.hiddenInput.value = '';
        }
        this.fecharDropdown();
      },

      fecharDropdown() {
        this.aberto = false;
        this.ativo = -1;
      },

      selecionarProximo() {
        if (this.ativo < this.resultados.length - 1) {
          this.ativo++;
          this._rolarParaAtivo();
        }
      },

      selecionarAnterior() {
        if (this.ativo > 0) {
          this.ativo--;
          this._rolarParaAtivo();
        }
      },

      _rolarParaAtivo() {
        this.$nextTick(() => {
          const el = document.getElementById(this.idBase + '-opt-' + this.ativo);
          if (el) el.scrollIntoView({ block: 'nearest' });
        });
      },

      confirmarSelecao() {
        if (this.ativo >= 0 && this.resultados[this.ativo]) {
          this.selecionar(this.resultados[this.ativo]);
        }
      },

      mensagemVaziaVisivel() {
        const minimo = Math.max(this.minChars, 1);
        return !this.buscando && this.query.length >= minimo && this.resultados.length === 0;
      },
    };
  }

  let _uidSeq = 0;
  function proximoId() {
    _uidSeq += 1;
    return _uidSeq;
  }

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('autocomplete', factory);
  });
})();
