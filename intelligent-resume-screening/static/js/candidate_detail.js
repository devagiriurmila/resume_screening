(function () {
  const sel = document.getElementById("review-status");
  if (!sel) return;
  const id = sel.dataset.id;
  document.getElementById("save-review").addEventListener("click", async () => {
    try {
      await api("/api/candidates/" + id + "/review", { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review_status: sel.value, note: document.getElementById("review-note").value }) });
      showAlert("Review saved.", "success");
    } catch (e) { showAlert(e.message); }
  });
  document.getElementById("delete-candidate").addEventListener("click", async () => {
    if (!confirm("Permanently delete this candidate's extracted data?")) return;
    try { await api("/api/candidates/" + id, { method: "DELETE" }); location.href = "/candidates"; }
    catch (e) { showAlert(e.message); }
  });
})();
