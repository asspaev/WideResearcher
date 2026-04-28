(function () {
    var container = document.getElementById('research-ws-data');
    if (!container) return;

    var RESEARCH_ID = container.dataset.researchId;
    if (!RESEARCH_ID) return;

    var STAGE_ORDER   = JSON.parse(container.dataset.stageOrder);
    var LABELS_ACTIVE = JSON.parse(container.dataset.labelsActive);
    var LABELS_DONE   = JSON.parse(container.dataset.labelsDone);

    var stageTimers  = {};
    var currentStage  = container.dataset.initialStage || 'LAUNCH';
    var currentStatus = 'IN_PROCESS';
    var currentError  = null;
    var stageStartTime = null;
    var timerInterval  = null;
    var isFirstMessage = true;

    var iconActiveEl = document.getElementById('rs-tpl-active');
    var iconCheckEl  = document.getElementById('rs-tpl-check');
    var iconErrorEl  = document.getElementById('rs-tpl-error');
    var iconActive = iconActiveEl ? iconActiveEl.innerHTML : '●';
    var iconCheck  = iconCheckEl  ? iconCheckEl.innerHTML  : '✓';
    var iconError  = iconErrorEl  ? iconErrorEl.innerHTML  : '✗';

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function formatTime(sec) {
        return '<span class="rs-time">(' + sec + ' сек.)</span>';
    }

    function renderStages() {
        var el = document.getElementById('research-stages');
        if (!el) return;

        var currentIdx = STAGE_ORDER.indexOf(currentStage);
        var html = '';

        if (currentStatus === 'IN_PROCESS') {
            var secs = stageTimers[currentStage] || 0;
            html += '<div class="rs-item rs-item--active">'
                  + '<div class="rs-icon rs-icon--spin">' + iconActive + '</div>'
                  + '<span class="rs-label">' + (LABELS_ACTIVE[currentStage] || currentStage) + '</span>'
                  + formatTime(secs)
                  + '</div>';
        } else if (currentStatus === 'ERROR') {
            html += '<div class="rs-item rs-item--error">'
                  + '<div class="rs-icon">' + iconError + '</div>'
                  + '<div class="rs-error-content">'
                  + '<span class="rs-label">' + (LABELS_ACTIVE[currentStage] || currentStage) + '</span>'
                  + (currentError ? '<span class="rs-error-text">' + escapeHtml(currentError) + '</span>' : '')
                  + '</div>'
                  + '</div>';
        }

        for (var i = currentIdx - 1; i >= 0; i--) {
            var stage = STAGE_ORDER[i];
            var depth = currentIdx - 1 - i;
            var depthCls = depth > 0 ? ' rs-item--depth-' + Math.min(depth, 4) : '';
            var timeStr = stageTimers[stage] !== undefined ? formatTime(stageTimers[stage]) : '';
            html += '<div class="rs-item rs-item--done' + depthCls + '">'
                  + '<div class="rs-icon rs-icon--check">' + iconCheck + '</div>'
                  + '<span class="rs-label">' + (LABELS_DONE[stage] || stage) + '</span>'
                  + timeStr
                  + '</div>';
        }

        el.innerHTML = html;
    }

    function startTimer(initialElapsed) {
        stopTimer();
        var elapsed = initialElapsed || 0;
        stageStartTime = Date.now() - elapsed * 1000;
        stageTimers[currentStage] = elapsed;
        timerInterval = setInterval(function () {
            stageTimers[currentStage] = Math.round((Date.now() - stageStartTime) / 1000);
            renderStages();
        }, 1000);
    }

    function stopTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function freezeCurrentStage() {
        if (stageStartTime !== null) {
            stageTimers[currentStage] = Math.round((Date.now() - stageStartTime) / 1000);
        }
        stopTimer();
        stageStartTime = null;
    }

    function onMessage(data) {
        var newStage  = data.stage;
        var newStatus = data.status;
        var newError  = data.error || null;

        var stageChanged = newStage !== currentStage;

        if (!isFirstMessage && stageChanged) {
            freezeCurrentStage();
        }

        if (isFirstMessage && data.timers) {
            stageTimers = data.timers;
        }

        currentStage  = newStage;
        currentStatus = newStatus;
        currentError  = newError;

        if (newStatus === 'IN_PROCESS') {
            if (isFirstMessage || stageChanged) {
                startTimer(isFirstMessage ? (data.active_elapsed || 0) : 0);
            }
        } else {
            freezeCurrentStage();
        }

        isFirstMessage = false;

        renderStages();

        if (newStatus === 'COMPLETE') {
            setTimeout(function () { window.location.reload(); }, 1500);
        } else if (newStatus === 'ERROR') {
            var btn = document.getElementById('rs-restart-btn');
            if (btn) btn.hidden = false;
        }
    }

    renderStages();
    startTimer();

    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/researches/' + RESEARCH_ID;
    var ws = new WebSocket(wsUrl);

    ws.onmessage = function (evt) {
        try { onMessage(JSON.parse(evt.data)); } catch (e) {}
    };
})();
