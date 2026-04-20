/* Date range quick buttons */
function goRange(days, basePath) {
    var to = new Date();
    var from = new Date();
    from.setDate(from.getDate() - days);
    var path = basePath || window.location.pathname;
    window.location.href = path + '?from=' + from.toISOString().slice(0,10) + '&to=' + to.toISOString().slice(0,10);
}

/* Highlight active range button on load */
(function() {
    var params = new URLSearchParams(window.location.search);
    var from = params.get('from'), to = params.get('to');
    if (!from || !to) return;
    // Parse as local dates (avoid timezone issues)
    var parts1 = from.split('-'), parts2 = to.split('-');
    var d1 = new Date(parts1[0], parts1[1]-1, parts1[2]);
    var d2 = new Date(parts2[0], parts2[1]-1, parts2[2]);
    var diff = Math.round((d2 - d1) / 86400000);
    var today = new Date(); today.setHours(0,0,0,0);
    // Only highlight if "to" is today (±1 day)
    if (Math.abs(today - d2) > 86400000 * 1.5) return;
    var btns = document.querySelectorAll('[onclick*="goRange"]');
    btns.forEach(function(btn) {
        var m = btn.getAttribute('onclick').match(/goRange\(\s*(\d+)/);
        if (m && parseInt(m[1]) === diff) {
            btn.style.background = '#E08A3C';
            btn.style.color = '#fff';
        }
    });
})();
