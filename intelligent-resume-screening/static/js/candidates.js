(function () {
  const state = { page: 1, sort: "score", order: "desc" };
  const $ = id => document.getElementById(id);
  const preset = new URLSearchParams(location.search);
  if (preset.get("session_id")) $("session").value = preset.get("session_id");
  if (preset.get("q")) $("q").value = preset.get("q");

  const reviewLabel = { pending: "Pending", shortlisted: "Shortlisted", on_hold: "On hold", not_selected: "Not selected" };

  function chips(list, cls, max) {
    if (!list || !list.length) return '<span class="nd">None</span>';
    const shown = list.slice(0, max || 6).map(s => '<span class="badge ' + cls + '">' + esc(s) + "</span>").join("");
    return shown + (list.length > (max || 6) ? ' <small class="text-muted">+' + (list.length - (max || 6)) + "</small>" : "");
  }

  async function load() {
    const p = new URLSearchParams({ page: state.page, per_page: 10, sort: state.sort, order: state.order });
    [["q", "q"], ["session_id", "session"], ["min_score", "min_score"], ["review_status", "review"], ["needs_review", "flag"]]
      .forEach(([k, id]) => { if ($(id).value) p.set(k, $(id).value); });
    try {
      const d = await api("/api/candidates?" + p.toString());
      $("rows").innerHTML = d.candidates.length ? d.candidates.map(c =>
        "<tr><td><a href=\"/candidates/" + c.candidate_id + "\">" + (c.name ? esc(c.name) : '<span class="nd">Not detected</span>') +
        '</a><div class="small text-muted">' + esc(c.original_filename) + "</div></td>" +
        "<td class=\"small\">" + notDetected(c.email) + "<br>" + notDetected(c.phone) + "</td>" +
        "<td>" + chips(c.skills, "badge-skill", 5) + "</td>" +
        "<td>" + (c.experience_years === null ? '<span class="nd">Not detected</span>' : esc(c.experience_years) + " yrs") + "</td>" +
        '<td class="small">' + notDetected(c.education) + "</td>" +
        '<td style="min-width:110px"><strong>' + c.score.toFixed(1) + '%</strong><div class="score-bar"><div style="width:' + c.score + '%"></div></div></td>' +
        "<td>" + chips(c.matched_skills, "badge-skill", 5) + "</td><td>" + chips(c.missing_skills, "badge-missing", 5) + "</td>" +
        "<td><span class=\"badge " + (c.processing_status === "processed" ? "bg-success" : "bg-warning text-dark") + "\">" +
        esc(c.processing_status.replace(/_/g, " ")) + "</span>" +
        (c.needs_review ? '<br><span class="badge bg-info text-dark mt-1">Manual review</span>' : "") + "</td>" +
        "<td>" + esc(reviewLabel[c.review_status] || c.review_status) + "</td></tr>").join("")
        : '<tr><td colspan="10" class="text-center text-muted">No candidates match.</td></tr>';
      $("count").textContent = d.total + " candidate(s) - page " + d.page + " of " + d.pages;
      let html = "";
      for (let i = 1; i <= d.pages; i++)
        html += '<li class="page-item ' + (i === d.page ? "active" : "") + '"><a class="page-link" href="#" data-p="' + i + '">' + i + "</a></li>";
      $("pager").innerHTML = html;
    } catch (e) { showAlert("Could not load candidates: " + e.message); }
  }

  $("pager").addEventListener("click", e => {
    const a = e.target.closest("a[data-p]");
    if (!a) return;
    e.preventDefault(); state.page = parseInt(a.dataset.p, 10); load();
  });
  document.querySelectorAll("th.sortable").forEach(th => th.addEventListener("click", () => {
    state.order = (state.sort === th.dataset.sort && state.order === "desc") ? "asc" : "desc";
    state.sort = th.dataset.sort; state.page = 1; load();
  }));
  let timer;
  ["q", "session", "min_score", "review", "flag"].forEach(id => $(id).addEventListener("input", () => {
    clearTimeout(timer); timer = setTimeout(() => { state.page = 1; load(); }, 250);
  }));
  load();
})();
