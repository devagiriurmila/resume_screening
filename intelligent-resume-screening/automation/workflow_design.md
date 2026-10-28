# UiPath workflow design - "ResumeScreeningBot"

Tested design target: **UiPath Studio 2023.10 or newer, Windows (not Legacy) project, C# or VB.NET expressions**.
Property names below are those used by the standard activity packages; if your Studio version labels something slightly
differently, use the Properties panel search box.

## 0. Prerequisites
1. Finish the README setup so `scripts\run_app.bat` works and the site opens at http://127.0.0.1:5000.
2. Create at least one job in the web UI (or run `python database\seed.py`) and note its **Job ID** (Jobs page -> the order shown, or `GET /api/jobs`).
3. Find the Python executable used by the project's virtual environment, e.g.
   `C:\Users\<you>\intelligent-resume-screening\venv\Scripts\python.exe`. Using the venv's python means all packages are available.
4. Put some PDFs in an input folder, e.g. `C:\RPA\ResumeScreening\Input` (use `sample_data\resumes`).

### UiPath packages (Manage Packages -> Official)
| Package | Needed for |
|---------|-----------|
| `UiPath.System.Activities` | Start Process, Assign, Try Catch, Retry Scope, Log Message, Path Exists, Directory/File activities (already included) |
| `UiPath.Excel.Activities` | Optional: open the report and count rows |
| `UiPath.WebAPI.Activities` | Only for the alternative "HTTP Request" route (section 6) |
| `UiPath.UIAutomation.Activities` | Only for the optional browser demo (section 7) |
| `UiPath.Python.Activities` | Only for the alternative "Invoke Python Method" route (section 5b) |

## 1. Project layout
```
ResumeScreeningBot/
  Main.xaml                  (State Machine or Sequence - Sequence is enough)
  Framework/ (optional)
  Workflows/
    CheckPrerequisites.xaml
    RunResumeEngine.xaml
    VerifyReport.xaml
  Data/Config.json  (see automation/uipath/Config.json)
```
Keep Main simple: it invokes the three workflows in order inside one Try Catch.

## 2. Main.xaml - activity by activity
Arguments/variables are defined in `variables.md`.

1. **Read Text File** `Data\Config.json` -> `configJson` (String). Then **Deserialize JSON** (`UiPath.WebAPI.Activities` or use the
   `JObject.Parse(configJson)` via **Assign**) -> `config` (`Newtonsoft.Json.Linq.JObject`). Assign each setting:
   `inputFolder = config("InputFolder").ToString`, etc.
2. **Log Message** (Level `Info`): `"Run started. Input = " + inputFolder`.
3. **Try Catch** (the whole run):
   - **Try**
     1. **Invoke Workflow File** `Workflows\CheckPrerequisites.xaml`
        (In: `inputFolder`, `outputFolder`, `pythonExe`, `scriptPath`; Out: `pdfCount` Int32).
     2. **If** `pdfCount = 0` -> **Log Message** `Warning` "No PDFs found" -> **Terminate Workflow** (Reason "Nothing to process", not an error).
     3. **Invoke Workflow File** `Workflows\RunResumeEngine.xaml`
        (In: all config values; Out: `summaryJson` String, `exitCode` Int32).
     4. **Invoke Workflow File** `Workflows\VerifyReport.xaml` (In: `summaryJson`; Out: `reportPath` String, `total`, `successful`, `failed` Int32).
     5. **Log Message** `Info`: `"Done. Total=" + total + " Successful=" + successful + " Failed=" + failed + " Report=" + reportPath`.
   - **Catches**
     - `BusinessRuleException`: **Log Message** `Warning` with `exception.Message`; **Terminate Workflow** with status Faulted.
     - `System.Exception`: **Log Message** `Error` with `exception.ToString`; optionally **Send SMTP Mail Message** to yourself; **Rethrow**.
   - **Finally**: **Log Message** `Info` "Run finished".

