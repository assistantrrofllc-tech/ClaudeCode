/* CrewLedger Dashboard — Core JavaScript */

// ── Permissions (overridden by page-level scripts when available) ───
if (typeof CAN_EDIT === 'undefined') var CAN_EDIT = true;

// ── Receipt Image Modal ─────────────────────────────────

var _currentReceiptId = null;
var _currentReceiptData = null;
var _autoEditOnLoad = false;

function openReceiptModal(receiptId) {
    var modal = document.getElementById('receipt-modal');
    var img = document.getElementById('modal-receipt-image');
    var details = document.getElementById('modal-receipt-details');
    var footer = document.getElementById('modal-receipt-footer');

    _currentReceiptId = receiptId;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    details.innerHTML = '<div class="loading">Loading...</div>';
    if (footer) footer.innerHTML = '';
    img.src = '';

    fetch('/api/receipts/' + receiptId)
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            _currentReceiptData = data;

            // Set image
            if (data.image_url) {
                img.src = data.image_url;
                img.style.display = 'block';
            } else {
                img.style.display = 'none';
            }

            // Build details panel
            var html = '<h3>' + escapeHtml(data.vendor_name || 'Unknown Vendor') + '</h3>';
            html += '<div class="detail-grid">';
            html += detailField('Employee', data.employee_name);
            html += detailField('Date', formatDate(data.purchase_date));
            html += detailField('Project', data.project_name);
            html += detailField('Status', '<span class="badge badge--' + (data.status || '') + '">' + (data.status || '?') + '</span>');
            html += detailField('Subtotal', formatMoney(data.subtotal));
            html += detailField('Tax', formatMoney(data.tax));
            html += detailField('Total', '<strong>' + formatMoney(data.total) + '</strong>');
            html += detailField('Payment', data.payment_method);
            if (data.flag_reason) {
                html += detailField('Flag Reason', '<span style="color:#dc2626">' + escapeHtml(data.flag_reason) + '</span>');
            }
            html += '</div>';

            // Notes section
            html += '<div class="notes-section">';
            html += '<label class="detail-label">Notes</label>';
            html += '<textarea id="modal-notes" class="notes-input" placeholder="Add notes...">' + escapeHtml(data.notes || '') + '</textarea>';
            html += '<button class="btn btn--small btn--secondary" onclick="saveNotes(' + receiptId + ')">Save Notes</button>';
            html += '<span id="notes-msg" style="margin-left:8px;font-size:12px;"></span>';
            html += '</div>';

            // Line items
            if (data.line_items && data.line_items.length > 0) {
                html += '<table class="line-items-table">';
                html += '<thead><tr><th>Item</th><th>Qty</th><th class="amount">Price</th></tr></thead>';
                html += '<tbody>';
                for (var i = 0; i < data.line_items.length; i++) {
                    var item = data.line_items[i];
                    html += '<tr>';
                    html += '<td>' + escapeHtml(item.item_name || '?') + '</td>';
                    html += '<td>' + (item.quantity || 1) + '</td>';
                    html += '<td class="amount">' + formatMoney(item.extended_price) + '</td>';
                    html += '</tr>';
                }
                html += '</tbody></table>';
            }

            details.innerHTML = html;

            // Auto-open edit form if requested via quick edit
            if (_autoEditOnLoad) {
                _autoEditOnLoad = false;
                setTimeout(function() { toggleEditForm(receiptId); }, 50);
            }

            // Footer with edit/history/delete buttons
            if (footer) {
                var isHidden = (data.status === 'deleted' || data.status === 'duplicate');
                var btns = ' <button class="btn btn--small btn--secondary" onclick="showEditHistory(' + receiptId + ')">Edit History</button>';
                if (CAN_EDIT) {
                    btns = '<button class="btn btn--small btn--secondary" onclick="toggleEditForm(' + receiptId + ')">Edit Receipt</button>' + btns;
                    if (isHidden) {
                        btns += ' <button class="btn btn--small btn--success" onclick="restoreReceipt(' + receiptId + ')">Restore</button>';
                    } else {
                        if (data.status === 'pending' || data.status === 'flagged') {
                            btns += ' <button class="btn btn--small btn--success" onclick="confirmReceipt(' + receiptId + ')">Confirm</button>';
                        }
                        btns += ' <button class="btn btn--small btn--secondary" onclick="markDuplicate(' + receiptId + ')">Mark Duplicate</button>';
                        btns += ' <button class="btn btn--small btn--danger" onclick="deleteReceipt(' + receiptId + ')">Delete</button>';
                    }
                }
                footer.innerHTML = btns;
            }
        })
        .catch(function(err) {
            details.innerHTML = '<div class="loading">Failed to load receipt details.</div>';
        });
}

