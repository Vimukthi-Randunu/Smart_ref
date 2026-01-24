const ctx = document.getElementById('movementChart');

new Chart(ctx, {
    type: 'bar',
    data: {
        labels: ['Inbound', 'Outbound'],
        datasets: [{
            label: 'Stock Quantity',
            data: [inbound, outbound],
            backgroundColor: ['#10b981', '#6366f1'],
            borderRadius: 8,
            borderSkipped: false,
            borderColor: ['#059669', '#4f46e5'],
            borderWidth: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { 
                display: false 
            },
            tooltip: {
                backgroundColor: '#1f2937',
                padding: 12,
                titleFont: { size: 14, weight: 600 },
                bodyFont: { size: 13 },
                cornerRadius: 6,
                borderColor: '#4b5563',
                borderWidth: 1
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: '#e5e7eb',
                    drawBorder: false
                },
                ticks: {
                    color: '#6b7280',
                    font: { size: 12 }
                }
            },
            x: {
                grid: {
                    display: false,
                    drawBorder: false
                },
                ticks: {
                    color: '#6b7280',
                    font: { size: 13, weight: 600 }
                }
            }
        }
    }
});
