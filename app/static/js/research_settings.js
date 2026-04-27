(function () {
    const popup = document.getElementById('popup-overlay');
    const getVal = (name) => parseInt(popup.querySelector(`[name="${name}"]`).value) || 0;
    const setVal = (name, v) => { popup.querySelector(`[name="${name}"]`).value = v; };
    const getTotal = () => parseInt(document.getElementById('rp-total-count')?.textContent) || Infinity;

    const setSpan = (sel, v) => { const el = popup.querySelector(sel); if (el) el.textContent = v; };

    function clamp() {
        const total = getTotal();
        let bm25 = Math.min(getVal('n_top_bm25_chunks'), total);
        let embed = Math.min(getVal('n_top_embed_chunks'), bm25);
        let rerank = Math.min(getVal('n_top_rerank_chunks'), embed);
        setVal('n_top_bm25_chunks', bm25); setSpan('.rp-bm25 span', bm25);
        setVal('n_top_embed_chunks', embed); setSpan('.rp-embed span', embed);
        setVal('n_top_rerank_chunks', rerank); setSpan('.rp-reranker span', rerank);
        const rc = popup.querySelector('#result_count'); if (rc) rc.value = rerank;
        setSpan('.rp-source span', rerank);
    }

    ['n_top_bm25_chunks', 'n_top_embed_chunks', 'n_top_rerank_chunks'].forEach(name => {
        popup.querySelector(`[name="${name}"]`).addEventListener('input', clamp);
    });

    ['n_vectors', 'n_search_queries', 'n_top_search_results'].forEach(name => {
        popup.querySelector(`[name="${name}"]`).addEventListener('input', () => setTimeout(clamp, 0));
    });
})();