## 3. CheckPrerequisites.xaml
1. **Path Exists** (PathType `Folder`, Path `inputFolder`) -> `inputExists` Boolean.
   **If** `Not inputExists` -> **Throw** `New BusinessRuleException("Input folder not found: " + inputFolder)`.
2. **Create Directory** `outputFolder` (safe if it already exists).
3. **Path Exists** (PathType `File`, Path `pythonExe`) and again for `scriptPath`; Throw `BusinessRuleException` if either is missing.
4. **Assign** `pdfFiles = Directory.GetFiles(inputFolder, "*.pdf")` (`String[]`) and `pdfCount = pdfFiles.Length` (Out argument).

## 4. Verify the Flask app is running (inside RunResumeEngine, before the script)
The script itself can start Flask (`--start-server`) so this is optional, but showing the check is useful for the assignment:
1. **Retry Scope** (NumberOfRetries `3`, RetryInterval `00:00:05`, Condition = a **Check True** activity)
   - Action: **HTTP Request** (UiPath.WebAPI.Activities) `GET http://127.0.0.1:5000/api/health`, Accept `application/json`; output `StatusCode` Int32.
   - Condition: **Check True** `statusCode = 200`.
   - If all retries fail, a following **If** invokes **Start Process** with `pythonExe` and `scriptPath.Replace("scripts\process_resumes.py","app.py")` (WorkingDirectory = project root) and then **Delay** 00:00:05.

## 5. RunResumeEngine.xaml - call the Python engine
### 5a. Recommended: Start Process
Inside **Retry Scope** (NumberOfRetries `2`, RetryInterval `00:00:10`; Condition: **Check True** `exitCode <> 2`):

**Start Process** (UiPath.System.Activities) properties:

