/* ═══════════════════════════════════════════════════════════════════
   AegisLab AI — Frontend Application (Vanilla JS)
   Firebase Auth · Categorized Lab Entry · Patient Management
   AI Analysis · History · Biomarker Trends
   ═══════════════════════════════════════════════════════════════════ */

// ── Firebase Configuration ──────────────────────────────────────────
const firebaseConfig = {
    apiKey: "AIzaSyAzV2zadIkjw6OM6IZwwiSQkbIs4t6P9m8",
    authDomain: "aegislab-ai.firebaseapp.com",
    projectId: "aegislab-ai",
    storageBucket: "aegislab-ai.firebasestorage.app",
    messagingSenderId: "122901812587",
    appId: "1:122901812587:web:82968ebced6b3367d2a82e",
    measurementId: "G-M6GG36RGVJ",
};

// ── Config Validation ───────────────────────────────────────────────
const _isPlaceholder = (v) => !v || v.startsWith("YOUR_") || v === "000000000000";
const _configMissing =
    _isPlaceholder(firebaseConfig.apiKey) ||
    _isPlaceholder(firebaseConfig.projectId) ||
    _isPlaceholder(firebaseConfig.appId);

if (!_configMissing) {
    firebase.initializeApp(firebaseConfig);
}
const auth = _configMissing ? null : firebase.auth();
const googleProvider = _configMissing ? null : new firebase.auth.GoogleAuthProvider();

// ── Constants ───────────────────────────────────────────────────────
const API_BASE = "http://localhost:8000/api/v1/diagnostics";

// ── DOM References ──────────────────────────────────────────────────
const loginContainer = document.getElementById("login-container");
const dashboardContainer = document.getElementById("dashboard-container");
const loginBtn = document.getElementById("login-btn");
const loginError = document.getElementById("login-error");
const logoutBtn = document.getElementById("logout-btn");
const userEmailBadge = document.getElementById("user-email");

const labForm = document.getElementById("lab-form");
const patientIdInput = document.getElementById("patient-id");
const analyzeBtn = document.getElementById("analyze-btn");
const resultsContainer = document.getElementById("results-container");
const resultsContent = document.getElementById("results-content");

const welcomePanel = document.getElementById("welcome-panel");
const lookupPanel = document.getElementById("lookup-panel");
const historyPatientId = document.getElementById("history-patient-id");
const loadHistoryBtn = document.getElementById("load-history-btn");
const historyContainer = document.getElementById("history-container");
const historySection = document.getElementById("history-section");
const trendCard = document.getElementById("trend-card");
const biomarkerSelector = document.getElementById("biomarker-selector");

// ── State ───────────────────────────────────────────────────────────
let authToken = null;
let trendChart = null;
let currentPatientHistory = [];

// ═══════════════════════════════════════════════════════════════════
//  AUTH
// ═══════════════════════════════════════════════════════════════════

if (_configMissing) {
    loginError.innerHTML =
        '🛑 <strong>Firebase config missing.</strong><br>' +
        'Open <code>frontend/app.js</code> and paste your Firebase web-app keys ' +
        'into the <code>firebaseConfig</code> object (lines 8–15).<br>' +
        '<a href="https://console.firebase.google.com" target="_blank">→ Firebase Console</a>';
    loginBtn.disabled = true;
    loginBtn.style.opacity = '0.5';
} else {
    auth.onAuthStateChanged(async (user) => {
        if (user) {
            authToken = await user.getIdToken();
            sessionStorage.setItem("aegis_token", authToken);
            userEmailBadge.textContent = user.email;
            showDashboard();
            await loadPatients();
        } else {
            authToken = null;
            sessionStorage.removeItem("aegis_token");
            showLogin();
        }
    });

    loginBtn.addEventListener("click", async () => {
        loginError.innerHTML = "";
        loginBtn.disabled = true;

        try {
            await auth.signInWithPopup(googleProvider);
        } catch (err) {
            loginError.innerHTML = diagnoseAuthError(err.code, err.message);
        } finally {
            loginBtn.disabled = false;
        }
    });
}

logoutBtn.addEventListener("click", () => auth.signOut());

function showDashboard() {
    loginContainer.style.display = "none";
    dashboardContainer.style.display = "block";
}

function showLogin() {
    loginContainer.style.display = "flex";
    dashboardContainer.style.display = "none";
}

