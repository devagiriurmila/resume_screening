document.querySelectorAll(".js-delete-job").forEach(btn => {
  btn.addEventListener("click", async () => {
    if (!confirm('Delete job "' + btn.dataset.title + '"? Past screening sessions keep their job snapshot.')) return;
    try { await api("/api/jobs/" + btn.dataset.id, { method: "DELETE" }); location.reload(); }
    catch (e) { showAlert(e.message); }
  });
});
