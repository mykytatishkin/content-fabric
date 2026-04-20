/* Draggable table columns: drag any <th> to reorder columns.
   Saves column order per page in localStorage.
   Works with all tables inside .table-wrap. */
(function() {
    var storageKey = 'col_order_' + location.pathname.replace(/\//g, '_');

    document.querySelectorAll('.table-wrap table').forEach(function(table) {
        var thead = table.querySelector('thead');
        var tbody = table.querySelector('tbody');
        if (!thead || !tbody) return;

        var headerRow = thead.querySelector('tr');
        var ths = Array.prototype.slice.call(headerRow.children);
        var colCount = ths.length;

        // Restore saved order
        var saved = null;
        try { saved = JSON.parse(localStorage.getItem(storageKey)); } catch(e) {}
        if (saved && saved.length === colCount) {
            applyOrder(saved, table, headerRow);
        }

        // Make headers draggable
        ths.forEach(function(th, i) {
            th.setAttribute('draggable', 'true');
            th.style.cursor = 'grab';

            th.addEventListener('dragstart', function(e) {
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', getColIndex(th));
                th.style.opacity = '0.5';
                table.classList.add('col-dragging');
            });

            th.addEventListener('dragend', function() {
                th.style.opacity = '';
                table.classList.remove('col-dragging');
                clearHighlights(headerRow);
            });

            th.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                clearHighlights(headerRow);
                th.classList.add('col-drop-target');
            });

            th.addEventListener('dragleave', function() {
                th.classList.remove('col-drop-target');
            });

            th.addEventListener('drop', function(e) {
                e.preventDefault();
                th.classList.remove('col-drop-target');
                var fromIdx = parseInt(e.dataTransfer.getData('text/plain'));
                var toIdx = getColIndex(th);
                if (fromIdx === toIdx || isNaN(fromIdx)) return;

                moveColumn(table, fromIdx, toIdx);

                // Save order
                var newOrder = [];
                var newThs = headerRow.querySelectorAll('th');
                newThs.forEach(function(h) {
                    newOrder.push(parseInt(h.getAttribute('data-orig-idx')));
                });
                try { localStorage.setItem(storageKey, JSON.stringify(newOrder)); } catch(e) {}
            });
        });

        // Set original indices
        ths.forEach(function(th, i) {
            if (!th.hasAttribute('data-orig-idx')) {
                th.setAttribute('data-orig-idx', i);
            }
        });

        // Also set orig indices on td cells
        var rows = tbody.querySelectorAll('tr');
        rows.forEach(function(row) {
            Array.prototype.slice.call(row.children).forEach(function(td, i) {
                if (!td.hasAttribute('data-orig-idx')) {
                    td.setAttribute('data-orig-idx', i);
                }
            });
        });
    });

    function getColIndex(th) {
        return Array.prototype.indexOf.call(th.parentNode.children, th);
    }

    function moveColumn(table, fromIdx, toIdx) {
        var rows = table.querySelectorAll('tr');
        rows.forEach(function(row) {
            var cells = Array.prototype.slice.call(row.children);
            if (fromIdx >= cells.length || toIdx >= cells.length) return;
            var cell = cells[fromIdx];
            var ref = cells[toIdx];
            if (fromIdx < toIdx) {
                row.insertBefore(cell, ref.nextSibling);
            } else {
                row.insertBefore(cell, ref);
            }
        });
    }

    function applyOrder(order, table, headerRow) {
        // Set data-orig-idx before reordering
        var ths = Array.prototype.slice.call(headerRow.children);
        ths.forEach(function(th, i) { th.setAttribute('data-orig-idx', i); });

        var tbody = table.querySelector('tbody');
        var bodyRows = tbody ? tbody.querySelectorAll('tr') : [];
        bodyRows.forEach(function(row) {
            Array.prototype.slice.call(row.children).forEach(function(td, i) {
                td.setAttribute('data-orig-idx', i);
            });
        });

        // Reorder header
        order.forEach(function(origIdx) {
            var th = headerRow.querySelector('th[data-orig-idx="' + origIdx + '"]');
            if (th) headerRow.appendChild(th);
        });

        // Reorder body rows
        bodyRows.forEach(function(row) {
            order.forEach(function(origIdx) {
                var td = row.querySelector('[data-orig-idx="' + origIdx + '"]');
                if (td) row.appendChild(td);
            });
        });
    }

    function clearHighlights(headerRow) {
        headerRow.querySelectorAll('.col-drop-target').forEach(function(el) {
            el.classList.remove('col-drop-target');
        });
    }

    // CSS for drop target highlight
    var style = document.createElement('style');
    style.textContent = '.col-drop-target{background:rgba(224,138,60,0.15)!important;box-shadow:inset 0 0 0 2px rgba(224,138,60,0.4);}' +
        '.col-dragging td,.col-dragging th{transition:none;}' +
        'th[draggable]{position:relative;}' +
        'th[draggable]:active{cursor:grabbing;}';
    document.head.appendChild(style);
})();
