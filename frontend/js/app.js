let dashboardData = null;
let allMonths = [];
let activeFilter = "all";
let showIncBTW = false;
const BTW_RATE = 0.21;

document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
    document.getElementById("refresh-btn").addEventListener("click", () => loadDashboard(true));

    // Filter buttons
    document.querySelectorAll(".filter-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const filter = btn.dataset.filter;
            setActiveFilter(filter);
            if (filter === "custom") {
                document.getElementById("custom-range").style.display = "flex";
            } else {
                document.getElementById("custom-range").style.display = "none";
                applyFilter(filter);
            }
        });
    });

    // Custom range apply
    document.getElementById("apply-range").addEventListener("click", () => {
        applyFilter("custom");
    });

    // BTW toggle switch
    document.getElementById("btw-toggle").addEventListener("click", () => {
        showIncBTW = !showIncBTW;
        const sw = document.getElementById("btw-toggle");
        sw.classList.toggle("inc", showIncBTW);
        sw.querySelectorAll(".btw-option").forEach(opt => {
            opt.classList.toggle("active", (opt.dataset.val === "inc") === showIncBTW);
        });
        applyFilter(activeFilter);
    });

    // Auto-refresh every 5 min
    setInterval(() => loadDashboard(), 5 * 60 * 1000);
});

async function loadDashboard(forceRefresh = false) {
    showLoading(true);
    try {
        dashboardData = forceRefresh ? await API.refresh() : await API.getDashboard();
        allMonths = dashboardData.months;
        populateRangeSelects(allMonths);
        applyFilter(activeFilter);
    } catch (err) {
        showError(err.message);
    }
    showLoading(false);
    loadTargets();
}

function setActiveFilter(filter) {
    activeFilter = filter;
    document.querySelectorAll(".filter-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.filter === filter);
    });
}

function getRevenue(m) {
    return showIncBTW ? m.revenue * (1 + BTW_RATE) : m.revenue;
}

function applyFilter(filter) {
    const filtered = filterMonths(filter);
    renderKPIs(filtered);
    const chartData = filtered.map(m => ({ ...m, display_revenue: getRevenue(m) }));
    createRevenueChart(document.getElementById("revenue-chart"), chartData, showIncBTW);
}

function filterMonths(filter) {
    if (!allMonths || allMonths.length === 0) return [];

    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth() + 1;

    switch (filter) {
        case "all":
            return allMonths;

        case "ytd":
            return allMonths.filter(m => m.year === currentYear && m.month_num <= currentMonth);

        case "last-year":
            return allMonths.filter(m => m.year === currentYear - 1);

        case "q1":
            return allMonths.filter(m => m.month_num >= 1 && m.month_num <= 3 && m.year === currentYear);

        case "q2":
            return allMonths.filter(m => m.month_num >= 4 && m.month_num <= 6 && m.year === currentYear);

        case "q3":
            return allMonths.filter(m => m.month_num >= 7 && m.month_num <= 9);

        case "q4":
            return allMonths.filter(m => m.month_num >= 10 && m.month_num <= 12);

        case "custom": {
            const fromIdx = parseInt(document.getElementById("range-from").value);
            const toIdx = parseInt(document.getElementById("range-to").value);
            if (isNaN(fromIdx) || isNaN(toIdx)) return allMonths;
            const start = Math.min(fromIdx, toIdx);
            const end = Math.max(fromIdx, toIdx);
            return allMonths.slice(start, end + 1);
        }

        default:
            return allMonths;
    }
}

function populateRangeSelects(months) {
    const fromSelect = document.getElementById("range-from");
    const toSelect = document.getElementById("range-to");
    fromSelect.innerHTML = "";
    toSelect.innerHTML = "";

    months.forEach((m, i) => {
        const label = m.month;
        fromSelect.add(new Option(label, i));
        toSelect.add(new Option(label, i));
    });

    // Default: first and last
    if (months.length > 0) {
        fromSelect.value = "0";
        toSelect.value = String(months.length - 1);
    }
}

