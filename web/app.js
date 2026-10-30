/**
 * YottaFlex FairCollect AI — Frontend Controller & State Manager
 * Handles all 4 Personas: Operations Analyst, Risk & Compliance, Customer, Administrator.
 */

// Global State
let currentPersona = "analyst";
let selectedCaseId = null;
let selectedCustomerId = null;
let allCasesCache = [];

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  loadAnalystCases();
  loadComplianceSummary();
  scanComplianceAnomalies();
  loadAuditEvents();
  loadSystemMetrics();
  loadSampleCustomers();
}

// -------------------------------------------------------------
// Persona Switching
// -------------------------------------------------------------
function switchPersona(persona) {
  currentPersona = persona;

  // Update nav buttons
  document.querySelectorAll(".persona-btn").forEach(btn => btn.classList.remove("active"));
  const activeBtn = document.getElementById(`tab-${persona}-btn`);
  if (activeBtn) activeBtn.classList.add("active");

  // Update view sections
  document.querySelectorAll(".tab-content").forEach(view => view.classList.remove("active"));
  const activeView = document.getElementById(`view-${persona}`);
  if (activeView) activeView.classList.add("active");

  // Load relevant data on switch
  if (persona === "analyst") {
    loadAnalystCases();
  } else if (persona === "compliance") {
    loadComplianceSummary();
    scanComplianceAnomalies();
    loadAuditEvents();
  } else if (persona === "customer") {
    if (!selectedCustomerId) {
      const select = document.getElementById("cust-switcher-select");
      if (select && select.value) {
        selectedCustomerId = select.value;
      }
    }
    if (selectedCustomerId) {
      loadCustomerOverview(selectedCustomerId);
    }
  } else if (persona === "admin") {
    loadSystemMetrics();
  }
}

