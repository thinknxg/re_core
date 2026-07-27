/**
 * tenant-portal-api.js
 *
 * Drop this <script> into tenant_portal (1).html (or its own <script src="">
 * once you copy it into www/tenant-portal/). Replace every showNotice()
 * stub call in the mockup's existing script with a call into this module.
 *
 * Adjust API_BASE if the site isn't served at the same origin as the page.
 */

const API_BASE = ""; // same-origin — e.g. "" for mysite-v16.localhost:8002

function getToken() {
  return localStorage.getItem("tenant_portal_token");
}
function setToken(token) {
  localStorage.setItem("tenant_portal_token", token);
}
function clearToken() {
  localStorage.removeItem("tenant_portal_token");
}

async function callApi(method, params = {}) {
  const token = getToken();
  if (method !== "tenant_portal_login" && !token) {
    window.location.href = "/tenant-portal/login"; // adjust to your actual login route
    return null;
  }

  const body = { ...params };
  if (token) body.token = token;

  const res = await fetch(`${API_BASE}/api/method/re_core.re_core.tenant_portal_api.${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      clearToken();
      window.location.href = "/tenant-portal/login";
      return null;
    }
    const message = data?.exception || data?.message || "Something went wrong";
    throw new Error(message);
  }

  return data.message;
}

// ---- Auth ----
async function tenantLogin(mobile, accessCode) {
  const result = await callApi("tenant_portal_login", { mobile, access_code: accessCode });
  if (result?.token) setToken(result.token);
  return result;
}
async function tenantLogout() {
  await callApi("tenant_portal_logout");
  clearToken();
}

// ---- Dashboard ----
const getDashboard = () => callApi("tenant_portal_dashboard");

// ---- My Lease ----
const getLease = () => callApi("tenant_portal_lease");

// ---- Payments ----
const getInstallments = () => callApi("tenant_portal_installments");
const payInstallment = (installmentName, amount, modeOfPayment = "Cash", remarks) =>
  callApi("tenant_portal_pay_installment", {
    installment_name: installmentName,
    amount,
    mode_of_payment: modeOfPayment,
    remarks,
  });

// ---- Cheque Schedule ----
const getPdcs = () => callApi("tenant_portal_pdcs");

// ---- Maintenance ----
const getMaintenanceRequests = () => callApi("tenant_portal_maintenance_list");
const getTenantUnits = () => callApi("tenant_portal_units");
const createMaintenanceRequest = (category, description, priority = "Medium", unit, photo1, photo2) =>
  callApi("tenant_portal_create_maintenance_request", {
    category,
    description,
    priority,
    unit,
    photo_1: photo1,
    photo_2: photo2,
  });

// ---- Documents ----
const getDocuments = () => callApi("tenant_portal_documents");

// Expose on window so the existing mockup script (non-module) can call these directly
window.tenantPortal = {
  tenantLogin,
  tenantLogout,
  getDashboard,
  getLease,
  getInstallments,
  payInstallment,
  getPdcs,
  getMaintenanceRequests,
  getTenantUnits,
  createMaintenanceRequest,
  getDocuments,
  getToken,
};