function renderKPIs(months) {
    if (!months || months.length === 0) {
        ["kpi-revenue", "kpi-gross-margin", "kpi-nett-margin", "kpi-profit"].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.querySelector(".kpi-value").textContent = "--";
                el.querySelector(".kpi-change").textContent = "";
            }
        });
        document.getElementById("kpi-month-label").textContent = "";
        return;
    }

    const current = months[months.length - 1];
    const prev = months.length > 1 ? months[months.length - 2] : null;

    if (months.length > 1) {
        const totalRevenue = months.reduce((sum, m) => sum + getRevenue(m), 0);
        const totalProfit = months.reduce((sum, m) => sum + m.nett_margin_business, 0);
        const avgGrossMargin = months.reduce((sum, m) => sum + m.gross_margin_pct, 0) / months.length;
        const avgNettMargin = months.reduce((sum, m) => sum + m.nett_margin_business_pct, 0) / months.length;

        setKPI("kpi-revenue", totalRevenue, null, true);
        setKPI("kpi-gross-margin", avgGrossMargin, null, false, "%");
        setKPI("kpi-nett-margin", avgNettMargin, null, false, "%");
        setKPI("kpi-profit", totalProfit, null, true);

        const first = months[0].month;
        const last = months[months.length - 1].month;
        document.getElementById("kpi-month-label").textContent = `${first} - ${last}`;
    } else {
        setKPI("kpi-revenue", getRevenue(current), null, true);
        setKPI("kpi-gross-margin", current.gross_margin_pct, null, false, "%");
        setKPI("kpi-nett-margin", current.nett_margin_business_pct, null, false, "%");
        setKPI("kpi-profit", current.nett_margin_business, null, true);
        document.getElementById("kpi-month-label").textContent = current.month;
    }
}

function setKPI(id, value, prevValue, isCurrency = true, suffix = "") {
    const el = document.getElementById(id);
    if (!el) return;
    const valEl = el.querySelector(".kpi-value");
    const changeEl = el.querySelector(".kpi-change");

    if (isCurrency) {
        valEl.textContent = "\u20ac " + value.toLocaleString("nl-NL", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    } else {
        valEl.textContent = value.toFixed(1) + suffix;
    }

    if (prevValue != null && prevValue !== 0) {
        const pctChange = ((value - prevValue) / Math.abs(prevValue)) * 100;
        const arrow = pctChange >= 0 ? "\u2191" : "\u2193";
        changeEl.textContent = `${arrow} ${Math.abs(pctChange).toFixed(1)}%`;
        changeEl.className = "kpi-change " + (pctChange >= 0 ? "positive" : "negative");
    } else {
        changeEl.textContent = "";
    }
}

// ── Target Tracking ──

let targetData = null;
let activeTargetQ = "total";

async function loadTargets() {
    try {
        targetData = await API.getTargets();
        document.getElementById("target-section").style.display = "block";

        // Wire up Q buttons
        document.querySelectorAll(".target-q-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                activeTargetQ = btn.dataset.q;
                document.querySelectorAll(".target-q-btn").forEach(b => b.classList.toggle("active", b.dataset.q === activeTargetQ));
                renderTargetProgress(targetData.categories, activeTargetQ);
            });
        });

        renderTargetProgress(targetData.categories, activeTargetQ);
        renderTargetChart(targetData.categories);
    } catch (err) {
        console.error("Target load error:", err);
    }
}