// -------------------------------------------------------------
// 1. Analyst View Logic
// -------------------------------------------------------------
async function loadAnalystCases() {
  const tier = document.getElementById("analyst-tier-filter")?.value || "";
  const status = document.getElementById("analyst-status-filter")?.value || "";
  const search = document.getElementById("analyst-search-input")?.value || "";

  const tbody = document.getElementById("analyst-cases-tbody");
  tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 2rem;">Loading prioritized accounts...</td></tr>`;

  try {
    let url = `/api/cases?limit=100`;
    if (tier) url += `&tier=${encodeURIComponent(tier)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    const res = await fetch(url);
    const data = await res.json();
    allCasesCache = data.items || [];

    // Update KPI stats
    updateAnalystStats(allCasesCache);

    if (allCasesCache.length === 0) {
      tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 2rem;">No delinquent accounts found matching filters.</td></tr>`;
      return;
    }

    tbody.innerHTML = allCasesCache.map(c => {
      const tierBadgeClass = getTierBadgeClass(c.priority_tier);
      const formattedArrears = formatCurrency(c.total_arrears);
      const borrowerName = `${c.first_name} ${c.last_name}`;
      
      // Calculate local time display
      const localTimeStr = c.permissible_start_time ? `${c.timezone.split("/")[1]} (Pref ${c.permissible_start_time}-${c.permissible_end_time})` : c.timezone;

      return `
        <tr>
          <td><span class="badge ${tierBadgeClass}">${c.priority_tier.split("_")[0]}</span></td>
          <td><strong style="color: #fff;">${c.priority_score.toFixed(1)}</strong></td>
          <td class="mono" style="color: var(--text-accent); font-weight: 500;">${c.case_id}</td>
          <td>
            <div style="font-weight: 600;">${borrowerName}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${c.phone_number}</div>
          </td>
          <td class="mono">${c.loan_id}</td>
          <td style="font-weight: 700; color: var(--color-warning);">${formattedArrears}</td>
          <td><span style="font-weight: 600;">${c.days_past_due}d</span></td>
          <td><span class="badge badge-status">${c.risk_segment}</span></td>
          <td><span class="badge ${getStatusBadgeClass(c.case_status)}">${c.case_status}</span></td>
          <td style="font-size: 0.75rem; color: var(--text-secondary);">${localTimeStr}</td>
          <td>
            <button class="btn btn-primary btn-sm" onclick="openCaseModal('${c.case_id}')">
              Review & Act
            </button>
          </td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading analyst cases:", err);
    tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--color-danger); padding: 2rem;">Error loading cases.</td></tr>`;
  }
}

function updateAnalystStats(cases) {
  const activeCases = cases.filter(c => c.case_status === "ACTIVE" || c.case_status === "PENDING_PTP");
  const p1Cases = cases.filter(c => c.priority_tier === "P1_CRITICAL");
  const totalArrears = cases.reduce((acc, c) => acc + (c.total_arrears || 0), 0);
  const activePtps = cases.filter(c => c.active_ptp_id !== null);

  document.getElementById("analyst-active-cases-val").textContent = activeCases.length;
  document.getElementById("analyst-p1-cases-val").textContent = p1Cases.length;
  document.getElementById("analyst-queue-arrears-val").textContent = formatCurrency(totalArrears);
  document.getElementById("analyst-active-ptps-val").textContent = activePtps.length;
}

function onAnalystFilterChange() {
  loadAnalystCases();
}

// -------------------------------------------------------------
// Case Details & Modal
// -------------------------------------------------------------
async function openCaseModal(caseId) {
  selectedCaseId = caseId;
  const overlay = document.getElementById("case-modal-overlay");
  overlay.classList.add("active");

  const feedback = document.getElementById("m-outreach-feedback");
  feedback.style.display = "none";

  try {
    const res = await fetch(`/api/cases/${caseId}/details`);
    const data = await res.json();
    const c = data.case;
    const cust = data.customer;
    const loan = data.loan;
    const explain = data.explainability;

    document.getElementById("modal-case-title").textContent = `Case ${c.case_id} — ${cust.first_name} ${cust.last_name}`;
    document.getElementById("modal-case-subtitle").textContent = `Loan: ${loan.loan_id} | Status: ${c.case_status}`;

    document.getElementById("m-borrower-name").textContent = `${cust.first_name} ${cust.last_name}`;
    document.getElementById("m-borrower-time").textContent = `${cust.timezone}`;
    document.getElementById("m-borrower-arrears").textContent = formatCurrency(loan.total_arrears);
    document.getElementById("m-borrower-dpd").textContent = `${loan.days_past_due} Days Past Due`;

    // Explainability score breakdown
    const scoreVal = explain.priority_score;
    const tierBadge = document.getElementById("m-priority-badge");
    tierBadge.className = `badge ${getTierBadgeClass(explain.priority_tier)}`;
    tierBadge.textContent = `${explain.priority_tier} (${scoreVal.toFixed(1)} / 100)`;

    document.getElementById("m-priority-meter-fill").style.width = `${Math.min(100, scoreVal)}%`;
    document.getElementById("m-factor-arrears").textContent = `+${explain.explainability.arrears_exposure_points} pts`;
    document.getElementById("m-factor-dpd").textContent = `+${explain.explainability.aging_dpd_points} pts`;
    document.getElementById("m-factor-risk").textContent = `+${explain.explainability.risk_segment_points} pts`;
    document.getElementById("m-factor-ptp").textContent = `${explain.explainability.commitment_history_adjustment >= 0 ? '+' : ''}${explain.explainability.commitment_history_adjustment} pts`;

    // Prefill modal PTP date (default 5 days from now)
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 5);
    document.getElementById("modal-ptp-date-input").value = futureDate.toISOString().split("T")[0];
    document.getElementById("modal-ptp-amount-input").value = (loan.total_arrears * 0.5).toFixed(2);

    // Guardrail pill
    const guardrailPill = document.getElementById("m-guardrail-pill");
    if (cust.dispute_status === "ACTIVE_DISPUTE") {
      guardrailPill.className = "badge badge-danger";
      guardrailPill.textContent = "🛑 Active Dispute Moratorium";
    } else if (cust.hardship_status !== "NONE") {
      guardrailPill.className = "badge badge-warning";
      guardrailPill.textContent = `🛑 Hardship: ${cust.hardship_status}`;
    } else if (cust.cease_desist_flag) {
      guardrailPill.className = "badge badge-danger";
      guardrailPill.textContent = "🛑 Cease & Desist Enforced";
    } else {
      guardrailPill.className = "badge badge-success";
      guardrailPill.textContent = "✓ Compliant Window Active";
    }

  } catch (err) {
    console.error("Error opening case modal:", err);
  }
}

function closeCaseModal() {
  document.getElementById("case-modal-overlay").classList.remove("active");
  selectedCaseId = null;
}

