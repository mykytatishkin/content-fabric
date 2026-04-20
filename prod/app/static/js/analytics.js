/* Analytics page charts with channel toggle + upload event markers + daily deltas */
(function() {
    var el = document.getElementById('analyticsChartData');
    if (!el) return;
    var chartData;
    try { chartData = JSON.parse(el.textContent); } catch(e) { return; }
    if (typeof Chart === 'undefined') return;

    var uploadEvents = [];
    var evEl = document.getElementById('uploadEventsData');
    if (evEl) try { uploadEvents = JSON.parse(evEl.textContent) || []; } catch(e) {}

    var eventsByDate = {};
    uploadEvents.forEach(function(ev) {
        if (!eventsByDate[ev.date]) eventsByDate[ev.date] = [];
        eventsByDate[ev.date].push(ev);
    });
    var eventDates = Object.keys(eventsByDate);

    var colors = ['#0ea5e9','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];
    var channelNames = Object.keys(chartData);
    var enabledChannels = {};
    var charts = {};

    var savedState = null;
    try { savedState = JSON.parse(localStorage.getItem('analytics_channels')); } catch(e) {}
    channelNames.forEach(function(name) {
        enabledChannels[name] = savedState ? (savedState[name] !== false) : true;
    });

    var toggleContainer = document.getElementById('channelToggles');
    if (toggleContainer) {
        channelNames.forEach(function(name, i) {
            var color = colors[i % colors.length];
            var label = document.createElement('label');
            label.style.cssText = 'display:flex;align-items:center;gap:0.3rem;font-size:0.8rem;cursor:pointer;user-select:none;';
            var cb = document.createElement('input');
            cb.type = 'checkbox'; cb.checked = enabledChannels[name]; cb.style.accentColor = color;
            cb.addEventListener('change', function() { enabledChannels[name] = this.checked; saveState(); rebuildCharts(); });
            var dot = document.createElement('span');
            dot.style.cssText = 'width:10px;height:10px;border-radius:50%;display:inline-block;background:' + color;
            label.appendChild(cb); label.appendChild(dot);
            label.appendChild(document.createTextNode(' ' + name));
            toggleContainer.appendChild(label);
        });
    }

    function saveState() { try { localStorage.setItem('analytics_channels', JSON.stringify(enabledChannels)); } catch(e) {} }
    window.toggleAllChannels = function(on) {
        channelNames.forEach(function(name) { enabledChannels[name] = on; });
        toggleContainer.querySelectorAll('input[type=checkbox]').forEach(function(cb) { cb.checked = on; });
        saveState(); rebuildCharts();
    };

    function getLabels() {
        for (var name in chartData) if (enabledChannels[name]) return chartData[name].dates;
        for (var name in chartData) return chartData[name].dates;
        return [];
    }
    function nd(d) { return String(d).substring(0, 10); }

    function buildDatasets(metric, type) {
        var datasets = [], i = 0;
        for (var name in chartData) {
            var ch = chartData[name];
            var isBar = type === 'bar';
            datasets.push({
                label: name, data: ch[metric],
                borderColor: colors[i % colors.length],
                backgroundColor: isBar ? colors[i % colors.length] + '90' : colors[i % colors.length] + '20',
                tension: 0.3, pointRadius: isBar ? 0 : 2, borderWidth: isBar ? 0 : 2,
                fill: !isBar, hidden: !enabledChannels[name],
                barPercentage: 0.6, categoryPercentage: 0.8,
            });
            i++;
        }
        return datasets;
    }

    // Upload marker plugin
    var uploadMarkerPlugin = {
        id: 'uploadMarkers',
        afterDraw: function(chart) {
            if (!eventDates.length) return;
            var xAxis = chart.scales.x, yAxis = chart.scales.y, ctx = chart.ctx;
            var labelDates = (chart.data.labels || []).map(nd);
            eventDates.forEach(function(eventDate) {
                var idx = labelDates.indexOf(eventDate);
                if (idx === -1) return;
                var x = xAxis.getPixelForValue(idx);
                if (x < xAxis.left || x > xAxis.right) return;
                ctx.save();
                ctx.beginPath(); ctx.setLineDash([4, 4]);
                ctx.strokeStyle = 'rgba(224,138,60,0.5)'; ctx.lineWidth = 1.5;
                ctx.moveTo(x, yAxis.top); ctx.lineTo(x, yAxis.bottom); ctx.stroke();
                ctx.setLineDash([]); ctx.fillStyle = '#E08A3C';
                ctx.beginPath(); ctx.moveTo(x-4, yAxis.top); ctx.lineTo(x+4, yAxis.top);
                ctx.lineTo(x, yAxis.top+8); ctx.closePath(); ctx.fill();
                var count = eventsByDate[eventDate].length;
                if (count > 1) { ctx.font = '9px sans-serif'; ctx.textAlign = 'center'; ctx.fillText(count+'x', x, yAxis.top+18); }
                ctx.restore();
            });
        }
    };
    Chart.register(uploadMarkerPlugin);

    function makeOpts(isBar) {
        return {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    filter: function(item) { return !item.dataset.hidden; },
                    callbacks: {
                        label: function(ctx) {
                            var v = ctx.parsed.y;
                            var prefix = v > 0 ? '+' : '';
                            return ctx.dataset.label + ': ' + prefix + v.toLocaleString();
                        },
                        afterBody: function(items) {
                            if (!items.length) return '';
                            var dateStr = nd((items[0].chart.data.labels || [])[items[0].dataIndex]);
                            var events = eventsByDate[dateStr];
                            if (!events || !events.length) return '';
                            var lines = ['', '📤 Uploads:'];
                            events.forEach(function(ev) { lines.push('  ' + ev.channel + ': ' + (ev.title||'').substring(0,40)); });
                            return lines;
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { font: { size: 11 }, maxTicksLimit: 15,
                    callback: function(val) { return nd(this.getLabelForValue(val)).substring(5); }
                }},
                y: { ticks: { font: { size: 11 }, callback: function(v) {
                    var prefix = v > 0 ? '+' : '';
                    return v >= 1e6 ? prefix+(v/1e6).toFixed(1)+'M' : v >= 1e3 ? prefix+(v/1e3).toFixed(0)+'K' : (isBar ? prefix : '') + v;
                }}}
            }
        };
    }

    function createChart(canvasId, metric, type) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        return new Chart(canvas, {
            type: type || 'line',
            data: { labels: getLabels(), datasets: buildDatasets(metric, type) },
            options: makeOpts(type === 'bar'),
        });
    }

    function rebuildCharts() {
        Object.keys(charts).forEach(function(key) {
            var chart = charts[key]; if (!chart) return;
            var i = 0;
            for (var name in chartData) { chart.setDatasetVisibility(i, enabledChannels[name]); i++; }
            chart.update();
        });
    }

    var labels = getLabels();
    if (!labels || labels.length === 0) return;

    charts.subsDelta = createChart('subsDeltaChart', 'subs_delta', 'bar');
    charts.viewsDelta = createChart('viewsDeltaChart', 'views_delta', 'bar');
    charts.subs = createChart('subscribersChart', 'subscribers', 'line');
    charts.views = createChart('viewsChart', 'views', 'line');

    rebuildCharts();
})();
