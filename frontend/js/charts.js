let revenueChart = null;

const COLORS = {
    blue: "#2563EB",
    green: "#16A34A",
    lightBlue: "rgba(37, 99, 235, 0.1)",
    lightGreen: "rgba(22, 163, 74, 0.1)",
    gray: "#F0F0F0",
    text: "#1A1A1A",
    textSecondary: "#6B6B6B",
};

function destroyChart(chart) {
    if (chart) chart.destroy();
    return null;
}

function formatEuro(val) {
    if (Math.abs(val) >= 1000) return "\u20ac " + (val / 1000).toFixed(1) + "k";
    return "\u20ac " + val.toFixed(0);
}

function createRevenueChart(ctx, months, incBTW) {
    revenueChart = destroyChart(revenueChart);
    const labels = months.map(m => m.month);
    revenueChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [
                {
                    label: incBTW ? "Omzet (Incl. VAT)" : "Omzet (Excl. VAT)",
                    data: months.map(m => m.display_revenue != null ? m.display_revenue : m.revenue),
                    backgroundColor: COLORS.blue,
                    borderRadius: 6,
                    barPercentage: 0.6,
                    categoryPercentage: 0.7,
                },
                {
                    label: "Profit",
                    data: months.map(m => m.nett_margin_business),
                    backgroundColor: COLORS.green,
                    borderRadius: 6,
                    barPercentage: 0.6,
                    categoryPercentage: 0.7,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        font: { family: "'Inter', sans-serif", size: 13, weight: 500 },
                        usePointStyle: true,
                        pointStyle: "circle",
                        padding: 20,
                    },
                },
                tooltip: {
                    backgroundColor: "#1A1A1A",
                    titleFont: { family: "'Inter', sans-serif", size: 13 },
                    bodyFont: { family: "'Inter', sans-serif", size: 13 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: \u20ac ${ctx.parsed.y.toLocaleString("nl-NL", { minimumFractionDigits: 0 })}`,
                    },
                },
            },
            scales: {
                y: {
                    ticks: {
                        callback: v => formatEuro(v),
                        font: { family: "'Inter', sans-serif", size: 12 },
                        color: COLORS.textSecondary,
                    },
                    grid: { color: COLORS.gray },
                    border: { display: false },
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        font: { family: "'Inter', sans-serif", size: 12 },
                        color: COLORS.textSecondary,
                    },
                    border: { display: false },
                },
            },
        },
    });
    return revenueChart;
}

let targetChart = null;

function createTargetChart(ctx, labels, datasets) {
    targetChart = destroyChart(targetChart);
    targetChart = new Chart(ctx, {
        type: "bar",
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        font: { family: "'Inter', sans-serif", size: 13, weight: 500 },
                        usePointStyle: true,
                        pointStyle: "circle",
                        padding: 20,
                    },
                },
                tooltip: {
                    backgroundColor: "#1A1A1A",
                    titleFont: { family: "'Inter', sans-serif", size: 13 },
                    bodyFont: { family: "'Inter', sans-serif", size: 13 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: \u20ac ${ctx.parsed.y.toLocaleString("nl-NL", { minimumFractionDigits: 0 })}`,
                    },
                },
            },
            scales: {
                x: {
                    stacked: true,
                    grid: { display: false },
                    ticks: { font: { family: "'Inter', sans-serif", size: 13 } },
                    border: { display: false },
                },
                y: {
                    stacked: true,
                    ticks: {
                        callback: v => formatEuro(v),
                        font: { family: "'Inter', sans-serif", size: 12 },
                        color: COLORS.textSecondary,
                    },
                    grid: { color: COLORS.gray },
                    border: { display: false },
                },
            },
        },
    });
    // The "Target" line dataset should NOT be stacked
    targetChart.data.datasets.forEach((ds, i) => {
        if (ds.type === "line") {
            targetChart.options.scales.y.stacked = true;
        }
    });
    return targetChart;
}