async function executeOutreach(channel) {
  if (!selectedCaseId) return;
  const feedback = document.getElementById("m-outreach-feedback");
  feedback.style.display = "block";
  feedback.style.background = "rgba(99, 102, 241, 0.1)";
  feedback.style.color = "var(--text-accent)";
  feedback.textContent = `Evaluating legal guardrails and executing ${channel} outreach...`;

  try {
    const res = await fetch(`/api/cases/${selectedCaseId}/attempt-contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, agent_notes: "Operations outreach initiated from workbench." })
    });
    const data = await res.json();

    if (data.blocked) {
      feedback.style.background = "rgba(239, 68, 68, 0.15)";
      feedback.style.color = "#fca5a5";
      feedback.style.border = "1px solid rgba(239, 68, 68, 0.4)";
      feedback.innerHTML = `<strong>🛑 OUTBOUND CONTACT BLOCKED BY GUARDRAIL:</strong><br>${data.reason} (Rule: ${data.rule_triggered})`;
      showToast(data.reason, "error");
    } else {
      feedback.style.background = "rgba(16, 185, 129, 0.15)";
      feedback.style.color = "#6ee7b7";
      feedback.style.border = "1px solid rgba(16, 185, 129, 0.4)";
      feedback.innerHTML = `<strong>✓ COMPLIANT CONTACT LOGGED:</strong><br>Attempt ID ${data.attempt_id} recorded. Customer local time: ${data.customer_local_time}. Status: ${data.compliance_status}.`;
      showToast(`Outreach recorded successfully (${channel})`, "success");
      loadAnalystCases();
    }
  } catch (err) {
    feedback.textContent = "Error executing outreach.";
  }
}

async function recordPTPFromModal() {
  if (!selectedCaseId) return;
  const dateVal = document.getElementById("modal-ptp-date-input").value;
  const amountVal = parseFloat(document.getElementById("modal-ptp-amount-input").value);

  if (!dateVal || isNaN(amountVal) || amountVal <= 0) {
    showToast("Please provide valid promise date and positive amount", "error");
    return;
  }

  try {
    const res = await fetch(`/api/cases/${selectedCaseId}/record-promise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ promise_due_date: dateVal, promised_amount: amountVal })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Promise to Pay registered: ${data.ptp_id}`, "success");
      closeCaseModal();
      loadAnalystCases();
    }
  } catch (err) {
    showToast("Failed to record commitment", "error");
  }
}

// -------------------------------------------------------------
// 2. Risk & Compliance Logic
// -------------------------------------------------------------
async function loadComplianceSummary() {
  try {
    const res = await fetch("/api/compliance/summary");
    const data = await res.json();

    document.getElementById("comp-rate-val").textContent = `${data.compliance_rate_pct}%`;
    document.getElementById("comp-violations-val").textContent = data.violations_count;
    document.getElementById("comp-disputes-val").textContent = data.regulatory_holds.active_disputes;
    document.getElementById("comp-ptp-kept-rate").textContent = `${data.commitment_metrics.fulfillment_rate_pct}%`;
  } catch (err) {
    console.error("Error loading compliance summary:", err);
  }
}

async function scanComplianceAnomalies() {
  const container = document.getElementById("anomalies-list-container");
  container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem;">Scanning database tables for the 5 negative scenarios...</p>`;

  try {
    const res = await fetch("/api/compliance/anomalies");
    const data = await res.json();
    const anomalies = data.anomalies || [];

    if (anomalies.length === 0) {
      container.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-md); padding: 1.25rem; color: var(--color-success);">
          <strong>✓ 100% CLEAN: Zero Compliance Anomalies Detected.</strong>
          <p style="font-size: 0.8rem; margin-top: 0.25rem; color: var(--text-secondary);">
            All paid accounts closed, quiet hours observed, payments chronologically allocated, commitments reasonable, and disputes frozen.
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = anomalies.map(a => `
      <div class="anomaly-item" id="anomaly-item-${a.anomaly_id}">
        <div class="anomaly-info">
          <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem;">
            <span class="badge badge-danger">${a.severity}</span>
            <span class="badge badge-status">${a.entity_type}</span>
            <span class="mono" style="font-size: 0.75rem; color: var(--text-muted);">${a.anomaly_id}</span>
          </div>
          <h4>${formatIssueType(a.issue_type)}</h4>
          <p style="font-size: 0.82rem; color: var(--text-secondary);">${a.description}</p>
          <div class="anomaly-rule">Rule: <code>${a.detection_rule}</code> | Expected Decision: <code>${a.expected_decision}</code></div>
        </div>
        <div>
          <button class="btn btn-danger btn-sm" onclick="remediateAnomaly('${a.anomaly_id}', '${a.issue_type}', '${a.entity_id}')">
            ⚡ Remediate Now
          </button>
        </div>
      </div>
    `).join("");

  } catch (err) {
    container.innerHTML = `<p style="color: var(--color-danger);">Error scanning for anomalies.</p>`;
  }
}

