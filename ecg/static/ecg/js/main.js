(function () {
    function initHistorySelectAll() {
        const selectAll = document.getElementById("select-all");
        if (selectAll) {
            selectAll.addEventListener("change", function () {
                document.querySelectorAll(".prediction-checkbox").forEach(function (cb) {
                    cb.checked = selectAll.checked;
                });
            });
        }

        document.querySelectorAll(".history-delete-btn").forEach(function (button) {
            button.addEventListener("click", function (event) {
                const message = button.dataset.confirmMessage || "Ban co chac chan?";
                if (!window.confirm(message)) {
                    event.preventDefault();
                }
            });
        });
    }

    function initRealtimeDashboard() {
        const chartCanvas = document.getElementById("ecgChart");
        if (!chartCanvas || typeof window.Chart === "undefined") return;

        const FS = 125;
        const CHUNK_SIZE = 25;
        const CHUNK_INTERVAL = (CHUNK_SIZE / FS) * 1000;
        const DISPLAY_SECONDS = 8;
        const MAX_POINTS = DISPLAY_SECONDS * FS;
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const WS_URL = protocol + "://" + window.location.host + "/ws/ecg/";
        const RECONNECT_DELAY = 3000;

        let ws = null;
        let ecgBuffer = [];
        let rawSignal = null;
        let totalSamples = 0;
        let chunkIndex = 0;
        let samplesStreamed = 0;
        let streamActive = false;
        let streamTimer = null;
        let reconnectTimer = null;
        let isUserStop = false;
        let lastPrediction = null;

        const ctx = chartCanvas.getContext("2d");
        const ecgChart = new window.Chart(ctx, {
            type: "line",
            data: {
                labels: [],
                datasets: [{
                    label: "ECG",
                    data: [],
                    borderColor: "#22c55e",
                    borderWidth: 1.2,
                    pointRadius: 0,
                    tension: 0.15,
                    fill: { target: "origin", above: "rgba(34,197,94,0.04)" }
                }]
            },
            options: {
                animation: false,
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: {
                    x: { display: false },
                    y: { grid: { color: "rgba(148,163,184,.06)" }, ticks: { color: "#475569", font: { size: 10 } } }
                }
            }
        });

        const byId = function (id) { return document.getElementById(id); };
        const wsStatusText = byId("ws-status-text");
        const wsDot = byId("ws-dot");
        const predCard = byId("pred-card");
        const predValue = byId("pred-value");
        const confValue = byId("conf-value");
        const ratioValue = byId("ratio-value");
        const samplesValue = byId("samples-value");
        const streamBadge = byId("stream-badge");
        const progressFill = byId("progress-fill");
        const progressPct = byId("progress-pct");
        const ratioFill = byId("ratio-fill");
        const ratioPctLabel = byId("ratio-pct-label");
        const btnStart = byId("btn-start");
        const btnStop = byId("btn-stop");
        const eventLog = byId("event-log");
        const fileNameDisp = byId("file-name-display");
        const latencyEl = byId("latency-value");
        const fileInput = byId("ecgFileInput");
        const uploadZone = byId("upload-zone");
        const clearLogBtn = byId("clear-log-btn");

        if (!wsStatusText || !wsDot || !btnStart || !btnStop || !eventLog || !fileInput) return;

        function log(msg, cls) {
            const ts = new Date().toLocaleTimeString("vi-VN");
            const div = document.createElement("div");
            div.className = cls || "log-info";
            div.textContent = "[" + ts + "] " + msg;
            eventLog.appendChild(div);
            eventLog.scrollTop = eventLog.scrollHeight;
        }

        function setWsState(state, text) {
            wsDot.className = state;
            wsStatusText.textContent = text;
        }

        function setStreamState(active) {
            streamActive = active;
            btnStart.disabled = active || !rawSignal;
            btnStop.disabled = !active;
            streamBadge.textContent = active ? "STREAMING" : "IDLE";
            streamBadge.style.background = active ? "rgba(56,189,248,.2)" : "rgba(148,163,184,.15)";
            streamBadge.style.color = active ? "#38bdf8" : "var(--text-muted)";
            if (active) setWsState("streaming", "Dang stream...");
            else setWsState("connected", "Da ket noi");
        }

        function stopStreamTimer() {
            if (streamTimer) {
                clearInterval(streamTimer);
                streamTimer = null;
            }
        }

        function sendNextChunk() {
            if (!streamActive || !ws || ws.readyState !== WebSocket.OPEN) {
                stopStreamTimer();
                return;
            }
            if (chunkIndex >= totalSamples) {
                log("Da stream xong toan bo du lieu.", "log-info");
                stopStreamTimer();
                setStreamState(false);
                return;
            }
            const chunk = rawSignal.slice(chunkIndex, chunkIndex + CHUNK_SIZE);
            chunkIndex += chunk.length;
            ws.send(JSON.stringify({ chunk: Array.from(chunk) }));
        }

        function startStreamTimer() {
            if (streamTimer) clearInterval(streamTimer);
            streamTimer = setInterval(sendNextChunk, CHUNK_INTERVAL);
        }

        function connectWebSocket() {
            if (ws && ws.readyState <= 1) return;
            ws = new WebSocket(WS_URL);
            setWsState("", "Dang ket noi...");

            ws.onopen = function () {
                setWsState("connected", "Da ket noi");
                log("WebSocket ket noi thanh cong.", "log-info");
                if (reconnectTimer) {
                    clearTimeout(reconnectTimer);
                    reconnectTimer = null;
                }
                btnStart.disabled = !rawSignal;
            };

            ws.onclose = function () {
                setWsState("disconnected", "Mat ket noi");
                stopStreamTimer();
                if (!isUserStop) {
                    log("Mat ket noi. Thu lai sau " + (RECONNECT_DELAY / 1000) + "s...", "log-warn");
                    reconnectTimer = setTimeout(connectWebSocket, RECONNECT_DELAY);
                }
            };

            ws.onerror = function () { log("Loi WebSocket.", "log-warn"); };
            ws.onmessage = function (ev) {
                const data = JSON.parse(ev.data);
                if (data.error) { log(data.error, "log-warn"); return; }
                if (data.stopped) { log("Server xac nhan dung.", "log-info"); return; }

                const chunk = data.signal || [];
                if (!chunk.length) return;

                ecgBuffer.push.apply(ecgBuffer, chunk);
                if (ecgBuffer.length > MAX_POINTS) ecgBuffer = ecgBuffer.slice(-MAX_POINTS);
                samplesStreamed += chunk.length;

                ecgChart.data.labels = ecgBuffer.map(function (_, i) { return i; });
                ecgChart.data.datasets[0].data = ecgBuffer.slice();

                if (data.prediction) lastPrediction = data;
                const prediction = lastPrediction;
                const isAbnormal = prediction && prediction.prediction === "Abnormal";
                ecgChart.data.datasets[0].borderColor = isAbnormal ? "#ef4444" : "#22c55e";
                ecgChart.update("quiet");

                if (data.prediction) {
                    const ratioPercent = Math.round((data.abnormal_ratio || 0) * 100);
                    const confPercent = Math.round((data.confidence || 0) * 100);

                    samplesValue.textContent = samplesStreamed.toLocaleString("vi-VN");
                    confValue.textContent = confPercent + " %";
                    ratioValue.textContent = ratioPercent + " %";
                    predValue.className = "stat-value " + (isAbnormal ? "abnormal" : "normal");
                    predValue.textContent = isAbnormal ? "Bat thuong" : "Binh thuong";
                    predCard.className = "stat-card h-100 " + (isAbnormal ? "abnormal" : "normal");

                    const ratioColor = ratioPercent > 20 ? "var(--red)" : "var(--green)";
                    ratioFill.style.width = Math.min(ratioPercent, 100) + "%";
                    ratioFill.style.background = ratioColor;
                    ratioPctLabel.textContent = ratioPercent + " %";

                    if (latencyEl && data.latency_ms != null) latencyEl.textContent = data.latency_ms + " ms";
                    if (isAbnormal) log("Canh bao bat thuong - ratio " + ratioPercent + "%, confidence " + confPercent + "%", "log-abnormal");
                } else {
                    samplesValue.textContent = samplesStreamed.toLocaleString("vi-VN");
                }

                if (totalSamples > 0) {
                    const pct = Math.min(100, Math.round((chunkIndex / totalSamples) * 100));
                    progressFill.style.width = pct + "%";
                    progressPct.textContent = pct + " %";
                }
            };
        }

        fileInput.addEventListener("change", function () {
            const file = this.files && this.files[0];
            if (!file) return;
            fileNameDisp.textContent = "File: " + file.name;
            const reader = new FileReader();
            reader.onload = function (e) {
                const lines = String(e.target.result).trim().split("\n");
                rawSignal = lines
                    .map(function (line) { return parseFloat(line.split(",")[0]); })
                    .filter(function (v) { return !Number.isNaN(v); });
                totalSamples = rawSignal.length;
                btnStart.disabled = !ws || ws.readyState !== WebSocket.OPEN;
                log("Da nap " + totalSamples.toLocaleString("vi-VN") + " mau.", "log-info");
            };
            reader.readAsText(file);
        });

        if (uploadZone) {
            uploadZone.addEventListener("click", function () { fileInput.click(); });
        }

        btnStart.addEventListener("click", function () {
            if (!rawSignal || !ws || ws.readyState !== WebSocket.OPEN) return;
            chunkIndex = 0;
            samplesStreamed = 0;
            ecgBuffer = [];
            lastPrediction = null;
            ecgChart.data.labels = [];
            ecgChart.data.datasets[0].data = [];
            ecgChart.data.datasets[0].borderColor = "#22c55e";
            ecgChart.update("quiet");
            progressFill.style.width = "0%";
            progressPct.textContent = "0 %";

            setStreamState(true);
            log("Bat dau stream " + totalSamples.toLocaleString("vi-VN") + " mau.", "log-info");
            startStreamTimer();
        });

        btnStop.addEventListener("click", function () {
            stopStreamTimer();
            setStreamState(false);
            isUserStop = true;
            if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ stop: true }));
            log("Da dung streaming.", "log-warn");
            setTimeout(function () { isUserStop = false; }, 500);
        });

        if (clearLogBtn) clearLogBtn.addEventListener("click", function () { eventLog.innerHTML = ""; });

        connectWebSocket();
    }

    document.addEventListener("DOMContentLoaded", function () {
        initHistorySelectAll();
        initRealtimeDashboard();
    });
})();
