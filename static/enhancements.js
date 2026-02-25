/**
 * ============================================================
 * SMART REFILL - ENHANCEMENTS & FEATURES
 * ============================================================
 */

// ============================================================
// DARK MODE TOGGLE
// ============================================================

const darkModeToggle = document.querySelector('.dark-mode-toggle');

if (darkModeToggle) {
    // Check for saved preference
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        // Wait for SmartRefill to be initialized before updating icon if needed
        // but updateToggleIcon is global so it works
        updateToggleIcon();
    }

    darkModeToggle.addEventListener('click', function () {
        // Use the exposed function if available, otherwise fallback (though it should be available)
        if (window.SmartRefill && window.SmartRefill.toggleDarkMode) {
            window.SmartRefill.toggleDarkMode();
        } else {
            // Fallback just in case
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('darkMode', document.body.classList.contains('dark-mode') ? 'enabled' : 'disabled');
            updateToggleIcon();
        }
    });
}

function updateToggleIcon() {
    const toggle = document.querySelector('.dark-mode-toggle');
    if (!toggle) return;

    if (document.body.classList.contains('dark-mode')) {
        toggle.innerHTML = '<i class="fas fa-sun"></i> Light Mode';
    } else {
        toggle.innerHTML = '<i class="fas fa-moon"></i> Dark Mode';
    }
}

// ============================================================
// BARCODE SCANNER SUPPORT
// ============================================================

/**
 * BarcodeScanner - Detects barcode scanner input
 * Barcode scanners type very fast (<100ms between chars) and send Enter
 * This class distinguishes scanner input from manual typing
 */
class BarcodeScanner {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            onScan: options.onScan || (() => { }),
            minLength: options.minLength || 3,
            scannerThreshold: options.scannerThreshold || 100, // ms between keystrokes
            enterKeyRequired: options.enterKeyRequired !== false,
            ...options
        };

        this.buffer = '';
        this.lastKeyTime = 0;
        this.timestamps = [];

        this.init();
    }

    init() {
        this.input.addEventListener('keypress', (e) => this.handleKeypress(e));
        this.input.addEventListener('paste', (e) => this.handlePaste(e));
    }

    handleKeypress(e) {
        const currentTime = Date.now();
        const timeDiff = currentTime - this.lastKeyTime;

        if (e.key === 'Enter') {
            e.preventDefault();

            // Check if this looks like a scanner input
            if (this.buffer.length >= this.options.minLength) {
                const avgTimeDiff = this.getAverageTimeDiff();
                const isScanner = avgTimeDiff < this.options.scannerThreshold;

                this.options.onScan(this.buffer.trim(), isScanner);
                this.showFeedback(isScanner ? '✅ Scanned!' : '✓ Entered');
            }

            this.reset();
        } else {
            // Accumulate characters
            this.buffer += e.key;
            this.timestamps.push(currentTime);
        }

        this.lastKeyTime = currentTime;
    }

    handlePaste(e) {
        // Pasting simulates scanner for testing
        const pastedText = (e.clipboardData || window.clipboardData).getData('text');
        if (pastedText && pastedText.length >= this.options.minLength) {
            e.preventDefault();
            this.buffer = pastedText;
            this.options.onScan(pastedText.trim(), true);
            this.showFeedback('✅ Scanned!');
            this.reset();
        }
    }

    getAverageTimeDiff() {
        if (this.timestamps.length < 2) return 0;

        let totalDiff = 0;
        for (let i = 1; i < this.timestamps.length; i++) {
            totalDiff += this.timestamps[i] - this.timestamps[i - 1];
        }
        return totalDiff / (this.timestamps.length - 1);
    }

    reset() {
        this.buffer = '';
        this.timestamps = [];
    }

    showFeedback(message) {
        const indicator = this.input.parentElement.querySelector('.scan-indicator');
        if (indicator) {
            const originalText = indicator.textContent;
            indicator.textContent = message;
            indicator.classList.add('success');

            setTimeout(() => {
                indicator.textContent = originalText;
                indicator.classList.remove('success');
            }, 2000);
        }
    }
}

// Initialize barcode scanner on product lookup fields
function initBarcodeScanners() {
    // Add Product page - barcode input
    const addProductInput = document.getElementById('barcode-input');
    if (addProductInput) {
        new BarcodeScanner(addProductInput, {
            onScan: (barcode, isScanner) => {
                // Populate product name field
                const nameField = document.querySelector('input[name="name"]');
                if (nameField && !nameField.value) {
                    nameField.value = barcode;
                    nameField.focus();
                }
            }
        });
    }

    // Inbound/Outbound - product lookup
    const productLookup = document.getElementById('product-lookup');
    if (productLookup) {
        new BarcodeScanner(productLookup, {
            onScan: (barcode, isScanner) => {
                // Find matching product in dropdown
                const productSelect = document.querySelector('select[name="name"]');
                if (productSelect) {
                    const options = Array.from(productSelect.options);
                    const match = options.find(opt =>
                        opt.value.toLowerCase().includes(barcode.toLowerCase())
                    );

                    if (match) {
                        productSelect.value = match.value;
                        productSelect.dispatchEvent(new Event('change'));

                        // Move to quantity field
                        const qtyField = document.querySelector('input[name="quantity"]');
                        if (qtyField) qtyField.focus();
                    } else {
                        alert(`Product not found: ${barcode}`);
                    }
                }
            }
        });
    }

    // Product search - warehouse stock page
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        new BarcodeScanner(searchInput, {
            onScan: (barcode, isScanner) => {
                // Trigger search
                searchInput.value = barcode;
                searchInput.dispatchEvent(new Event('keyup'));
            }
        });
    }
}

