(function () {
    var contentEl = document.querySelector('.content-research[data-research-id]');
    if (!contentEl) return;

    var researchId = contentEl.dataset.researchId;
    var commentOverlay = document.getElementById('segment-comment-overlay');
    var commentTextarea = document.getElementById('segment-comment-textarea');
    var currentRow = null;

    async function patchSegment(segIdx, data) {
        try {
            var resp = await fetch('/api/v1/researches/' + researchId + '/segments/' + segIdx, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            return resp.ok;
        } catch (e) {
            return false;
        }
    }

    document.querySelectorAll('.segment-row').forEach(function (row) {
        var segIdx = parseInt(row.dataset.segmentIndex);
        var contentDiv = row.querySelector('.segment-content');
        var editTextarea = row.querySelector('.segment-content-edit');
        var btnEdit = row.querySelector('.btn-edit');
        var btnSave = row.querySelector('.btn-save');
        var btnCancel = row.querySelector('.btn-cancel');
        var btnLike = row.querySelector('.btn-like');
        var btnDislike = row.querySelector('.btn-dislike');
        var btnComment = row.querySelector('.btn-comment');

        if (btnEdit) {
            btnEdit.addEventListener('click', function () {
                editTextarea.value = contentDiv.textContent;
                row.classList.add('editing');
                editTextarea.focus();
            });
        }

        if (btnSave) {
            btnSave.addEventListener('click', async function () {
                var newContent = editTextarea.value;
                var ok = await patchSegment(segIdx, { content: newContent });
                if (ok) {
                    contentDiv.textContent = newContent;
                    row.classList.remove('editing');
                }
            });
        }

        if (btnCancel) {
            btnCancel.addEventListener('click', function () {
                row.classList.remove('editing');
            });
        }

        if (btnLike) {
            btnLike.addEventListener('click', async function () {
                var isLiked = btnLike.classList.contains('active');
                var newLike = !isLiked;
                var data = { is_like: newLike };
                if (newLike && btnDislike && btnDislike.classList.contains('active-dislike')) {
                    data.is_dislike = false;
                }
                var ok = await patchSegment(segIdx, data);
                if (ok) {
                    btnLike.classList.toggle('active', newLike);
                    if (newLike && btnDislike) {
                        btnDislike.classList.remove('active-dislike');
                    }
                }
            });
        }

        if (btnDislike) {
            btnDislike.addEventListener('click', async function () {
                var isDisliked = btnDislike.classList.contains('active-dislike');
                var newDislike = !isDisliked;
                var data = { is_dislike: newDislike };
                if (newDislike && btnLike && btnLike.classList.contains('active')) {
                    data.is_like = false;
                }
                var ok = await patchSegment(segIdx, data);
                if (ok) {
                    btnDislike.classList.toggle('active-dislike', newDislike);
                    if (newDislike && btnLike) {
                        btnLike.classList.remove('active');
                    }
                }
            });
        }

        if (btnComment) {
            btnComment.addEventListener('click', function () {
                currentRow = row;
                commentTextarea.value = row.dataset.comment || '';
                commentOverlay.classList.remove('hidden');
            });
        }
    });

    if (commentOverlay) {
        var saveBtn = document.getElementById('segment-comment-save');
        var resetBtn = document.getElementById('segment-comment-reset');

        saveBtn.addEventListener('click', async function () {
            if (!currentRow) return;
            var segIdx = parseInt(currentRow.dataset.segmentIndex);
            var comment = commentTextarea.value.trim();
            var ok = await patchSegment(segIdx, { comment: comment || null });
            if (ok) {
                var btnComment = currentRow.querySelector('.btn-comment');
                if (btnComment) btnComment.classList.toggle('active', !!comment);
                currentRow.dataset.comment = comment;
                commentOverlay.classList.add('hidden');
                currentRow = null;
            }
        });

        resetBtn.addEventListener('click', async function () {
            if (!currentRow) return;
            var segIdx = parseInt(currentRow.dataset.segmentIndex);
            var ok = await patchSegment(segIdx, { comment: null });
            if (ok) {
                var btnComment = currentRow.querySelector('.btn-comment');
                if (btnComment) btnComment.classList.remove('active');
                currentRow.dataset.comment = '';
                commentOverlay.classList.add('hidden');
                currentRow = null;
            }
        });

        commentOverlay.addEventListener('click', function (e) {
            if (e.target === commentOverlay) {
                commentOverlay.classList.add('hidden');
                currentRow = null;
            }
        });
    }
})();
