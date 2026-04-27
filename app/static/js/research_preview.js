(function () {
    var MAPPINGS = [
        { hoverSel: '.rp-direction',    spanSel: '.rp-direction span',    inputSel: '[name="n_vectors"]' },
        { hoverSel: '.rp-search',       spanSel: '.rp-search span',       inputSel: '[name="n_top_search_results"]' },
        { hoverSel: '.rp-search-count', spanSel: '.rp-search-count',      inputSel: '[name="n_search_queries"]' },
        { hoverSel: '.rp-bm25',         spanSel: '.rp-bm25 span',         inputSel: '[name="n_top_bm25_chunks"]' },
        { hoverSel: '.rp-embed',        spanSel: '.rp-embed span',        inputSel: '[name="n_top_embed_chunks"]' },
        { hoverSel: '.rp-reranker',     spanSel: '.rp-reranker span',     inputSel: '[name="n_top_rerank_chunks"]' },
        { hoverSel: '.rp-source',       spanSel: '.rp-source span',       inputSel: '#result_count' },
    ];

    function initResearchPreview() {
        var popup = document.getElementById('popup');
        if (!popup || !popup.querySelector('.research-preview')) return;
        if (popup._rpInited) return;
        popup._rpInited = true;

        var form = popup.querySelector('form');

        function updateBarWidths() {
            var total = parseInt(popup.querySelector('#rp-total-count')?.textContent) || 0;
            var bm25 = parseInt(popup.querySelector('.rp-bm25 span')?.textContent) || 0;
            var embed = parseInt(popup.querySelector('.rp-embed span')?.textContent) || 0;
            var rerank = parseInt(popup.querySelector('.rp-reranker span')?.textContent) || 0;

            function safeRatio(num, den) {
                if (!den || den <= 0) return 1;
                return Math.min(1, Math.max(0, num / den));
            }

            var bm25Pct = Math.max(80, safeRatio(bm25, total) * 100);
            var embedPct = bm25Pct * safeRatio(embed, bm25);
            var rerankPct = embedPct * safeRatio(rerank, embed);

            var bm25El = popup.querySelector('.rp-bm25');
            var embedEl = popup.querySelector('.rp-embed');
            var rerankerWrapper = popup.querySelector('.rp-reranker-wrapper');
            var sourceEl = popup.querySelector('.rp-source');

            if (bm25El) bm25El.style.width = bm25Pct.toFixed(2) + '%';
            if (embedEl) embedEl.style.width = embedPct.toFixed(2) + '%';
            if (rerankerWrapper) rerankerWrapper.style.width = rerankPct.toFixed(2) + '%';
            if (sourceEl) sourceEl.style.width = rerankPct.toFixed(2) + '%';
        }

        function syncPreviews() {
            if (form) {
                var rerankInput = form.querySelector('[name="n_top_rerank_chunks"]');
                var resultCount = form.querySelector('#result_count');
                if (rerankInput && resultCount) {
                    resultCount.value = rerankInput.value || rerankInput.placeholder;
                }
                MAPPINGS.forEach(function (m) {
                    var spanEl = popup.querySelector(m.spanSel);
                    var inputEl = form.querySelector(m.inputSel);
                    if (spanEl && inputEl) {
                        spanEl.textContent = inputEl.value || inputEl.placeholder;
                    }
                });
                var totalEl = popup.querySelector('.rp-total span');
                if (totalEl) {
                    var vIn = form.querySelector('[name="n_vectors"]');
                    var qIn = form.querySelector('[name="n_search_queries"]');
                    var tIn = form.querySelector('[name="n_top_search_results"]');
                    var v = parseInt((vIn && (vIn.value || vIn.placeholder)) || 0);
                    var q = parseInt((qIn && (qIn.value || qIn.placeholder)) || 0);
                    var t = parseInt((tIn && (tIn.value || tIn.placeholder)) || 0);
                    totalEl.textContent = v * q * t;
                }
            }
            updateBarWidths();
        }

        if (form) {
            ['n_vectors', 'n_top_search_results', 'n_search_queries',
             'n_top_bm25_chunks', 'n_top_embed_chunks', 'n_top_rerank_chunks'
            ].forEach(function (name) {
                var el = form.querySelector('[name="' + name + '"]');
                if (el) el.addEventListener('input', syncPreviews);
            });

            MAPPINGS.forEach(function (m) {
                var hoverEl = popup.querySelector(m.hoverSel);
                var inputEl = form.querySelector(m.inputSel);
                if (hoverEl && inputEl) {
                    hoverEl.addEventListener('mouseenter', function () { inputEl.classList.add('rp-highlighted'); });
                    hoverEl.addEventListener('mouseleave', function () { inputEl.classList.remove('rp-highlighted'); });
                }
            });
        }

        syncPreviews();
    }

    document.body.addEventListener('htmx:afterSettle', initResearchPreview);
})();
