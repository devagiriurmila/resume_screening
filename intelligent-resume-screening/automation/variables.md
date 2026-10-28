# Variables, arguments and configuration

## Config.json (Data\Config.json) - see `uipath/Config.json`
| Key | Example | Meaning |
|-----|---------|---------|
| `PythonExe` | `C:\\Users\\me\\intelligent-resume-screening\\venv\\Scripts\\python.exe` | Interpreter of the project's venv |
| `ProjectRoot` | `C:\\Users\\me\\intelligent-resume-screening` | Working directory for Start Process |
| `ScriptPath` | `C:\\Users\\me\\intelligent-resume-screening\\scripts\\process_resumes.py` | Batch entry point |
| `InputFolder` | `C:\\RPA\\ResumeScreening\\Input` | PDFs to process |
| `OutputFolder` | `C:\\RPA\\ResumeScreening\\Output` | Excel report, log, summary |
| `BaseUrl` | `http://127.0.0.1:5000` | Flask address |
| `JobId` | `1` | Job description to screen against |
| `MaxRetries` | `3` | Retry count |

## Main.xaml variables
| Name | Type | Scope | Default | Notes |
|------|------|-------|---------|-------|
| `configJson` | `String` | Main | - | Raw file text |
| `config` | `Newtonsoft.Json.Linq.JObject` | Main | - | Parsed config |
| `pythonExe`, `projectRoot`, `scriptPath`, `inputFolder`, `outputFolder`, `baseUrl` | `String` | Main | from config | |
| `jobId` | `Int32` | Main | from config | |
| `maxRetries` | `Int32` | Main | 3 | |
| `pdfCount` | `Int32` | Main | 0 | Out of CheckPrerequisites |
| `summaryJson` | `String` | Main | "" | Last stdout line |
| `exitCode` | `Int32` | Main | 0 | 0 ok / 1 partial / 2 fatal |
| `reportPath` | `String` | Main | "" | Excel path |
| `total`, `successful`, `failed` | `Int32` | Main | 0 | Counts for the final log |

## Workflow arguments
| Workflow | Name | Direction | Type |
|----------|------|-----------|------|
| CheckPrerequisites | `in_InputFolder`, `in_OutputFolder`, `in_PythonExe`, `in_ScriptPath` | In | `String` |
| CheckPrerequisites | `out_PdfCount` | Out | `Int32` |
| RunResumeEngine | `in_PythonExe`, `in_ProjectRoot`, `in_ScriptPath`, `in_InputFolder`, `in_OutputFolder`, `in_BaseUrl` | In | `String` |
| RunResumeEngine | `in_JobId`, `in_MaxRetries` | In | `Int32` |
| RunResumeEngine | `out_SummaryJson` | Out | `String` |
| RunResumeEngine | `out_ExitCode` | Out | `Int32` |
| VerifyReport | `in_SummaryJson` | In | `String` |
| VerifyReport | `out_ReportPath` | Out | `String` |
| VerifyReport | `out_Total`, `out_Successful`, `out_Failed` | Out | `Int32` |

## Local variables inside workflows
| Name | Type | Used for |
|------|------|----------|
| `stdOut`, `stdErr` | `String` | Start Process outputs |
| `pdfFiles` | `String[]` | `Directory.GetFiles(in_InputFolder, "*.pdf")` |
| `inputExists` | `Boolean` | Path Exists result |
| `summary` | `Newtonsoft.Json.Linq.JObject` | Parsed JSON summary |
| `dt` | `System.Data.DataTable` | Excel Read Range output |
| `statusCode` | `Int32` | HTTP Request health check |
| `sessionId` | `Int32` | Screening session reused across per-file uploads (API route) |

## JSON summary printed by `process_resumes.py` (last stdout line)
```json
{"total": 8, "successful": 7, "failed": 1, "session_id": 1,
 "report": "C:\\RPA\\Output\\screening_report_session1_20261027_101500.xlsx",
 "failures": [{"file": "invalid_not_a_pdf.pdf", "reason": "File content is not a real PDF ..."}],
 "exit_code": 1}
```