function renderTargetProgress(categories, qFilter) {
    const container = document.getElementById("target-progress");
    container.innerHTML = "";

    const order = ["Sleep Masks", "Pillowcases", "Pyjamas", "Total GMV"];
    const qIndex = { q1: 0, q2: 1, q3: 2, q4: 3 };

    order.forEach(name => {
        const cat = categories[name];
        if (!cat) return;

        let actual, target, label;

        if (qFilter === "total") {
            actual = cat.ytd_actual;
            target = cat.ytd_target;
            label = "Total";
        } else if (qFilter === "ytd") {
            // Pro-rata target: full quarters passed + fraction of current quarter
            const now = new Date();
            const currentMonth = now.getMonth(); // 0-based
            const currentQ = Math.floor(currentMonth / 3);
            const monthInQ = currentMonth - (currentQ * 3);
            const qFraction = (monthInQ + now.getDate() / 30) / 3;

            actual = cat.ytd_actual;
            target = 0;
            for (let q = 0; q < 4; q++) {
                if (q < currentQ) {
                    target += cat.quarterly_targets[q]; // full past quarters
                } else if (q === currentQ) {
                    target += cat.quarterly_targets[q] * qFraction; // fraction of current Q
                }
            }
            target = Math.round(target);
            label = "YTD";
        } else {
            const qi = qIndex[qFilter];
            actual = cat.quarterly_actuals[qi];
            target = cat.quarterly_targets[qi];
            label = qFilter.toUpperCase();
        }

        const pctVal = target > 0 ? (actual / target) * 100 : 0;
        const pct = Math.min(pctVal, 100);

        // Expected progress within the selected period
        let expectedPct;
        if (qFilter === "ytd") {
            expectedPct = 100; // target is already pro-rata, so 100% = on track
        } else if (qFilter === "total") {
            const now = new Date();
            const dayOfYear = Math.floor((now - new Date(now.getFullYear(), 0, 0)) / 86400000);
            expectedPct = (dayOfYear / 365) * 100;
        } else {
            const qi = qIndex[qFilter];
            const now = new Date();
            const currentQ = Math.floor(now.getMonth() / 3);
            if (qi < currentQ) {
                expectedPct = 100; // past quarter
            } else if (qi > currentQ) {
                expectedPct = 0; // future quarter
            } else {
                const qStartMonth = qi * 3;
                const monthInQ = now.getMonth() - qStartMonth;
                expectedPct = ((monthInQ + now.getDate() / 30) / 3) * 100;
            }
        }

        const onTrack = pctVal >= (expectedPct * 0.85);

        const card = document.createElement("div");
        card.className = "progress-card" + (name === "Total GMV" ? " total" : "");
        card.innerHTML = `
            <div class="progress-header">
                <span class="progress-name">${name}</span>
                <span class="progress-pct ${onTrack ? 'on-track' : 'behind'}">${pctVal.toFixed(1)}%</span>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill ${onTrack ? 'on-track' : 'behind'}" style="width: ${pct}%"></div>
                ${expectedPct > 0 ? `<div class="progress-bar-expected" style="left: ${Math.min(expectedPct, 100)}%"></div>` : ''}
            </div>
            <div class="progress-amounts">
                <span>\u20ac ${actual.toLocaleString("nl-NL", {maximumFractionDigits: 0})}</span>
                <span class="progress-target">/ \u20ac ${target.toLocaleString("nl-NL", {maximumFractionDigits: 0})}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderTargetChart(categories) {
    const catOrder = ["Sleep Masks", "Pillowcases", "Pyjamas"];
    const colors = { "Sleep Masks": "#2563EB", "Pillowcases": "#B8C4D4", "Pyjamas": "#E8DDD0" };
    const labels = ["Q1", "Q2", "Q3", "Q4"];

    const datasets = catOrder.map(name => ({
        label: name,
        data: categories[name]?.quarterly_actuals || [0, 0, 0, 0],
        backgroundColor: colors[name],
        borderRadius: 6,
        barPercentage: 0.6,
        categoryPercentage: 0.7,
    }));

    // Target line
    const totalTargets = categories["Total GMV"]?.quarterly_targets || [0, 0, 0, 0];
    datasets.push({
        label: "Target",
        data: totalTargets,
        type: "line",
        borderColor: "#C25B56",
        borderWidth: 2,
        borderDash: [6, 4],
        pointBackgroundColor: "#C25B56",
        pointRadius: 5,
        fill: false,
        tension: 0,
    });

    createTargetChart(document.getElementById("target-chart"), labels, datasets);
}

function renderTargetTable(categories) {
    const tbody = document.getElementById("target-table-body");
    tbody.innerHTML = "";

    const order = ["Sleep Masks", "Pillowcases", "Pyjamas", "Total GMV"];

    order.forEach(name => {
        const cat = categories[name];
        if (!cat) return;

        const tr = document.createElement("tr");
        if (name === "Total GMV") tr.className = "total-row";

        let html = `<td class="cat-name">${name}</td>`;

        for (let q = 0; q < 4; q++) {
            const actual = cat.quarterly_actuals[q];
            const target = cat.quarterly_targets[q];
            const pct = target > 0 ? (actual / target) * 100 : 0;
            const cls = actual === 0 ? "" : pct >= 90 ? "on-track" : pct >= 70 ? "warning" : "behind";

            html += `<td class="num ${cls}">\u20ac ${(actual / 1000).toFixed(1)}k</td>`;
            html += `<td class="num target-col">\u20ac ${(target / 1000).toFixed(0)}k</td>`;
        }

        // YTD
        const ytdCls = cat.ytd_actual === 0 ? "" : cat.ytd_pct >= 90 ? "on-track" : cat.ytd_pct >= 70 ? "warning" : "behind";
        html += `<td class="num ${ytdCls}">\u20ac ${(cat.ytd_actual / 1000).toFixed(1)}k</td>`;
        html += `<td class="num target-col">\u20ac ${(cat.ytd_target / 1000).toFixed(0)}k</td>`;

        tr.innerHTML = html;
        tbody.appendChild(tr);
    });
}

function showLoading(show) {
    const el = document.getElementById("loading");
    if (el) el.style.display = show ? "flex" : "none";
}

function showError(msg) {
    const el = document.getElementById("error-msg");
    if (el) {
        el.textContent = msg;
        el.style.display = "block";
        setTimeout(() => { el.style.display = "none"; }, 5000);
    }
}
