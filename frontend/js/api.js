const API_BASE = window.location.origin;

async function fetchJSON(path) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (json.status === "error") throw new Error(json.message);
    return json.data;
}

const API = {
    getDashboard: () => fetchJSON("/api/dashboard"),
    getMonthDetail: (tab) => fetchJSON(`/api/month/${encodeURIComponent(tab)}`),
    getTargets: () => fetchJSON("/api/targets"),
    refresh: () => fetchJSON("/api/refresh"),
};