function diagnoseAuthError(code, message) {
    const diagnostics = {
        "auth/unauthorized-domain":
            '🌐 <strong>Domain not authorized.</strong><br>' +
            'Go to <a href="https://console.firebase.google.com" target="_blank">Firebase Console</a> → ' +
            'Authentication → Settings → <strong>Authorized domains</strong> → Add <code>localhost</code>.',
        "auth/invalid-api-key":
            '🔑 <strong>Invalid API Key.</strong><br>' +
            'Your <code>apiKey</code> in <code>firebaseConfig</code> is incorrect. ' +
            'Copy the correct key from Firebase Console → Project Settings → Your Apps.',
        "auth/api-key-not-valid.-please-pass-a-valid-api-key.":
            '🔑 <strong>API Key not valid.</strong><br>' +
            'Regenerate it in Firebase Console → Project Settings.',
        "auth/operation-not-supported-in-this-environment":
            '⚠️ <strong>Protocol error.</strong><br>' +
            'Access via <code>http://localhost:8000</code>, not <code>file:///</code>.',
        "auth/popup-closed-by-user":
            'Sign-in popup was closed. Please try again.',
        "auth/cancelled-popup-request":
            'Only one sign-in popup allowed at a time.',
        "auth/popup-blocked":
            '🚫 <strong>Popup blocked.</strong> Allow popups in your browser for this site.',
        "auth/user-disabled": 'This account has been disabled.',
        "auth/too-many-requests": 'Too many attempts. Please wait a minute.',
        "auth/account-exists-with-different-credential":
            'An account already exists with this email using a different method.',
        "auth/network-request-failed":
            '📡 <strong>Network error.</strong> Check your internet connection.',
        "auth/internal-error":
            '⚙️ <strong>Internal error.</strong><br>' +
            'Ensure Google Sign-In is enabled: Firebase Console → Authentication → Sign-in method → Google → Enable.',
    };
    if (diagnostics[code]) return diagnostics[code];
    return `❌ <strong>${code || 'Unknown error'}</strong><br><span style="font-size:0.82rem;color:#5a6270">${message || 'No details.'}</span>`;
}

// ═══════════════════════════════════════════════════════════════════
//  PATIENT TOGGLE (New vs Existing)
// ═══════════════════════════════════════════════════════════════════

const patientRadios = document.querySelectorAll('input[name="patient-mode"]');
const newPatientFields = document.getElementById("new-patient-fields");
const existingFields = document.getElementById("existing-patient-fields");
const patientSelect = document.getElementById("patient-select");

patientRadios.forEach((radio) => {
    radio.addEventListener("change", () => {
        if (radio.value === "new") {
            newPatientFields.style.display = "block";
            existingFields.style.display = "none";
        } else {
            newPatientFields.style.display = "none";
            existingFields.style.display = "block";
        }
    });
});

// ═══════════════════════════════════════════════════════════════════
//  ACCORDION CATEGORIES
// ═══════════════════════════════════════════════════════════════════

document.querySelectorAll(".category-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
        const target = document.getElementById(btn.dataset.target);
        const isActive = btn.classList.contains("active");

        if (isActive) {
            btn.classList.remove("active");
            target.classList.add("collapsed");
        } else {
            btn.classList.add("active");
            target.classList.remove("collapsed");
        }
    });
});

// ═══════════════════════════════════════════════════════════════════
//  ADDITIONAL TESTS (Dynamic rows)
// ═══════════════════════════════════════════════════════════════════

const additionalList = document.getElementById("additional-tests-list");
const addTestBtn = document.getElementById("add-test-btn");

addTestBtn.addEventListener("click", () => {
    const row = document.createElement("div");
    row.className = "additional-row";
    row.innerHTML = `
        <input type="text" placeholder="Test name" class="additional-key" />
        <input type="number" step="any" placeholder="Value" class="additional-val" />
        <button type="button" class="btn-remove" title="Remove">×</button>
    `;
    row.querySelector(".btn-remove").addEventListener("click", () => row.remove());
    additionalList.appendChild(row);
});

// ═══════════════════════════════════════════════════════════════════
//  QUICK ACTIONS
// ═══════════════════════════════════════════════════════════════════

document.getElementById("quick-lookup-btn").addEventListener("click", () => {
    welcomePanel.style.display = "none";
    lookupPanel.style.display = "block";
    historySection.style.display = "block";
});

document.getElementById("quick-history-btn").addEventListener("click", () => {
    welcomePanel.style.display = "none";
    lookupPanel.style.display = "block";
    historySection.style.display = "block";
});

// ═══════════════════════════════════════════════════════════════════
//  LAB ANALYSIS — Form → JSON construction
// ═══════════════════════════════════════════════════════════════════

labForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const user = auth.currentUser;
    if (user) authToken = await user.getIdToken(true);

    // Build tests object from categorized inputs
    const tests = {};

    // Hematology + Chemistry (all named inputs inside lab-input-row)
    labForm.querySelectorAll(".lab-input-row input[name]").forEach((input) => {
        const val = input.value.trim();
        if (val !== "") {
            tests[input.name] = parseFloat(val);
        }
    });

    // Additional dynamic tests
    additionalList.querySelectorAll(".additional-row").forEach((row) => {
        const key = row.querySelector(".additional-key").value.trim();
        const val = row.querySelector(".additional-val").value.trim();
        if (key && val !== "") {
            tests[key] = parseFloat(val);
        }
    });

    if (Object.keys(tests).length === 0) {
        alert("Please enter at least one lab test value.");
        return;
    }

    // Determine patient ID and name
    const mode = document.querySelector('input[name="patient-mode"]:checked').value;
    let pid = null;
    let pname = null;
    if (mode === "new") {
        pid = patientIdInput.value.trim() || null;
        pname = document.getElementById("patient-name").value.trim() || null;
    } else {
        pid = patientSelect.value || null;
    }

    const payload = { tests, patient_id: pid, patient_name: pname };

    // UI: loading state
    const btnText = analyzeBtn.querySelector(".btn-text");
    const btnSpinner = analyzeBtn.querySelector(".btn-spinner");
    btnText.textContent = "Analyzing…";
    btnSpinner.style.display = "inline-block";
    analyzeBtn.disabled = true;
    resultsContainer.style.display = "none";

    try {
        const res = await fetch(`${API_BASE}/analyze`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${authToken}`,
            },
            body: JSON.stringify(payload),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server error ${res.status}`);
        }

        const report = await res.json();

        // Hide welcome, show results
        welcomePanel.style.display = "none";
        lookupPanel.style.display = "none";
        renderReport(report);
        resultsContainer.style.display = "block";

        // Refresh patient dropdown from server
        await loadPatients();

        // Auto-load history if patient_id was provided
        if (pid) {
            historyPatientId.value = pid;
            await loadPatientHistory(pid);
        }
    } catch (err) {
        alert(`Analysis failed: ${err.message}`);
    } finally {
        btnText.textContent = "Analyze Results";
        btnSpinner.style.display = "none";
        analyzeBtn.disabled = false;
    }
});

// ═══════════════════════════════════════════════════════════════════
//  LOAD PATIENTS (from API)
// ═══════════════════════════════════════════════════════════════════

async function loadPatients() {
    try {
        const user = auth.currentUser;
        if (user) authToken = await user.getIdToken(true);

        const res = await fetch(`${API_BASE}/patients`, {
            headers: { Authorization: `Bearer ${authToken}` },
        });

        if (!res.ok) return;

        const patients = await res.json();

        // Rebuild the dropdown
        patientSelect.innerHTML = '<option value="" disabled selected>— Select a patient —</option>';
        patients.forEach((p) => {
            const opt = document.createElement("option");
            opt.value = p.patient_ref;
            opt.textContent = `${p.name} — ${p.patient_ref}`;
            patientSelect.appendChild(opt);
        });
    } catch (err) {
        console.warn("Failed to load patients:", err);
    }
}

function renderReport(r) {
    resultsContent.innerHTML = `
        <div class="report-section">
            <h3>Risk Level</h3>
            <span class="risk-badge risk-${r.risk_level}">${r.risk_level}</span>
        </div>

        <div class="report-section">
            <h3>Summary</h3>
            <p>${escapeHtml(r.summary)}</p>
        </div>

        <div class="report-section">
            <h3>Abnormal Values</h3>
            <ul>${r.abnormal_values.map((v) => `<li>${escapeHtml(v)}</li>`).join("")}</ul>
        </div>

        <div class="report-section">
            <h3>Possible Conditions</h3>
            ${r.possible_conditions
            .map(
                (c) => `
                <div class="condition-bar">
                    <span class="condition-name">${escapeHtml(c.name)}</span>
                    <div class="condition-track">
                        <div class="condition-fill" style="width:${c.confidence_percentage}%"></div>
                    </div>
                    <span class="condition-pct">${c.confidence_percentage}%</span>
                </div>`
            )
            .join("")}
        </div>

        <div class="report-section">
            <h3>Explanation</h3>
            <p>${escapeHtml(r.explanation)}</p>
        </div>

        <div class="report-section">
            <h3>Recommended Actions</h3>
            <ul>${r.recommended_actions.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul>
        </div>

        ${r.alerts && r.alerts.length
            ? `<div class="report-section">
                <h3>⚠ Alerts</h3>
                ${r.alerts.map((a) => `<div class="alert-banner">${escapeHtml(a)}</div>`).join("")}
            </div>`
            : ""
        }
    `;
}

// ═══════════════════════════════════════════════════════════════════
//  PATIENT HISTORY
// ═══════════════════════════════════════════════════════════════════