async function remediateAnomaly(anomalyId, issueType, entityId) {
  try {
    const res = await fetch("/api/compliance/remediate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ anomaly_id: anomalyId, issue_type: issueType, entity_id: entityId })
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      showToast(`Remediated: ${data.message}`, "success");
      scanComplianceAnomalies();
      loadComplianceSummary();
      loadAuditEvents();
    }
  } catch (err) {
    showToast("Remediation failed", "error");
  }
}

async function loadAuditEvents() {
  const tbody = document.getElementById("audit-events-tbody");
  try {
    const res = await fetch("/api/audit-events?limit=25");
    const data = await res.json();
    const events = data.events || [];

    if (events.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No audit events recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = events.map(e => `
      <tr>
        <td class="mono" style="font-size: 0.75rem; color: var(--text-secondary);">${e.event_timestamp ? e.event_timestamp.replace('T', ' ').substring(0, 19) : ''}</td>
        <td><span class="badge badge-status">${e.actor_persona}</span></td>
        <td><strong>${e.entity_name}</strong></td>
        <td class="mono">${e.entity_id}</td>
        <td><strong style="color: var(--text-accent);">${e.action}</strong></td>
        <td><span style="font-size: 0.75rem; color: var(--text-muted);">${e.previous_state || '—'}</span></td>
        <td><span style="font-size: 0.75rem; color: #fff;">${e.new_state || '—'}</span></td>
        <td style="font-size: 0.75rem; color: var(--text-secondary);">${e.notes || ''}</td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--color-danger);">Error loading audit events.</td></tr>`;
  }
}

// -------------------------------------------------------------
// 3. Customer Portal Logic
// -------------------------------------------------------------
async function loadSampleCustomers() {
  try {
    const res = await fetch("/api/cases?limit=20");
    const data = await res.json();
    const cases = data.items || [];
    const select = document.getElementById("cust-switcher-select");
    select.innerHTML = cases.map(c => `
      <option value="${c.customer_id}">${c.first_name} ${c.last_name} (${c.customer_id} — ${c.priority_tier})</option>
    `).join("");

    if (cases.length > 0) {
      selectedCustomerId = cases[0].customer_id;
      loadCustomerOverview(selectedCustomerId);
    }
  } catch (err) {
    console.error("Error loading sample customers:", err);
  }
}

function onCustomerSelectChange(customerId) {
  selectedCustomerId = customerId;
  loadCustomerOverview(customerId);
}

async function loadCustomerOverview(customerId) {
  try {
    const res = await fetch(`/api/customer/${customerId}/overview`);
    const data = await res.json();
    const cust = data.customer;
    const loans = data.loans || [];

    document.getElementById("cust-portal-name").textContent = `${cust.first_name} ${cust.last_name} (${cust.customer_id})`;

    if (loans.length > 0) {
      const primaryLoan = loans[0];
      const l = primaryLoan.loan;
      const inss = primaryLoan.installments || [];
      const ptps = primaryLoan.promises || [];

      document.getElementById("cust-balance-val").textContent = formatCurrency(l.current_balance);
      document.getElementById("cust-loan-meta").textContent = `Loan ${l.loan_id} (${l.loan_type})`;
      document.getElementById("cust-arrears-val").textContent = formatCurrency(l.total_arrears);
      document.getElementById("cust-dpd-meta").textContent = `${l.days_past_due} Days Overdue`;

      // Protection status
      const statusPill = document.getElementById("cust-status-badge-val");
      const metaPill = document.getElementById("cust-protection-meta");
      if (cust.dispute_status === "ACTIVE_DISPUTE") {
        statusPill.textContent = "Under Formal Dispute";
        statusPill.style.color = "#f87171";
        metaPill.textContent = "Moratorium active under FDCPA Sec 809";
      } else if (cust.hardship_status !== "NONE") {
        statusPill.textContent = `Hardship: ${cust.hardship_status}`;
        statusPill.style.color = "#fbbf24";
        metaPill.textContent = "Outreach paused under hardship relief";
      } else {
        statusPill.textContent = l.loan_status;
        statusPill.style.color = l.loan_status === "PAID_OFF" ? "var(--color-success)" : "var(--text-accent)";
        metaPill.textContent = l.loan_status === "PAID_OFF" ? "Account settled in full" : "Standard collections workflow";
      }

      // Active commitment PTP
      const activePtp = ptps.find(p => p.ptp_status === "PENDING");
      if (activePtp) {
        document.getElementById("cust-ptp-status-val").textContent = `$${activePtp.promised_amount.toFixed(2)}`;
        document.getElementById("cust-ptp-meta").textContent = `Due ${activePtp.promise_due_date} (PTP ${activePtp.ptp_id})`;
      } else {
        document.getElementById("cust-ptp-status-val").textContent = "None";
        document.getElementById("cust-ptp-meta").textContent = "No active promise to pay";
      }

      // Render Installments Table
      const inssTbody = document.getElementById("cust-installments-tbody");
      inssTbody.innerHTML = inss.map(i => `
        <tr>
          <td><strong style="color: var(--text-accent);">#${i.installment_number}</strong></td>
          <td class="mono">${i.due_date}</td>
          <td>${formatCurrency(i.principal_due)}</td>
          <td>${formatCurrency(i.interest_due)}</td>
          <td><strong>${formatCurrency(i.total_amount_due)}</strong></td>
          <td style="color: var(--color-success);">${formatCurrency(i.amount_paid)}</td>
          <td style="font-weight: 700; color: ${i.remaining_balance > 0 ? 'var(--color-warning)' : 'var(--text-muted)'};">${formatCurrency(i.remaining_balance)}</td>
          <td>${i.days_overdue > 0 ? `<span style="color: var(--color-danger); font-weight: 600;">${i.days_overdue}d</span>` : '0d'}</td>
          <td><span class="badge ${getStatusBadgeClass(i.status)}">${i.status}</span></td>
        </tr>
      `).join("");

      // Prefill payment amount
      document.getElementById("cust-pay-amount-input").value = l.total_arrears > 0 ? l.total_arrears.toFixed(2) : l.current_balance.toFixed(2);
    }
  } catch (err) {
    console.error("Error loading customer overview:", err);
  }
}

async function submitCustomerPayment() {
  if (!selectedCustomerId) return;
  const amount = parseFloat(document.getElementById("cust-pay-amount-input").value);
  const method = document.getElementById("cust-pay-method-select").value;
  const feedback = document.getElementById("cust-pay-feedback");

  if (isNaN(amount) || amount <= 0) {
    showToast("Please enter a valid positive payment amount.", "error");
    return;
  }

  feedback.innerHTML = `<span style="color: var(--text-accent);">Processing waterfall repayment...</span>`;

  try {
    // Fetch loan id
    const overviewRes = await fetch(`/api/customer/${selectedCustomerId}/overview`);
    const overviewData = await overviewRes.json();
    const loanId = overviewData.loans[0].loan.loan_id;

    const res = await fetch(`/api/customer/${selectedCustomerId}/pay?loan_id=${loanId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount, payment_method: method })
    });
    const data = await res.json();

    if (data.success) {
      const r = data.result;
      feedback.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); padding: 0.75rem; border-radius: var(--radius-sm); color: #6ee7b7;">
          <strong>✓ Repayment of ${formatCurrency(amount)} Applied via Waterfall!</strong><br>
          Payment ID: <code>${r.payment_id}</code> | New Balance: ${formatCurrency(r.new_balance)} | New Arrears: ${formatCurrency(r.new_arrears)}
          ${r.case_status === "CLOSED_PAID" ? "<br><strong>🎉 Account Settled: Collection Case Automatically Closed (CLOSED_PAID)!</strong>" : ""}
        </div>
      `;
      showToast(`Repayment of ${formatCurrency(amount)} credited successfully`, "success");
      loadCustomerOverview(selectedCustomerId);
    }
  } catch (err) {
    feedback.innerHTML = `<span style="color: var(--color-danger);">Error submitting repayment.</span>`;
  }
}

async function submitCustomerPTP() {
  if (!selectedCustomerId) return;
  const dateVal = document.getElementById("cust-ptp-date-input").value;
  const amountVal = parseFloat(document.getElementById("cust-ptp-amount-input").value);
  const feedback = document.getElementById("cust-ptp-feedback");

  if (!dateVal || isNaN(amountVal) || amountVal <= 0) {
    showToast("Please provide commitment date and amount", "error");
    return;
  }

  try {
    const overviewRes = await fetch(`/api/customer/${selectedCustomerId}/overview`);
    const overviewData = await overviewRes.json();
    const loanId = overviewData.loans[0].loan.loan_id;

    // Find case id
    const casesRes = await fetch(`/api/cases?limit=200`);
    const casesData = await casesRes.json();
    const userCase = casesData.items.find(c => c.customer_id === selectedCustomerId);

    if (!userCase) {
      showToast("No active collection case found for this customer", "error");
      return;
    }

    const res = await fetch(`/api/cases/${userCase.case_id}/record-promise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ promise_due_date: dateVal, promised_amount: amountVal })
    });
    const data = await res.json();

    if (data.success) {
      feedback.innerHTML = `
        <div style="color: var(--color-success); margin-top: 0.5rem;">
          ✓ Commitment registered (${data.ptp_id}). Collection outreach is paused until ${dateVal}.
        </div>
      `;
      showToast("Payment commitment registered!", "success");
      loadCustomerOverview(selectedCustomerId);
    }
  } catch (err) {
    feedback.innerHTML = `<span style="color: var(--color-danger);">Failed to register commitment.</span>`;
  }
}

async function submitCustomerRightsRequest() {
  if (!selectedCustomerId) return;
  const actionType = document.getElementById("cust-rights-type-select").value;
  const notes = document.getElementById("cust-rights-notes-input").value || "Consumer statutory protection requested";
  const feedback = document.getElementById("cust-rights-feedback");

  try {
    const res = await fetch(`/api/customer/${selectedCustomerId}/assistance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action_type: actionType,
        status_value: actionType === "DISPUTE" ? "ACTIVE_DISPUTE" : "TEMPORARY_UNEMPLOYMENT",
        notes: notes
      })
    });
    const data = await res.json();

    if (data.success) {
      feedback.innerHTML = `
        <div style="color: var(--color-warning); margin-top: 0.5rem;">
          ✓ Statutory freeze active. Outbound dialer & collection outreach immediately stopped.
        </div>
      `;
      showToast("Consumer rights freeze applied", "success");
      loadCustomerOverview(selectedCustomerId);
    }
  } catch (err) {
    feedback.innerHTML = `<span style="color: var(--color-danger);">Error submitting request.</span>`;
  }
}

