/**
 * ============================================================
 * SMART REFILL - ENHANCEMENTS & FEATURES
 * ============================================================
 */

// ============================================================
// DARK MODE TOGGLE
// ============================================================

function initializeDarkMode() {
    const savedMode = localStorage.getItem('darkMode');
    const darkModeToggle = document.querySelector('.dark-mode-toggle');

    if (savedMode === 'enabled') {
        document.body.classList.add('dark-mode');
        if (darkModeToggle) darkModeToggle.textContent = '🌙';
    } else {
        if (darkModeToggle) darkModeToggle.textContent = '☀️';
    }

    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', toggleDarkMode);
    }
}

function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const darkModeToggle = document.querySelector('.dark-mode-toggle');
    
    if (document.body.classList.contains('dark-mode')) {
        localStorage.setItem('darkMode', 'enabled');
        if (darkModeToggle) darkModeToggle.textContent = '🌙';
    } else {
        localStorage.setItem('darkMode', 'disabled');
        if (darkModeToggle) darkModeToggle.textContent = '☀️';
    }
}

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

    searchInput.addEventListener('keyup', function() {
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

    categorySelect.addEventListener('change', function() {
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
    if (confirm(`Are you sure you want to delete SKU '${productName}'? This action cannot be undone.`)) {
        return true;
    }
    return false;
}

// ============================================================
// HELPER FUNCTIONS
// ============================================================

function confirmDelete(productName) {
    if (confirm(`Are you sure you want to delete SKU '${productName}'? This action cannot be undone.`)) {
        return true;
    }
    return false;
}

// ============================================================
// INITIALIZATION
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initializeDarkMode();
});

// Export functions for use in HTML
window.SmartRefill = {
    exportTableToCSV,
    filterTable,
    filterByCategory,
    showAlert,
    validateForm,
    markFieldError,
    clearFieldError,
    toggleDarkMode,
    confirmDelete
};
