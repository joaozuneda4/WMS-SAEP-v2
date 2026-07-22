/**
 * itensFormset — Alpine factory para o container de linhas de item de um
 * formset dinâmico (`item_form_row.html`, ADR-0016).
 *
 * Vive no container (ex. `#itens-container`), não em cada linha, porque
 * "pode remover" depende de contar linhas-irmãs ainda visíveis — uma linha
 * isolada não enxerga as demais. As linhas herdam este escopo Alpine por
 * aninhamento normal do DOM (sem `x-data` próprio), então o botão de cada
 * linha chama `removerLinha($event)` direto.
 *
 * Uso no template chamador:
 *   <div id="itens-container" x-data="itensFormset()">
 *     {% include "components/item_form_row.html" ... %}
 *   </div>
 */
(function () {
  'use strict';

  function factory() {
    return {
      // $el reflete o elemento onde a expressão Alpine foi avaliada (o botão
      // clicado), não a raiz do x-data — por isso guardamos o container aqui.
      init() {
        this._container = this.$el;
      },

      podRemoverItem() {
        return this._container.querySelectorAll('.item-form-row:not([style*="display: none"])').length > 1;
      },

      removerLinha(event) {
        const row = event.target.closest('.item-form-row');
        if (!row) return;

        if (!this.podRemoverItem()) {
          this._avisarNaoPodeRemover(row);
          return;
        }

        const outraLinhaVisivel = Array.from(
          this._container.querySelectorAll('.item-form-row:not([style*="display: none"])')
        ).find((linha) => linha !== row);
        const botaoFoco = outraLinhaVisivel?.querySelector('button[aria-label="Remover item"]');

        row.style.display = 'none';
        const deleteInput = row.querySelector('[name$="-DELETE"]');
        if (deleteInput) deleteInput.value = 'on';
        botaoFoco?.focus();
      },

      _avisarNaoPodeRemover(row) {
        const aviso = document.querySelector('.aviso_quantidade');
        if (aviso) aviso.style.color = '#f87171';
        row.style.outline = '2px solid #f87171';
        setTimeout(() => {
          if (aviso) aviso.style.color = '';
          row.style.outline = '';
        }, 2000);
      },
    };
  }

  document.addEventListener('alpine:init', () => {
    window.Alpine.data('itensFormset', factory);
  });
})();