// Auto-initialize on page load
document.addEventListener('DOMContentLoaded', initBarcodeScanners);


// ============================================================
// EXPORT TO CSV
// ============================================================

function exportTableToCSV(filename = 'export.csv') {
    const table = document.querySelector('table');
    if (!table) {
        alert('No table found to export');
        return;
    }

    let csv = [];
    const rows = table.querySelectorAll('tr');

    rows.forEach(row => {
        const cols = row.querySelectorAll('td, th');
        const csvRow = [];
        cols.forEach(col => {
            csvRow.push('"' + col.innerText.replace(/"/g, '""') + '"');
        });
        csv.push(csvRow.join(','));
    });

    downloadCSV(csv.join('\n'), filename);
}

function downloadCSV(csv, filename) {
    const csvFile = new Blob([csv], { type: 'text/csv' });
    const downloadLink = document.createElement('a');
    downloadLink.href = URL.createObjectURL(csvFile);
    downloadLink.download = filename;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

// ============================================================
// TABLE FILTERING & SEARCH
// ============================================================

function filterTable(tableSelector, searchInputSelector) {
    const searchInput = document.querySelector(searchInputSelector);
    const table = document.querySelector(tableSelector);

    if (!searchInput || !table) return;

    searchInput.addEventListener('keyup', function () {
        const searchValue = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(searchValue) ? '' : 'none';
        });
    });
}

// ============================================================
// CATEGORY FILTER
// ============================================================

function filterByCategory(selectSelector, tableSelector) {
    const categorySelect = document.querySelector(selectSelector);
    const table = document.querySelector(tableSelector);

    if (!categorySelect || !table) return;

    categorySelect.addEventListener('change', function () {
        const selectedCategory = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');

        rows.forEach(row => {
            if (selectedCategory === 'all') {
                row.style.display = '';
            } else {
                const categoryCell = row.querySelector('[data-category]');
                if (categoryCell) {
                    const category = categoryCell.getAttribute('data-category').toLowerCase();
                    row.style.display = category === selectedCategory ? '' : 'none';
                }
            }
        });
    });
}

// ============================================================
// SHOW ALERT MESSAGE
// ============================================================

function showAlert(message, type = 'info', duration = 5000) {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type}`;
    alertContainer.innerHTML = `
        <i class="fas fa-${getAlertIcon(type)}"></i>
        <span>${message}</span>
    `;

    document.body.insertBefore(alertContainer, document.body.firstChild);

    setTimeout(() => {
        alertContainer.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => alertContainer.remove(), 300);
    }, duration);
}

function getAlertIcon(type) {
    const icons = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// ============================================================
// FORM VALIDATION
// ============================================================

function validateForm(formSelector) {
    const form = document.querySelector(formSelector);
    if (!form) return false;

    let isValid = true;
    const inputs = form.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        if (!input.value.trim()) {
            markFieldError(input, 'This field is required');
            isValid = false;
        } else {
            clearFieldError(input);
        }
    });

    return isValid;
}

function markFieldError(field, message) {
    const parent = field.closest('.form-group') || field.parentElement;
    parent.classList.add('error');

    let errorMsg = parent.querySelector('.form-error');
    if (!errorMsg) {
        errorMsg = document.createElement('div');
        errorMsg.className = 'form-error';
        parent.appendChild(errorMsg);
    }
    errorMsg.textContent = message;
}

function clearFieldError(field) {
    const parent = field.closest('.form-group') || field.parentElement;
    parent.classList.remove('error');

    const errorMsg = parent.querySelector('.form-error');
    if (errorMsg) errorMsg.remove();
}

// ============================================================
// CONFIRMATION DIALOGS
// ============================================================

function confirmDelete(productName) {
    return confirm(`Are you sure you want to delete SKU '${productName}'? This action cannot be undone.`);
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================

// ============================================================
// INITIALIZATION
// ============================================================

// Export functions for use in HTML
window.SmartRefill = {
    exportTableToCSV,
    filterTable,
    filterByCategory,
    showAlert,
    validateForm,
    markFieldError,
    clearFieldError,
    confirmDelete,
    toggleDarkMode: function (forceState, instant) {
        // This is a wrapper to expose the internal logic if needed, 
        // but the current implementation uses event listeners.
        // Let's refactor the internal logic to be a callable function first
        // actually, let's just make the internal logic callable.

        const toggle = document.querySelector('.dark-mode-toggle');
        if (forceState !== null && forceState !== undefined) {
            if (forceState) {
                document.body.classList.add('dark-mode');
                localStorage.setItem('darkMode', 'enabled');
            } else {
                document.body.classList.remove('dark-mode');
                localStorage.setItem('darkMode', 'disabled');
            }
        } else {
            document.body.classList.toggle('dark-mode');
            if (document.body.classList.contains('dark-mode')) {
                localStorage.setItem('darkMode', 'enabled');
            } else {
                localStorage.setItem('darkMode', 'disabled');
            }
        }
        updateToggleIcon();
    }
};
