/* Sortable tables: click any <th> with data-sort to sort rows.
   data-sort values: "string" (default), "number", "date"
   Adds ▲/▼ indicator to active column. */
(function() {
    document.addEventListener('click', function(e) {
        var th = e.target.closest('th[data-sort]');
        if (!th) return;
        var table = th.closest('table');
        if (!table) return;
        var tbody = table.querySelector('tbody');
        if (!tbody) return;

        var colIdx = Array.prototype.indexOf.call(th.parentNode.children, th);
        var sortType = th.getAttribute('data-sort') || 'string';
        var isAsc = th.getAttribute('data-dir') !== 'asc';

        // Reset all headers in this table
        var headers = th.parentNode.querySelectorAll('th[data-sort]');
        for (var i = 0; i < headers.length; i++) {
            headers[i].removeAttribute('data-dir');
            // Remove old arrow
            var arrow = headers[i].querySelector('.sort-arrow');
            if (arrow) arrow.remove();
        }

        th.setAttribute('data-dir', isAsc ? 'asc' : 'desc');
        var arrowSpan = document.createElement('span');
        arrowSpan.className = 'sort-arrow';
        arrowSpan.style.cssText = 'margin-left:4px;font-size:0.7em;opacity:0.7;';
        arrowSpan.textContent = isAsc ? '\u25B2' : '\u25BC';
        th.appendChild(arrowSpan);

        var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
        rows.sort(function(a, b) {
            var cellA = a.children[colIdx];
            var cellB = b.children[colIdx];
            if (!cellA || !cellB) return 0;
            var valA = (cellA.getAttribute('data-val') || cellA.textContent).trim();
            var valB = (cellB.getAttribute('data-val') || cellB.textContent).trim();

            if (sortType === 'number') {
                var nA = parseFloat(valA.replace(/[^0-9.\-]/g, '')) || 0;
                var nB = parseFloat(valB.replace(/[^0-9.\-]/g, '')) || 0;
                return isAsc ? nA - nB : nB - nA;
            }
            if (sortType === 'date') {
                var dA = new Date(valA) || 0;
                var dB = new Date(valB) || 0;
                return isAsc ? dA - dB : dB - dA;
            }
            // string
            return isAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        });

        for (var j = 0; j < rows.length; j++) {
            tbody.appendChild(rows[j]);
        }
    });

    // Add cursor pointer to sortable headers
    var style = document.createElement('style');
    style.textContent = 'th[data-sort]{cursor:pointer;user-select:none;}th[data-sort]:hover{background:#eef2f7;}';
    document.head.appendChild(style);
})();
