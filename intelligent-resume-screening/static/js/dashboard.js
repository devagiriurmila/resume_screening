(async function () {
  try {
    const d = await api("/api/dashboard");
    document.getElementById("s-total").textContent = d.total_processed;
    document.getElementById("s-high").textContent = d.high_match;
    document.getElementById("s-high-label").textContent = "Score \u2265 " + d.thresholds.high_match + "%";
    document.getElementById("s-review").textContent = d.manual_review;
    document.getElementById("s-avg").textContent = d.average_score + "%";

    const total = d.distribution.counts.reduce((a, b) => a + b, 0);
    if (total === 0) document.getElementById("chart-empty").hidden = false;
    new Chart(document.getElementById("scoreChart"), {
      type: "bar",
      data: { labels: d.distribution.labels,
              datasets: [{ label: "Candidates", data: d.distribution.counts, backgroundColor: "#0d6efd", borderRadius: 6 }] },
      options: { plugins: { legend: { display: false } },
                 scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });

    const list = document.getElementById("recent");
    if (!d.recent_activity.length) {
      list.innerHTML = '<li class="list-group-item text-muted">No screening activity yet.</li>';
    } else {
      list.innerHTML = d.recent_activity.map(s =>
        '<li class="list-group-item d-flex justify-content-between"><span><a href="/candidates?session_id=' + s.id + '">#' + s.id +
        " " + esc(s.job_title) + '</a><br><small class="text-muted">' + esc(s.created_at) + " &middot; " + s.files +
        ' file(s)</small></span><span class="text-primary fw-semibold">' +
        (s.avg_score === null ? "-" : s.avg_score + "%") + "</span></li>").join("");
    }
  } catch (e) { showAlert("Could not load dashboard: " + e.message); }
})();
