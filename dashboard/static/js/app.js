/* CrewLedger Dashboard — Core JavaScript */

// ── Receipt Image Modal ─────────────────────────────────

function openReceiptModal(receiptId) {
    var modal = document.getElementById('receipt-modal');
    var img = document.getElementById('modal-receipt-image');
    var details = document.getElementById('modal-receipt-details');

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    details.innerHTML = '<div class="loading">Loading...</div>';
    img.src = '';

    fetch('/api/receipts/' + receiptId)
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
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
        })
        .catch(function(err) {
            details.innerHTML = '<div class="loading">Failed to load receipt details.</div>';
        });
}

function closeReceiptModal() {
    var modal = document.getElementById('receipt-modal');
    modal.style.display = 'none';
    document.body.style.overflow = '';
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeReceiptModal();
});


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
