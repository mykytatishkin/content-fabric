/* Date range quick buttons */
function goRange(days, basePath) {
    var to = new Date();
    var from = new Date();
    from.setDate(from.getDate() - days);
    var path = basePath || window.location.pathname;
    window.location.href = path + '?from=' + from.toISOString().slice(0,10) + '&to=' + to.toISOString().slice(0,10);
}