function closeReceiptModal() {
    var modal = document.getElementById('receipt-modal');
    modal.style.display = 'none';
    document.body.style.overflow = '';
    _currentReceiptId = null;
    _currentReceiptData = null;
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeReceiptModal();
});


// ── Notes ───────────────────────────────────────────────

function saveNotes(receiptId) {
    var notes = document.getElementById('modal-notes').value;
    var msg = document.getElementById('notes-msg');
    msg.innerHTML = '<span style="color:#6b7280;">Saving...</span>';

    fetch('/api/receipts/' + receiptId + '/notes', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({notes: notes}),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(d) {
        if (d.status === 'updated') {
            msg.innerHTML = '<span style="color:#16a34a;">Saved</span>';
            setTimeout(function() { msg.innerHTML = ''; }, 2000);
        } else {
            msg.innerHTML = '<span style="color:#dc2626;">' + (d.error || 'Failed') + '</span>';
        }
    });
}


// ── Receipt Editing ─────────────────────────────────────

var _cachedCategories = null;
var _cachedEmployees = null;

function _loadCategories(callback) {
    if (_cachedCategories) return callback(_cachedCategories);
    fetch('/api/categories?active=1')
        .then(function(r) { return r.json(); })
        .then(function(cats) { _cachedCategories = cats; callback(cats); });
}

function _loadEmployees(callback) {
    if (_cachedEmployees) return callback(_cachedEmployees);
    fetch('/api/employees')
        .then(function(r) { return r.json(); })
        .then(function(emps) {
            _cachedEmployees = emps.filter(function(e) { return e.is_active; });
            callback(_cachedEmployees);
        });
}

function _buildCategorySelect(id, selectedId) {
    var html = '<select id="' + id + '"><option value="">— Select —</option>';
    if (_cachedCategories) {
        for (var i = 0; i < _cachedCategories.length; i++) {
            var c = _cachedCategories[i];
            var sel = (c.id == selectedId) ? ' selected' : '';
            html += '<option value="' + c.id + '"' + sel + '>' + escapeHtml(c.name) + '</option>';
        }
    }
    html += '</select>';
    return html;
}

function _buildEmployeeSelect(id, selectedId) {
    var html = '<select id="' + id + '">';
    if (_cachedEmployees) {
        for (var i = 0; i < _cachedEmployees.length; i++) {
            var e = _cachedEmployees[i];
            var name = e.full_name || e.first_name;
            var sel = (e.id == selectedId) ? ' selected' : '';
            html += '<option value="' + e.id + '"' + sel + '>' + escapeHtml(name) + '</option>';
        }
    }
    html += '</select>';
    return html;
}

