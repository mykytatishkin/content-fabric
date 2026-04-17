/* Analytics page charts */
(function() {
    var el = document.getElementById('analyticsChartData');
    if (!el) return;
    var chartData;
    try { chartData = JSON.parse(el.textContent); } catch(e) { console.error('Bad chart data', e); return; }
    if (typeof Chart === 'undefined') { console.error('Chart.js not loaded'); return; }

    var colors = ['#0ea5e9','#f59e0b','#10b981','#ef4444','#8b5cf6','#ec4899','#14b8a6','#f97316','#6366f1','#84cc16'];

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
            });
            i++;
        }
        return datasets;
    }

    function getLabels() {
        for (var name in chartData) return chartData[name].dates;
        return [];
    }

    var baseOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 12, padding: 15, font: { size: 12 } } },
            tooltip: {
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

    var labels = getLabels();
    if (!labels || labels.length === 0) return;

    new Chart(document.getElementById('subscribersChart'), {
        type: 'line',
        data: { labels: labels, datasets: buildDatasets('subscribers') },
        options: baseOpts,
    });

    new Chart(document.getElementById('viewsChart'), {
        type: 'line',
        data: { labels: labels, datasets: buildDatasets('views') },
        options: baseOpts,
    });

    new Chart(document.getElementById('videosChart'), {
        type: 'line',
        data: { labels: labels, datasets: buildDatasets('videos') },
        options: baseOpts,
    });
})();
