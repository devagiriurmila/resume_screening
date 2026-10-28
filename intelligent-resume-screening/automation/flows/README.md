# Flowcharts (Mermaid source)

Each `.mmd` file is plain text. Preview in VS Code with the **Markdown Preview Mermaid Support** or
**Mermaid Chart** extension, or paste the contents into https://mermaid.live (copy only - nothing is uploaded by this project).

| File | What it shows |
|------|---------------|
| `system_flow.mmd` | Overall architecture: browser, UiPath robot, Flask API, engine, SQLite, reports, demo page + Selenium. |
| `resume_processing.mmd` | Upload validation -> extraction -> parsing -> scoring -> storage. Every rejection point is shown. |
| `ocr_extraction.mmd` | Per-page decision: embedded text versus OCR, confidence handling, and failure cases. |
| `skill_scoring.mmd` | Weight validation/normalisation, whole-word matching, alias and context rules, score formula. |
| `rpa_workflow.mmd` | The UiPath robot's steps: config -> run Python -> retry -> verify report -> log counts. |
| `error_handling.mmd` | How each category of error is handled and whether it is retried. |

Key ideas: one bad file never stops a batch; temporary failures (network, HTTP 5xx) are retried, permanent ones
(HTTP 4xx, invalid PDF) are not; thresholds only flag - they never reject.
