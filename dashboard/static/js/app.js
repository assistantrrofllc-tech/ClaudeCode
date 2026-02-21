/* CrewLedger Dashboard — Core JavaScript */

// ── Receipt Image Modal ─────────────────────────────────

var _currentReceiptId = null;
var _currentReceiptData = null;

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

            // Footer with edit/history buttons
            if (footer) {
                footer.innerHTML = '<button class="btn btn--small btn--secondary" onclick="toggleEditForm(' + receiptId + ')">Edit Receipt</button>'
                    + ' <button class="btn btn--small btn--secondary" onclick="showEditHistory(' + receiptId + ')">Edit History</button>';
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

function toggleEditForm(receiptId) {
    var details = document.getElementById('modal-receipt-details');
    var data = _currentReceiptData;
    if (!data) return;

    // Check if edit form already exists
    if (document.getElementById('receipt-edit-form')) {
        document.getElementById('receipt-edit-form').remove();
        return;
    }

    var form = document.createElement('div');
    form.id = 'receipt-edit-form';
    form.className = 'edit-form';
    form.innerHTML = '<h4>Edit Receipt</h4>'
        + '<div class="form-row">'
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
        + '</div>'
        + '<div style="margin-top:8px;">'
        + '<button class="btn btn--small btn--primary" onclick="saveReceiptEdit(' + receiptId + ')">Save Changes</button>'
        + ' <button class="btn btn--small btn--secondary" onclick="document.getElementById(\'receipt-edit-form\').remove()">Cancel</button>'
        + ' <span id="edit-msg" style="margin-left:8px;font-size:12px;"></span>'
        + '</div>';

    details.appendChild(form);
}

function saveReceiptEdit(receiptId) {
    var msg = document.getElementById('edit-msg');
    msg.innerHTML = '<span style="color:#6b7280;">Saving...</span>';

    var payload = {
        vendor_name: document.getElementById('edit-vendor').value,
        purchase_date: document.getElementById('edit-date').value,
        subtotal: parseFloat(document.getElementById('edit-subtotal').value) || 0,
        tax: parseFloat(document.getElementById('edit-tax').value) || 0,
        total: parseFloat(document.getElementById('edit-total').value) || 0,
        payment_method: document.getElementById('edit-payment').value,
        matched_project_name: document.getElementById('edit-project').value,
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
