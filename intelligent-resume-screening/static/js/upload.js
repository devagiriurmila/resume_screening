(function () {
  const MAX = 10 * 1024 * 1024;
  const drop = document.getElementById("drop"), input = document.getElementById("files");
  const queueEl = document.getElementById("queue"), startBtn = document.getElementById("start");
  const jobSel = document.getElementById("job");
  if (!drop) return;
  const wanted = new URLSearchParams(location.search).get("job_id");
  if (wanted) jobSel.value = wanted;

  let items = [];

  function addFiles(fileList) {
    Array.from(fileList).forEach(f => {
      const it = { file: f, state: "queued", error: null, pct: 0 };
      if (!/\.pdf$/i.test(f.name)) { it.state = "rejected"; it.error = "Only PDF files are supported."; }
      else if (f.size > MAX) { it.state = "rejected"; it.error = "Larger than 10 MB."; }
      else if (f.size === 0) { it.state = "rejected"; it.error = "File is empty."; }
      items.push(it);
    });
    render();
  }

  function badge(it) {
    const map = { queued: ["secondary", "Queued"], uploading: ["primary", "Uploading " + it.pct + "%"],
      processing: ["info", "Processing..."], processed: ["success", "Processed"],
      processed_with_warnings: ["warning", "Processed with warnings"], failed: ["danger", "Failed"],
      rejected: ["danger", "Rejected"] };
    const m = map[it.state] || ["secondary", it.state];
    return '<span class="badge bg-' + m[0] + '">' + esc(m[1]) + "</span>";
  }

  function render() {
    queueEl.innerHTML = items.map(it =>
      '<div class="border rounded p-2 mb-2"><div class="d-flex justify-content-between"><span>' + esc(it.file.name) +
      ' <small class="text-muted">(' + Math.round(it.file.size / 1024) + " KB)</small></span>" + badge(it) + "</div>" +
      (it.state === "uploading" ? '<div class="progress mt-1" style="height:6px"><div class="progress-bar" style="width:' + it.pct + '%"></div></div>' : "") +
      (it.error ? '<div class="small text-danger mt-1">' + esc(it.error) + "</div>" : "") +
      (it.score !== undefined && it.score !== null ? '<div class="small mt-1">Skill match: <strong>' + it.score + "%</strong> " +
        (it.candidateId ? '<a href="/candidates/' + it.candidateId + '">details</a>' : "") + "</div>" : "") + "</div>").join("");
    startBtn.disabled = !items.some(i => i.state === "queued");
  }

  function sendOne(it, jobId, sessionId) {
    return new Promise(resolve => {
      const xhr = new XMLHttpRequest();
      const fd = new FormData();
      fd.append("job_id", jobId);
      if (sessionId) fd.append("session_id", sessionId);
      fd.append("files", it.file);
      xhr.open("POST", "/api/resumes/upload");
      xhr.upload.onprogress = e => { if (e.lengthComputable) { it.state = "uploading"; it.pct = Math.round(e.loaded * 100 / e.total); render(); } };
      xhr.upload.onload = () => { it.state = "processing"; render(); };
      xhr.onload = () => {
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
        const r = data && data.results && data.results[0];
        if (r) {
          it.state = r.status; it.error = r.error; it.score = r.score; it.candidateId = r.candidate_id;
          if (r.warnings && r.warnings.length) it.error = r.warnings.join(" ");
        } else { it.state = "failed"; it.error = (data && data.error) || "Server error (" + xhr.status + ")"; }
        resolve(data ? data.session_id : sessionId);
      };
      xhr.onerror = () => { it.state = "failed"; it.error = "Network error - is the server running?"; resolve(sessionId); };
      xhr.send(fd);
    });
  }

  startBtn.addEventListener("click", async () => {
    startBtn.disabled = true;
    let sessionId = null;
    const jobId = jobSel.value;
    for (const it of items.filter(i => i.state === "queued")) {
      sessionId = await sendOne(it, jobId, sessionId) || sessionId;
      render();
    }
    if (sessionId) {
      const link = document.getElementById("view-results");
      link.href = "/candidates?session_id=" + sessionId; link.classList.remove("d-none");
    }
  });

  drop.addEventListener("click", () => input.click());
  drop.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") input.click(); });
  input.addEventListener("change", () => { addFiles(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("drag"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("drag"); }));
  drop.addEventListener("drop", e => addFiles(e.dataTransfer.files));
})();