// -------------------------------------------------------------
// 4. System Administrator Logic
// -------------------------------------------------------------
async function loadSystemMetrics() {
  try {
    const res = await fetch("/api/system/metrics");
    const data = await res.json();
    const p = data.portfolio;

    document.getElementById("admin-originated-val").textContent = formatCurrency(p.total_originated_usd);
    document.getElementById("admin-total-loans-meta").textContent = `${p.total_loans.toLocaleString()} Total Loans Originated`;
    document.getElementById("admin-balance-val").textContent = formatCurrency(p.current_balance_usd);
    document.getElementById("admin-arrears-val").textContent = formatCurrency(p.total_arrears_usd);
    document.getElementById("admin-collected-val").textContent = formatCurrency(p.total_repayments_collected_usd);

    // Render Delinquency Buckets table
    const bucketsTbody = document.getElementById("admin-buckets-tbody");
    const dpdRanges = {
      "CURRENT": "0 Days (Current)",
      "30_DPD": "1 - 30 Days Past Due",
      "60_DPD": "31 - 60 Days Past Due",
      "90_DPD": "61 - 90 Days Past Due",
      "120_PLUS_DPD": "91+ Days (Severe/Chargeoff)"
    };
    const riskLevels = {
      "CURRENT": "Normal (Low)",
      "30_DPD": "Early Delinquency",
      "60_DPD": "Moderate Escalation",
      "90_DPD": "Severe Impairment",
      "120_PLUS_DPD": "Critical Recovery / Chargeoff"
    };

    bucketsTbody.innerHTML = (data.delinquency_buckets || []).map(b => `
      <tr>
        <td><strong>${b.delinquency_bucket}</strong></td>
        <td>${dpdRanges[b.delinquency_bucket] || b.delinquency_bucket}</td>
        <td><strong style="color: #fff;">${b.count.toLocaleString()}</strong></td>
        <td style="font-weight: 700; color: var(--color-warning);">${formatCurrency(b.arrears)}</td>
        <td><span class="badge ${b.delinquency_bucket === 'CURRENT' ? 'badge-success' : 'badge-danger'}">${riskLevels[b.delinquency_bucket]}</span></td>
      </tr>
    `).join("");

  } catch (err) {
    console.error("Error loading system metrics:", err);
  }
}