function toggleEditForm(receiptId) {
    var details = document.getElementById('modal-receipt-details');
    var data = _currentReceiptData;
    if (!data) return;

    // Check if edit form already exists
    if (document.getElementById('receipt-edit-form')) {
        document.getElementById('receipt-edit-form').remove();
        return;
    }

    _loadCategories(function() {
        _loadEmployees(function() {
            var form = document.createElement('div');
            form.id = 'receipt-edit-form';
            form.className = 'edit-form';
            form.innerHTML = '<h4>Edit Receipt</h4>'
                + '<div class="form-row">'
                + '<div class="form-group"><label>Submitter</label>' + _buildEmployeeSelect('edit-employee', data.employee_id) + '</div>'
                + '<div class="form-group"><label>Vendor</label><input type="text" id="edit-vendor" value="' + escapeAttr(data.vendor_name || '') + '"></div>'
                + '<div class="form-group"><label>Date</label><input type="date" id="edit-date" value="' + (data.purchase_date || '') + '"></div>'
                + '</div>'
                + '<div class="form-row">'
                + '<div class="form-group"><label>Subtotal</label><input type="number" step="0.01" id="edit-subtotal" value="' + (data.subtotal || '') + '"></div>'
                + '<div class="form-group"><label>Tax</label><input type="number" step="0.01" id="edit-tax" value="' + (data.tax || '') + '"></div>'
                + '<div class="form-group"><label>Total</label><input type="number" step="0.01" id="edit-total" value="' + (data.total || '') + '"></div>'
                + '</div>'
                + '<div class="form-row">'
                + '<div class="form-group"><label>Payment Method</label><input type="text" id="edit-payment" value="' + escapeAttr(data.payment_method || '') + '"></div>'
                + '<div class="form-group"><label>Project</label><input type="text" id="edit-project" value="' + escapeAttr(data.project_name || data.matched_project_name || '') + '"></div>'
                + '<div class="form-group"><label>Category</label>' + _buildCategorySelect('edit-category', data.category_id) + '</div>'
                + '</div>'
                + '<div style="margin-top:8px;">'
                + '<button class="btn btn--small btn--primary" onclick="saveReceiptEdit(' + receiptId + ')">Save Changes</button>'
                + ' <button class="btn btn--small btn--secondary" onclick="document.getElementById(\'receipt-edit-form\').remove()">Cancel</button>'
                + ' <span id="edit-msg" style="margin-left:8px;font-size:12px;"></span>'
                + '</div>';

            details.appendChild(form);
        });
    });
}

function saveReceiptEdit(receiptId) {
    var msg = document.getElementById('edit-msg');
    msg.innerHTML = '<span style="color:#6b7280;">Saving...</span>';

    var catEl = document.getElementById('edit-category');
    var empEl = document.getElementById('edit-employee');
    var payload = {
        employee_id: empEl ? parseInt(empEl.value) : null,
        vendor_name: document.getElementById('edit-vendor').value,
        purchase_date: document.getElementById('edit-date').value,
        subtotal: parseFloat(document.getElementById('edit-subtotal').value) || 0,
        tax: parseFloat(document.getElementById('edit-tax').value) || 0,
        total: parseFloat(document.getElementById('edit-total').value) || 0,
        payment_method: document.getElementById('edit-payment').value,
        matched_project_name: document.getElementById('edit-project').value,
        category_id: catEl ? (parseInt(catEl.value) || null) : null,
    };

    fetch('/api/receipts/' + receiptId + '/edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(d) {
        if (d.status === 'updated') {
            msg.innerHTML = '<span style="color:#16a34a;">Saved! Reloading...</span>';
            setTimeout(function() { openReceiptModal(receiptId); }, 500);
            // Refresh ledger if it exists
            if (typeof loadLedger === 'function') loadLedger();
        } else {
            msg.innerHTML = '<span style="color:#dc2626;">' + (d.error || 'Failed') + '</span>';
        }
    });
}

