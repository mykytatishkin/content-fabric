/* Analytics page charts with channel toggle */
(function() {
    var el = document.getElementById('analyticsChartData');
    if (!el) return;
    var chartData;
    try { chartData = JSON.parse(el.textContent); } catch(e) { console.error('Bad chart data', e); return; }
    if (typeof Chart === 'undefined') { console.error('Chart.js not loaded'); return; }

    var colors = ['#0ea5e9','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];
    var channelNames = Object.keys(chartData);
    var enabledChannels = {};
    var charts = {};

    // Load saved state from localStorage
    var savedState = null;
    try { savedState = JSON.parse(localStorage.getItem('analytics_channels')); } catch(e) {}

    // Init enabled state: default all on, or restore from localStorage
    channelNames.forEach(function(name) {
        enabledChannels[name] = savedState ? (savedState[name] !== false) : true;
    });

    // Build toggle checkboxes
    var toggleContainer = document.getElementById('channelToggles');
    if (toggleContainer) {
        channelNames.forEach(function(name, i) {
            var color = colors[i % colors.length];
            var label = document.createElement('label');
            label.style.cssText = 'display:flex;align-items:center;gap:0.3rem;font-size:0.8rem;cursor:pointer;user-select:none;';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = enabledChannels[name];
            cb.dataset.channel = name;
            cb.style.accentColor = color;
            cb.addEventListener('change', function() {
                enabledChannels[name] = this.checked;
                saveState();
                rebuildCharts();
            });
            var dot = document.createElement('span');
            dot.style.cssText = 'width:10px;height:10px;border-radius:50%;display:inline-block;background:' + color;
            label.appendChild(cb);
            label.appendChild(dot);
            label.appendChild(document.createTextNode(' ' + name));
            toggleContainer.appendChild(label);
        });
    }

    function saveState() {
        try { localStorage.setItem('analytics_channels', JSON.stringify(enabledChannels)); } catch(e) {}
    }

    // Select All / Deselect All
    window.toggleAllChannels = function(on) {
        channelNames.forEach(function(name) { enabledChannels[name] = on; });
        var cbs = toggleContainer.querySelectorAll('input[type=checkbox]');
        cbs.forEach(function(cb) { cb.checked = on; });
        saveState();
        rebuildCharts();
    };

    function getLabels() {
        for (var name in chartData) {
            if (enabledChannels[name]) return chartData[name].dates;
        }
        // Fallback: first channel
        for (var name in chartData) return chartData[name].dates;
        return [];
    }

    function buildDatasets(metric) {
        var datasets = [];
        var i = 0;
        for (var name in chartData) {
            var ch = chartData[name];
            datasets.push({
                label: name,
                data: ch[metric],
                borderColor: colors[i % colors.length],
                backgroundColor: colors[i % colors.length] + '20',
                tension: 0.3,
                pointRadius: 2,
                borderWidth: 2,
                fill: false,
                hidden: !enabledChannels[name],
            });
            i++;
        }
        return datasets;
    }

    var baseOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: false },
            tooltip: {
                filter: function(item) { return !item.dataset.hidden; },
                callbacks: {
                    label: function(ctx) { return ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString(); }
                }
            }
        },
        scales: {
            x: { grid: { display: false }, ticks: { font: { size: 11 }, maxTicksLimit: 15 } },
            y: { ticks: { font: { size: 11 }, callback: function(v) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v; } } }
        }
    };

    function createChart(canvasId, metric) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        return new Chart(canvas, {
            type: 'line',
            data: { labels: getLabels(), datasets: buildDatasets(metric) },
            options: baseOpts,
        });
    }

    function rebuildCharts() {
        // Update visibility via Chart.js API (no full rebuild needed)
        ['subs', 'views', 'videos'].forEach(function(key) {
            var chart = charts[key];
            if (!chart) return;
            var i = 0;
            for (var name in chartData) {
                chart.setDatasetVisibility(i, enabledChannels[name]);
                i++;
            }
            chart.update();
        });
    }

    var labels = getLabels();
    if (!labels || labels.length === 0) return;

    charts.subs = createChart('subscribersChart', 'subscribers');
    charts.views = createChart('viewsChart', 'views');
    charts.videos = createChart('videosChart', 'videos');

    // Apply initial hidden state
    rebuildCharts();
})();