async function runDataGenerator() {
  const profile = document.getElementById("admin-gen-profile").value;
  const seed = parseInt(document.getElementById("admin-gen-seed").value) || 20261022;
  const feedback = document.getElementById("admin-gen-feedback");
  const btn = document.getElementById("btn-admin-run-generator");

  btn.disabled = true;
  feedback.innerHTML = `<span style="color: var(--text-accent);">Generating synthetic data and populating database...</span>`;

  try {
    const res = await fetch("/api/system/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile, seed })
    });
    const data = await res.json();

    if (data.success) {
      const c = data.counts;
      feedback.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); padding: 0.75rem; border-radius: var(--radius-sm); color: #6ee7b7; margin-top: 0.5rem;">
          <strong>✓ Generation Complete! (Seed ${seed}, Profile '${profile}')</strong><br>
          Loans: ${c.loans.toLocaleString()} | Installments: ${c.installments.toLocaleString()} | Payments: ${c.payments.toLocaleString()} | Anomalies: ${c.ground_truth_anomalies}
        </div>
      `;
      showToast("Data generation finished!", "success");
      loadSystemMetrics();
      loadAnalystCases();
      scanComplianceAnomalies();
    }
  } catch (err) {
    feedback.innerHTML = `<span style="color: var(--color-danger);">Error generating data.</span>`;
  } finally {
    btn.disabled = false;
  }
}

async function runAdminValidationSuite() {
  const summaryPill = document.getElementById("admin-validation-summary-pill");
  const list = document.getElementById("admin-validation-list");
  summaryPill.textContent = "Running 41 checks...";
  list.innerHTML = "";

  try {
    const res = await fetch("/api/system/validate");
    const data = await res.json();

    if (data.all_passed) {
      summaryPill.style.color = "var(--color-success)";
      summaryPill.textContent = `All ${data.total_checks} Checks Passed [PASS]`;
    } else {
      summaryPill.style.color = "var(--color-danger)";
      summaryPill.textContent = `${data.passed} Passed / ${data.failed} Failed`;
    }

    list.innerHTML = data.details.map(d => `
      <div style="padding: 0.25rem 0; border-bottom: 1px solid rgba(255,255,255,0.05); color: ${d.status === 'PASS' ? '#6ee7b7' : '#fca5a5'};">
        [${d.status}] ${d.category} — ${d.name}: ${d.message}
      </div>
    `).join("");

    showToast("Validation suite complete", data.all_passed ? "success" : "error");
  } catch (err) {
    summaryPill.textContent = "Validation execution failed";
  }
}

// -------------------------------------------------------------
// Helpers & Utilities
// -------------------------------------------------------------
function formatCurrency(val) {
  if (val === undefined || val === null) return "$0.00";
  return "$" + Number(val).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function getTierBadgeClass(tier) {
  switch (tier) {
    case "P1_CRITICAL": return "badge-p1";
    case "P2_HIGH": return "badge-p2";
    case "P3_MEDIUM": return "badge-p3";
    default: return "badge-p4";
  }
}

function getStatusBadgeClass(status) {
  switch (status) {
    case "ACTIVE": return "badge-danger";
    case "PENDING_PTP": return "badge-warning";
    case "UNDER_DISPUTE": return "badge-danger";
    case "HARDSHIP_HOLD": return "badge-warning";
    case "PAID":
    case "CLOSED_PAID":
    case "RESOLVED": return "badge-success";
    default: return "badge-status";
  }
}

function formatIssueType(type) {
  return type.replace(/_/g, " ");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✓' : '⚠️'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}
