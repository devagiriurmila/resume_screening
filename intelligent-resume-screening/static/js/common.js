/* Shared helpers. All dynamic text is escaped before it is placed in HTML. */
function esc(value) {
  return String(value === null || value === undefined ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

async function api(url, options) {
  const res = await fetch(url, options);
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON response */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || res.statusText || "Request failed");
    err.data = data; err.status = res.status;
    throw err;
  }
  return data;
}

function showAlert(message, type) {
  const box = document.getElementById("alerts");
  if (!box) return;
  box.innerHTML = '<div class="alert alert-' + (type || "danger") + ' alert-dismissible fade show" role="alert">' +
    esc(message) + '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>';
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function notDetected(value) {
  return (value === null || value === undefined || value === "") ? '<span class="nd">Not detected</span>' : esc(value);
}
