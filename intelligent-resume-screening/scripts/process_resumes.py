r"""Batch-process a folder of PDF resumes through the running web application's API.

This is the script UiPath calls with 'Invoke Python Script' / 'Start Process'. It can also be run by hand.

Exit codes: 0 = every file processed, 1 = some files failed/rejected, 2 = fatal error (server unreachable, no job...).
The LAST line printed to stdout is a one-line JSON summary that UiPath can parse.

Examples (PowerShell):
  python scripts\process_resumes.py --input-folder sample_data\resumes --output-folder outputs --job-id 1
  python scripts\process_resumes.py --input-folder C:\RPA\in --output-folder C:\RPA\out --job-title "Junior Data Analyst" --start-server
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("process_resumes")


def retry(func, attempts, delay, what):
    """Retry on connection errors and 5xx responses (temporary failures). 4xx errors are not retried."""
    last = None
    for i in range(1, attempts + 1):
        try:
            resp = func()
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            return resp
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last = exc
            log.warning("%s failed (attempt %d/%d): %s", what, i, attempts, exc)
            if i < attempts:
                time.sleep(delay * i)
    raise RuntimeError(f"{what} failed after {attempts} attempts: {last}")


def ensure_server(base_url, start_server, attempts, delay):
    def check():
        return requests.get(base_url + "/api/health", timeout=5)
    try:
        r = check()
        if r.ok:
            return r.json()
    except requests.RequestException:
        pass
    if not start_server:
        raise RuntimeError(f"Server not reachable at {base_url}. Start it (scripts\\run_app.bat) or pass --start-server.")
    log.info("Starting Flask application...")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=str(ROOT), creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(1)
        try:
            r = check()
            if r.ok:
                return r.json()
        except requests.RequestException:
            continue
    raise RuntimeError("Flask application did not become ready within 30 seconds.")


def pick_job(base_url, job_id, job_title, attempts, delay):
    jobs = retry(lambda: requests.get(base_url + "/api/jobs", timeout=15), attempts, delay, "Load jobs").json()["jobs"]
    if job_id:
        found = [j for j in jobs if j["id"] == job_id]
    elif job_title:
        found = [j for j in jobs if j["title"].lower() == job_title.lower()]
    else:
        found = jobs[:1]
    if not found:
        raise RuntimeError("No matching job description found. Create one in the web app first.")
    return found[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-folder", required=True)
    ap.add_argument("--output-folder", required=True)
    ap.add_argument("--job-id", type=int)
    ap.add_argument("--job-title")
    ap.add_argument("--base-url", default="http://127.0.0.1:5000")
    ap.add_argument("--start-server", action="store_true")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--retry-delay", type=float, default=2.0)
    ap.add_argument("--move-files", action="store_true", help="move inputs into processed/ or failed/ subfolders")
    args = ap.parse_args(argv)

    out_dir = Path(args.output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(out_dir / "process_resumes.log", encoding="utf-8")])
    base = args.base_url.rstrip("/")
    summary = {"total": 0, "successful": 0, "failed": 0, "session_id": None, "report": None, "failures": []}
    try:
        in_dir = Path(args.input_folder)
        if not in_dir.is_dir():
            raise RuntimeError(f"Input folder not found: {in_dir}")
        health = ensure_server(base, args.start_server, args.retries, args.retry_delay)
        log.info("Server OK (OCR available: %s)", health.get("ocr_available"))
        job = pick_job(base, args.job_id, args.job_title, args.retries, args.retry_delay)
        log.info("Using job #%s '%s'", job["id"], job["title"])

        files = sorted(p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
        # Non-PDF files are reported, not silently ignored
        for p in sorted(p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() != ".pdf"):
            log.warning("Skipping unsupported file: %s", p.name)
        summary["total"] = len(files)
        if not files:
            raise RuntimeError("No PDF files found in the input folder.")

        for path in files:
            def send():
                with open(path, "rb") as fh:
                    data = {"job_id": job["id"]}
                    if summary["session_id"]:
                        data["session_id"] = summary["session_id"]
                    return requests.post(base + "/api/resumes/upload", data=data,
                                         files={"files": (path.name, fh, "application/pdf")}, timeout=180)
            ok, reason = False, ""
            try:
                resp = retry(send, args.retries, args.retry_delay, f"Upload {path.name}")
                body = resp.json()
                summary["session_id"] = body.get("session_id", summary["session_id"])
                result = (body.get("results") or [{}])[0]
                ok = result.get("status") in ("processed", "processed_with_warnings")
                reason = result.get("error") or body.get("error") or ""
            except Exception as exc:  # noqa: BLE001
                reason = str(exc)
            if ok:
                summary["successful"] += 1
                log.info("OK     %s", path.name)
            else:
                summary["failed"] += 1
                summary["failures"].append({"file": path.name, "reason": reason})
                log.error("FAILED %s: %s", path.name, reason)
            if args.move_files:
                dest = in_dir / ("processed" if ok else "failed")
                dest.mkdir(exist_ok=True)
                path.replace(dest / path.name)

        if summary["session_id"] and summary["successful"]:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report = out_dir / f"screening_report_session{summary['session_id']}_{stamp}.xlsx"
            resp = retry(lambda: requests.get(base + "/api/reports/excel", params={"session_id": summary["session_id"]},
                                              timeout=120), args.retries, args.retry_delay, "Download Excel report")
            if resp.status_code != 200:
                raise RuntimeError(f"Excel report request returned {resp.status_code}: {resp.text[:200]}")
            report.write_bytes(resp.content)
            summary["report"] = str(report)
            log.info("Excel report saved: %s", report)
        log.info("Finished. total=%d successful=%d failed=%d", summary["total"], summary["successful"], summary["failed"])
        code = 0 if summary["failed"] == 0 else 1
    except Exception as exc:  # noqa: BLE001
        log.error("FATAL: %s", exc)
        summary["fatal_error"] = str(exc)
        code = 2
    summary["exit_code"] = code
    (out_dir / "last_run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return code


def run_batch(input_folder, output_folder, job_id=0, job_title="", base_url="http://127.0.0.1:5000",
              start_server=False):
    """Function entry point for UiPath's 'Invoke Python Method'. Returns the JSON summary as a string."""
    argv = ["--input-folder", str(input_folder), "--output-folder", str(output_folder), "--base-url", str(base_url)]
    if job_id:
        argv += ["--job-id", str(int(job_id))]
    if job_title:
        argv += ["--job-title", str(job_title)]
    if start_server:
        argv.append("--start-server")
    main(argv)
    return (Path(output_folder) / "last_run_summary.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