loadHistoryBtn.addEventListener("click", async () => {
    const pid = historyPatientId.value.trim();
    if (!pid) {
        alert("Please enter a Patient ID.");
        return;
    }
    await loadPatientHistory(pid);
});

async function loadPatientHistory(patientId) {
    const user = auth.currentUser;
    if (user) authToken = await user.getIdToken(true);

    historySection.style.display = "block";
    historyContainer.innerHTML = '<p class="empty-state">Loading…</p>';

    try {
        const res = await fetch(`${API_BASE}/history/${encodeURIComponent(patientId)}`, {
            headers: { Authorization: `Bearer ${authToken}` },
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server error ${res.status}`);
        }

        const records = await res.json();
        currentPatientHistory = records;

        if (!records.length) {
            historyContainer.innerHTML = '<p class="empty-state">No records found for this patient.</p>';
            trendCard.style.display = "none";
            return;
        }

        historyContainer.innerHTML = `
            <table class="history-table">
                <thead>
                    <tr><th>Date</th><th>AI Summary</th><th>Risk</th></tr>
                </thead>
                <tbody>
                    ${records
                .map(
                    (r) => `
                        <tr>
                            <td style="white-space:nowrap">${formatDate(r.created_at)}</td>
                            <td>${escapeHtml(r.ai_summary)}</td>
                            <td><span class="risk-badge risk-${r.risk_level}">${r.risk_level}</span></td>
                        </tr>`
                )
                .join("")}
                </tbody>
            </table>
        `;

        // Add to existing patient dropdown
        addPatientToDropdown(patientId);

        // Show trend chart
        trendCard.style.display = "block";
        renderChart(biomarkerSelector.value);
    } catch (err) {
        historyContainer.innerHTML = `<p class="empty-state" style="color:var(--risk-critical)">Failed: ${escapeHtml(err.message)}</p>`;
        trendCard.style.display = "none";
    }
}

// ═══════════════════════════════════════════════════════════════════
//  BIOMARKER TREND CHART
// ═══════════════════════════════════════════════════════════════════

biomarkerSelector.addEventListener("change", (e) => renderChart(e.target.value));

function renderChart(metricKey) {
    if (!currentPatientHistory.length) return;

    const sorted = [...currentPatientHistory].reverse();

    const labels = sorted.map((r) => {
        if (!r.created_at) return "—";
        return new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    });

    const dataPoints = sorted.map((r) => {
        if (!r.raw_data || r.raw_data[metricKey] === undefined) return null;
        const val = parseFloat(r.raw_data[metricKey]);
        return isNaN(val) ? null : val;
    });

    const canvas = document.getElementById("biomarkerChart");
    const ctx = canvas.getContext("2d");
    if (trendChart) { trendChart.destroy(); trendChart = null; }

    const hasData = dataPoints.some((v) => v !== null);

    trendChart = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                label: metricKey,
                data: dataPoints,
                borderColor: "#008080",
                backgroundColor: "rgba(0,128,128,0.06)",
                borderWidth: 2.5,
                pointBackgroundColor: "#008080",
                pointBorderColor: "#fff",
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.3,
                fill: true,
                spanGaps: true,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#1E293B",
                    titleColor: "#F0F4F8",
                    bodyColor: "#F0F4F8",
                    titleFont: { family: "'Inter'", weight: "600", size: 13 },
                    bodyFont: { family: "'Inter'", size: 12 },
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: false,
                    callbacks: {
                        label: (ctx) => ctx.parsed.y === null ? `${metricKey}: N/A` : `${metricKey}: ${ctx.parsed.y}`,
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { family: "'Inter'", size: 11, weight: "500" }, color: "#94A3B8" },
                    border: { display: false },
                },
                y: {
                    grid: { color: "rgba(0,0,0,0.03)", drawBorder: false },
                    ticks: { font: { family: "'Inter'", size: 11 }, color: "#94A3B8", padding: 8 },
                    border: { display: false },
                    beginAtZero: false,
                },
            },
        },
    });

    if (!hasData) {
        ctx.save();
        ctx.font = "500 14px Inter, sans-serif";
        ctx.fillStyle = "#94A3B8";
        ctx.textAlign = "center";
        ctx.fillText(`No "${metricKey}" data found`, canvas.width / 2, canvas.height / 2);
        ctx.restore();
    }
}

// ═══════════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════════

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}

function formatDate(isoStr) {
    if (!isoStr) return "—";
    return new Date(isoStr).toLocaleDateString("en-US", {
        year: "numeric", month: "short", day: "numeric",
        hour: "2-digit", minute: "2-digit",
    });
}
