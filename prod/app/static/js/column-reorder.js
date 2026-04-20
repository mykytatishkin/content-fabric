/* Table columns: reorder (drag), resize (drag edge), hide/show (menu).
   Saves state per page in localStorage.
   Works with all tables inside .table-wrap. */
(function() {
    var pathKey = location.pathname.replace(/\//g, '_');
    var orderKey = 'col_order_' + pathKey;
    var widthKey = 'col_width_' + pathKey;
    var hiddenKey = 'col_hidden_' + pathKey;

    document.querySelectorAll('.table-wrap').forEach(function(wrap) {
        var table = wrap.querySelector('table');
        if (!table) return;
        var thead = table.querySelector('thead');
        var tbody = table.querySelector('tbody');
        if (!thead || !tbody) return;

        var headerRow = thead.querySelector('tr');
        var ths = Array.prototype.slice.call(headerRow.children);
        var colCount = ths.length;

        // Fix table layout for resizable columns
        table.style.tableLayout = 'fixed';

        // Collect column names for toggle menu
        var colNames = [];
        ths.forEach(function(th, i) {
            th.setAttribute('data-orig-idx', i);
            colNames.push(th.textContent.trim() || 'Column ' + (i + 1));
        });
        tbody.querySelectorAll('tr').forEach(function(row) {
            Array.prototype.slice.call(row.children).forEach(function(td, i) {
                td.setAttribute('data-orig-idx', i);
            });
        });

        // ── Restore saved order ──
        var savedOrder = null;
        try { savedOrder = JSON.parse(localStorage.getItem(orderKey)); } catch(e) {}
        if (savedOrder && savedOrder.length === colCount) {
            applyOrder(savedOrder, table, headerRow);
        }

        // ── Restore saved widths ──
        var savedWidths = null;
        try { savedWidths = JSON.parse(localStorage.getItem(widthKey)); } catch(e) {}
        if (savedWidths) {
            headerRow.querySelectorAll('th').forEach(function(th) {
                var origIdx = th.getAttribute('data-orig-idx');
                if (savedWidths[origIdx]) th.style.width = savedWidths[origIdx] + 'px';
            });
        }

        // ── Restore hidden columns ──
        var hiddenCols = {};
        try { hiddenCols = JSON.parse(localStorage.getItem(hiddenKey)) || {}; } catch(e) {}
        applyHidden(hiddenCols, table);

        // ── Resize handles ──
        headerRow.querySelectorAll('th').forEach(function(th) {
            addResizeHandle(th, table);
        });

        // ── Drag to reorder ──
        headerRow.querySelectorAll('th').forEach(function(th) {
            th.setAttribute('draggable', 'true');

            th.addEventListener('dragstart', function(e) {
                if (table.classList.contains('col-resizing')) { e.preventDefault(); return; }
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
                saveOrder(headerRow);
            });
        });

        // ── Column toggle button + menu ──
        var toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-sm col-toggle-btn';
        toggleBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="8" cy="6" r="1.5" fill="currentColor"/><circle cx="16" cy="12" r="1.5" fill="currentColor"/><circle cx="10" cy="18" r="1.5" fill="currentColor"/></svg> Columns';
        toggleBtn.style.cssText = 'display:inline-flex;align-items:center;gap:4px;color:#5c5c60;margin-bottom:8px;position:relative;';

        var menu = document.createElement('div');
        menu.className = 'col-toggle-menu';
        menu.style.display = 'none';

        colNames.forEach(function(name, i) {
            var label = document.createElement('label');
            label.className = 'col-toggle-item';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = !hiddenCols[i];
            cb.dataset.colIdx = i;
            cb.addEventListener('change', function() {
                if (this.checked) {
                    delete hiddenCols[i];
                } else {
                    hiddenCols[i] = true;
                }
                applyHidden(hiddenCols, table);
                try { localStorage.setItem(hiddenKey, JSON.stringify(hiddenCols)); } catch(e) {}
            });
            label.appendChild(cb);
            label.appendChild(document.createTextNode(' ' + name));
            menu.appendChild(label);
        });

        // Reset button
        var resetBtn = document.createElement('button');
        resetBtn.textContent = 'Reset all';
        resetBtn.className = 'col-toggle-reset';
        resetBtn.addEventListener('click', function() {
            localStorage.removeItem(orderKey);
            localStorage.removeItem(widthKey);
            localStorage.removeItem(hiddenKey);
            location.reload();
        });
        menu.appendChild(resetBtn);

        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            var isOpen = menu.style.display !== 'none';
            menu.style.display = isOpen ? 'none' : 'block';
        });

        document.addEventListener('click', function(e) {
            if (!menu.contains(e.target) && e.target !== toggleBtn) {
                menu.style.display = 'none';
            }
        });

        var btnWrap = document.createElement('div');
        btnWrap.style.cssText = 'position:relative;display:inline-block;';
        btnWrap.appendChild(toggleBtn);
        btnWrap.appendChild(menu);
        wrap.parentNode.insertBefore(btnWrap, wrap);
    });

    function addResizeHandle(th, table) {
        var handle = document.createElement('div');
        handle.className = 'col-resize-handle';
        th.appendChild(handle);

        var startX, startW, thEl, tableEl;

        handle.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            thEl = th;
            tableEl = table;
            startX = e.pageX;
            startW = th.offsetWidth;
            table.classList.add('col-resizing');
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });

        function onMouseMove(e) {
            thEl.style.width = Math.max(40, startW + (e.pageX - startX)) + 'px';
        }

        function onMouseUp() {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            tableEl.classList.remove('col-resizing');
            var widths = {};
            tableEl.querySelector('thead tr').querySelectorAll('th').forEach(function(h) {
                widths[h.getAttribute('data-orig-idx')] = h.offsetWidth;
            });
            try { localStorage.setItem(widthKey, JSON.stringify(widths)); } catch(e) {}
        }
    }

    function getColIndex(th) {
        return Array.prototype.indexOf.call(th.parentNode.children, th);
    }

    function moveColumn(table, fromIdx, toIdx) {
        table.querySelectorAll('tr').forEach(function(row) {
            var cells = Array.prototype.slice.call(row.children);
            if (fromIdx >= cells.length || toIdx >= cells.length) return;
            var cell = cells[fromIdx];
            var ref = cells[toIdx];
            row.insertBefore(cell, fromIdx < toIdx ? ref.nextSibling : ref);
        });
    }

    function saveOrder(headerRow) {
        var newOrder = [];
        headerRow.querySelectorAll('th').forEach(function(h) {
            newOrder.push(parseInt(h.getAttribute('data-orig-idx')));
        });
        try { localStorage.setItem(orderKey, JSON.stringify(newOrder)); } catch(e) {}
    }

    function applyOrder(order, table, headerRow) {
        var tbody = table.querySelector('tbody');
        var bodyRows = tbody ? tbody.querySelectorAll('tr') : [];
        order.forEach(function(origIdx) {
            var th = headerRow.querySelector('th[data-orig-idx="' + origIdx + '"]');
            if (th) headerRow.appendChild(th);
        });
        bodyRows.forEach(function(row) {
            order.forEach(function(origIdx) {
                var td = row.querySelector('[data-orig-idx="' + origIdx + '"]');
                if (td) row.appendChild(td);
            });
        });
    }

    function applyHidden(hiddenCols, table) {
        table.querySelectorAll('tr').forEach(function(row) {
            Array.prototype.slice.call(row.children).forEach(function(cell) {
                var idx = cell.getAttribute('data-orig-idx');
                if (idx !== null && hiddenCols[idx]) {
                    cell.style.display = 'none';
                } else {
                    cell.style.display = '';
                }
            });
        });
    }

    function clearHighlights(headerRow) {
        headerRow.querySelectorAll('.col-drop-target').forEach(function(el) {
            el.classList.remove('col-drop-target');
        });
    }

    // CSS
    var style = document.createElement('style');
    style.textContent =
        '.col-drop-target{background:rgba(224,138,60,0.15)!important;box-shadow:inset 0 0 0 2px rgba(224,138,60,0.4);}' +
        '.col-dragging td,.col-dragging th{transition:none;}' +
        'th[draggable]{position:relative;cursor:grab;}' +
        'th[draggable]:active{cursor:grabbing;}' +
        '.col-resizing th[draggable]{cursor:col-resize!important;}' +
        '.col-resizing{user-select:none;-webkit-user-select:none;}' +
        '.col-resize-handle{position:absolute;top:0;right:0;width:5px;height:100%;cursor:col-resize;z-index:1;}' +
        '.col-resize-handle:hover,.col-resizing .col-resize-handle{background:rgba(224,138,60,0.4);}' +
        '.col-toggle-menu{position:absolute;top:100%;left:0;background:#fff;border:1px solid rgba(0,0,0,0.1);border-radius:12px;padding:8px 4px;min-width:180px;z-index:50;box-shadow:0 8px 24px rgba(0,0,0,0.12);max-height:320px;overflow-y:auto;}' +
        '.col-toggle-item{display:flex;align-items:center;gap:6px;padding:5px 10px;font-size:12px;cursor:pointer;border-radius:6px;color:#1d1d1f;white-space:nowrap;}' +
        '.col-toggle-item:hover{background:rgba(0,0,0,0.04);}' +
        '.col-toggle-item input{accent-color:#E08A3C;}' +
        '.col-toggle-reset{display:block;width:calc(100% - 8px);margin:6px 4px 2px;padding:5px 10px;font-size:11px;color:#858587;background:none;border:1px solid rgba(0,0,0,0.08);border-radius:6px;cursor:pointer;text-align:center;}' +
        '.col-toggle-reset:hover{background:rgba(0,0,0,0.04);color:#1d1d1f;}' +
        '.col-toggle-btn:hover{color:#1d1d1f!important;}';
    document.head.appendChild(style);
})();
