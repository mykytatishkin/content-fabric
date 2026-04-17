/* Channel stats page charts */
(function() {
    var el = document.getElementById('channelChartData');
    if (!el) return;
    var data;
    try { data = JSON.parse(el.textContent); } catch(e) { console.error('Bad chart data', e); return; }
    if (typeof Chart === 'undefined') { console.error('Chart.js not loaded'); return; }

    var baseOpts = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { display: false },
            tooltip: {
                callbacks: {
                    label: function(ctx) { return ctx.parsed.y.toLocaleString(); }
                }
            }
        },
        scales: {
            x: { grid: { display: false }, ticks: { font: { size: 11 }, maxTicksLimit: 15 } },
            y: {
                beginAtZero: false,
                ticks: { font: { size: 11 }, callback: function(v) { return v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? (v/1e3).toFixed(1)+'K' : v; } }
            }
        }
    };

    function makeChart(id, label, dataArr, color) {
        var canvas = document.getElementById(id);
        if (!canvas) return;
        var chartType = dataArr.length <= 1 ? 'bar' : 'line';
        new Chart(canvas, {
            type: chartType,
            data: {
                labels: data.dates,
                datasets: [{
                    label: label,
                    data: dataArr,
                    borderColor: color,
                    backgroundColor: chartType === 'bar' ? color + '40' : color + '15',
                    tension: 0.3, pointRadius: 3, borderWidth: 2, fill: true,
                    barPercentage: 0.3,
                }]
            },
            options: baseOpts,
        });
    }

    if (data.dates && data.dates.length > 0) {
        makeChart('subsChart', 'Subscribers', data.subscribers, '#8b5cf6');
        makeChart('viewsChart', 'Views', data.views, '#0ea5e9');
        makeChart('videosChart', 'Videos', data.videos, '#10b981');
    }
})();