function showEditHistory(receiptId) {
    var details = document.getElementById('modal-receipt-details');

    // Remove existing history panel
    var existing = document.getElementById('edit-history-panel');
    if (existing) { existing.remove(); return; }

    var panel = document.createElement('div');
    panel.id = 'edit-history-panel';
    panel.className = 'edit-history';
    panel.innerHTML = '<h4>Edit History</h4><div class="loading">Loading...</div>';
    details.appendChild(panel);

    fetch('/api/receipts/' + receiptId + '/edits')
        .then(function(resp) { return resp.json(); })
        .then(function(d) {
            if (!d.edits || d.edits.length === 0) {
                panel.innerHTML = '<h4>Edit History</h4><p class="text-muted">No edits recorded.</p>';
                return;
            }
            var html = '<h4>Edit History</h4><table class="line-items-table">';
            html += '<thead><tr><th>Field</th><th>Old</th><th>New</th><th>When</th></tr></thead><tbody>';
            for (var i = 0; i < d.edits.length; i++) {
                var e = d.edits[i];
                html += '<tr><td>' + escapeHtml(e.field_changed) + '</td>';
                html += '<td class="text-muted">' + escapeHtml(e.old_value || '—') + '</td>';
                html += '<td>' + escapeHtml(e.new_value || '—') + '</td>';
                html += '<td class="text-muted">' + escapeHtml(e.edited_at || '') + '</td></tr>';
            }
            html += '</tbody></table>';
            panel.innerHTML = html;
        });
}


// ── Confirm / Delete / Restore / Duplicate ──────────────

function confirmReceipt(receiptId) {
    fetch('/api/receipts/' + receiptId + '/edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({status: 'confirmed'}),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(d) {
        if (d.status === 'updated') {
            openReceiptModal(receiptId);
            if (typeof loadLedger === 'function') loadLedger();
            else location.reload();
        } else {
            alert(d.error || 'Failed to confirm receipt');
        }
    });
}

function deleteReceipt(receiptId) {
    if (!confirm('Are you sure you want to delete this receipt? It can be restored from the Ledger.')) return;
    fetch('/api/receipts/' + receiptId + '/delete', { method: 'POST' })
        .then(function(resp) { return resp.json(); })
        .then(function(d) {
            if (d.status === 'deleted') {
                closeReceiptModal();
                if (typeof loadLedger === 'function') loadLedger();
                else location.reload();
            } else {
                alert(d.error || 'Failed to delete receipt');
            }
        });
}

function restoreReceipt(receiptId) {
    fetch('/api/receipts/' + receiptId + '/restore', { method: 'POST' })
        .then(function(resp) { return resp.json(); })
        .then(function(d) {
            if (d.status === 'restored') {
                openReceiptModal(receiptId);
                if (typeof loadLedger === 'function') loadLedger();
            } else {
                alert(d.error || 'Failed to restore receipt');
            }
        });
}

function markDuplicate(receiptId) {
    var dupOf = prompt('Enter the receipt ID this is a duplicate of (or leave blank):');
    if (dupOf === null) return; // cancelled
    var payload = {};
    if (dupOf && dupOf.trim()) payload.duplicate_of = parseInt(dupOf.trim(), 10);
    fetch('/api/receipts/' + receiptId + '/duplicate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    })
    .then(function(resp) { return resp.json(); })
    .then(function(d) {
        if (d.status === 'duplicate') {
            closeReceiptModal();
            if (typeof loadLedger === 'function') loadLedger();
            else location.reload();
        } else {
            alert(d.error || 'Failed to mark as duplicate');
        }
    });
}


// ── Helpers ─────────────────────────────────────────────

function detailField(label, value) {
    return '<div><div class="detail-label">' + label + '</div>'
         + '<div class="detail-value">' + (value || '—') + '</div></div>';
}

function formatMoney(amount) {
    if (amount === null || amount === undefined) return '—';
    return '$' + Number(amount).toFixed(2);
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    var parts = dateStr.split('-');
    if (parts.length === 3) {
        var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        return months[parseInt(parts[1], 10) - 1] + ' ' + parseInt(parts[2], 10) + ', ' + parts[0];
    }
    return dateStr;
}

function escapeHtml(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
