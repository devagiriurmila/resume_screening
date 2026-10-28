(function () {
  const job = JSON.parse(document.getElementById("job-data").textContent);
  const box = document.getElementById("skills");

  function addRow(skill, weight) {
    const row = document.createElement("div");
    row.className = "row g-2 mb-2 skill-row";
    row.innerHTML =
      '<div class="col-7 col-md-8"><input class="form-control s-name" placeholder="Skill (e.g. Python)" maxlength="60" aria-label="Skill name"></div>' +
      '<div class="col-3 col-md-3"><input class="form-control s-weight" type="number" min="0.01" step="0.01" placeholder="Weight" aria-label="Weight"></div>' +
      '<div class="col-2 col-md-1"><button type="button" class="btn btn-outline-danger w-100 s-del" aria-label="Remove skill">&times;</button></div>';
    row.querySelector(".s-name").value = skill || "";
    row.querySelector(".s-weight").value = weight === undefined || weight === null ? "" : weight;
    row.querySelector(".s-del").addEventListener("click", () => { row.remove(); updateTotal(); });
    row.querySelector(".s-weight").addEventListener("input", updateTotal);
    box.appendChild(row);
    updateTotal();
  }

  function collect() {
    return Array.from(box.querySelectorAll(".skill-row")).map(r => ({
      skill: r.querySelector(".s-name").value.trim(),
      weight: r.querySelector(".s-weight").value
    })).filter(s => s.skill || s.weight !== "");
  }

  function updateTotal() {
    const total = collect().reduce((a, s) => a + (parseFloat(s.weight) || 0), 0);
    const el = document.getElementById("total");
    el.textContent = Math.round(total * 100) / 100;
    el.className = Math.abs(total - 100) < 0.005 ? "text-success" : "text-warning";
  }

  document.getElementById("normalize").addEventListener("click", () => {
    const rows = Array.from(box.querySelectorAll(".skill-row"));
    const total = rows.reduce((a, r) => a + (parseFloat(r.querySelector(".s-weight").value) || 0), 0);
    if (!total) return showAlert("Enter positive weights first.", "warning");
    let sum = 0, biggest = null, biggestVal = -1;
    rows.forEach(r => {
      const inp = r.querySelector(".s-weight");
      const v = Math.round((parseFloat(inp.value) || 0) * 10000 / total) / 100;
      inp.value = v; sum += v;
      if (v > biggestVal) { biggestVal = v; biggest = inp; }
    });
    if (biggest) biggest.value = Math.round((parseFloat(biggest.value) + (100 - sum)) * 100) / 100;
    updateTotal();
  });
  document.getElementById("add-skill").addEventListener("click", () => addRow("", ""));

  if (job) {
    document.getElementById("title").value = job.title;
    document.getElementById("description").value = job.description || "";
    document.getElementById("min_exp").value = job.min_experience_years;
    document.getElementById("education").value = job.education_requirement || "";
    if (job.education_requirement && document.getElementById("education").value !== job.education_requirement) {
      const opt = new Option(job.education_requirement, job.education_requirement, true, true);
      document.getElementById("education").add(opt);
    }
    job.skills.forEach(s => addRow(s.skill, s.weight));
  } else {
    addRow("Python", 40); addRow("SQL", 25); addRow("Excel", 20); addRow("Communication", 15);
  }

  document.getElementById("save").addEventListener("click", async () => {
    const payload = {
      title: document.getElementById("title").value,
      description: document.getElementById("description").value,
      min_experience_years: document.getElementById("min_exp").value || 0,
      education_requirement: document.getElementById("education").value,
      skills: collect()
    };
    try {
      await api(job ? "/api/jobs/" + job.id : "/api/jobs", {
        method: job ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      location.href = "/jobs";
    } catch (e) {
      const d = e.data && e.data.details ? Object.values(e.data.details).join(" ") : e.message;
      showAlert(d);
    }
  });
})();