| Property | Value |
|----------|-------|
| FileName | `pythonExe` |
| Arguments | VB.NET expression: `String.Format("""{0}"" --input-folder ""{1}"" --output-folder ""{2}"" --job-id {3} --base-url {4} --start-server --move-files", scriptPath, inputFolder, outputFolder, jobId, baseUrl)` (every path is quoted because folders may contain spaces; `--move-files` moves inputs into `processed\` / `failed\` subfolders so re-runs do not repeat work) |
| WorkingDirectory | `projectRoot` |
| Output -> Standard output | `stdOut` (String) |
| Output -> Standard error | `stdErr` (String) |
| Output -> Exit code | `exitCode` (Int32) |
| Timeout / wait for exit | enabled (wait for completion) |

After the activity:
1. **Assign** `summaryJson = stdOut.Trim.Split(Environment.NewLine.ToCharArray(), StringSplitOptions.RemoveEmptyEntries).Last` (the final line is the JSON summary).
2. **If** `exitCode = 2` -> **Throw** `New System.Exception("Python engine fatal error: " + stdErr + stdOut)` - the surrounding Retry Scope retries it (server not ready, temporary network problem).
3. **If** `exitCode = 1` -> **Log Message** `Warning` "Some files failed - see summary" (do NOT throw; partial success is normal).

Why Start Process? It needs no extra package, uses the venv's python directly, and gives you stdout and exit codes.

### 5b. Alternative: Python Scope (UiPath.Python.Activities)
1. **Python Scope**: Path = folder of `python.exe` (`...\venv\Scripts`), Library path = `projectRoot`, Version = your Python version (3.10-3.12), Target `x64`.
2. **Load Python Script** `scriptPath` -> `pyObj` (PythonObject).
3. **Invoke Python Method**: Instance `pyObj`, Name `run_batch`, InputParameters = `{inputFolder, outputFolder, jobId, "", baseUrl, True}`, Output `pyResult` (PythonObject).
4. **Get Python Object** (TypeArgument `String`) -> `summaryJson`.
Use this only if your UiPath/Python versions are known to be compatible; the Start Process route is more reliable.

## 6. Alternative: talk to the REST API directly (UiPath.WebAPI.Activities)
Use **HTTP Request** activities. Common settings: Accept `application/json`, Timeout 120000 ms, "Continue on error" off.

| Step | Method + URL | Body / notes |
|------|--------------|--------------|
| Health | `GET {baseUrl}/api/health` | expect 200 |
| Jobs | `GET {baseUrl}/api/jobs` | pick `jobs[i].id` by title (Deserialize JSON, LINQ) |
| Upload one PDF | `POST {baseUrl}/api/resumes/upload` | Body format `multipart/form-data`: parts `job_id` (text), optional `session_id` (text; reuse the value returned by the first upload), `files` (file part, MIME `application/pdf`) |
| Excel report | `GET {baseUrl}/api/reports/excel?session_id={sessionId}` | enable "Save response as file" = `outputFolder\report_{sessionId}.xlsx` |

Wrap each call in **Retry Scope** (3 tries, 5 s). Retry only for connection errors / 5xx; treat 4xx as a permanent failure for that file.
Put the per-file call in **For Each** (`pdfFiles`) with its own **Try Catch** so one bad file never stops the loop; increment `successful` or `failed` counters.

## 7. Optional: browser automation of the local demo page
Open `scraper\demo_job_page.html` (or `http://127.0.0.1:5000/demo-job`) with **Use Application/Browser** and read elements using the
selectors in `selectors.md` (**Get Text** for title/description; **For Each UI Element** for `li[data-testid="skill-item"]`; **Get Attribute**
`data-skill` / `data-weight`). Build a JSON body and POST it to `/api/jobs` with **HTTP Request**.
The Python alternative is `python scraper\scrape_job.py --save` (Selenium).
Only automate pages you own or have permission to automate.

## 8. VerifyReport.xaml
1. **Deserialize JSON** `summaryJson` -> `summary` (`JObject`). Assign `total = CInt(summary("total"))`, `successful`, `failed`, `reportPath = summary("report").ToString`.
2. **If** `successful > 0` and (`String.IsNullOrEmpty(reportPath)` or Not **Path Exists** `reportPath`) -> **Throw** `New System.Exception("Excel report missing")`.
3. Optional: **Excel Application Scope / Use Excel File** on `reportPath` -> **Read Range** sheet `Candidates` -> `dt` DataTable -> log `dt.Rows.Count` and the top candidate (`dt.Rows(0)("Candidate")`).
4. If `failed > 0` log each item of `summary("failures")` as `Warning` (file + reason). These need a person's attention.

## 9. Exception handling and logging summary
| Situation | Behaviour |
|-----------|-----------|
| Input folder missing / no PDFs | `BusinessRuleException` or graceful end - no retry |
| Flask not running | Python script starts it (`--start-server`) or Retry Scope waits |
| Temporary network/5xx | Python script retries 3x with growing delay; UiPath Retry Scope retries the whole call twice |
| Invalid/corrupt PDF | Reported in `failures`, run continues, exit code 1 |
| Fatal (exit code 2) | `System.Exception`, retried, then logged and rethrown |
| Always | `Log Message` at start, per failure, and final counts (total / successful / failed) |

## 10. Testing and debugging
1. Run the web app alone first and confirm `python scripts\process_resumes.py --input-folder sample_data\resumes --output-folder outputs --job-id 1` works (expect `successful=7 failed=1` - the included invalid file is rejected on purpose).
2. In Studio use **Debug -> Step Into**, set breakpoints after **Start Process**, and inspect `stdOut`, `stdErr`, `exitCode`, `summaryJson` in the Locals panel.
3. Turn on **Highlight Elements** / **Slow Step** when debugging the browser part.
4. Read `outputs\process_resumes.log` and `outputs\last_run_summary.json` - they record exactly what the Python side did.
5. Common problems: path has spaces -> quote it; `python` not recognised -> use the full path to `venv\Scripts\python.exe`;
   port 5000 busy -> change `PORT` in `.env` and `baseUrl` in Config; antivirus blocks `python.exe` -> allow-list the project folder.
6. Expected sample result: report in the output folder, ~7 candidates, one failure for `invalid_not_a_pdf.pdf`.
