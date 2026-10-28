r"""Read a job posting from the LOCAL demo page with Selenium and (optionally) save it through the API.

Only use this on pages you own or have permission to read. It does no login, CAPTCHA or anti-bot work.

Examples (PowerShell):
  python scraper\scrape_job.py                         # dry run: print what was found
  python scraper\scrape_job.py --save                  # also POST it to http://127.0.0.1:5000/api/jobs
  python scraper\scrape_job.py --url http://127.0.0.1:5000/demo-job --save
  python scraper\scrape_job.py --engine html           # no browser needed (stdlib HTML parser fallback)

Stable selectors (data-testid attributes): see automation/selectors.md
"""
import argparse
import json
import logging
import sys
from html.parser import HTMLParser
from pathlib import Path

log = logging.getLogger("scrape_job")
DEFAULT_PAGE = Path(__file__).resolve().parent / "demo_job_page.html"

SEL = {
    "title": '[data-testid="job-title"]',
    "description": '[data-testid="job-description"]',
    "min_exp": '[data-testid="min-experience"]',
    "education": '[data-testid="education"]',
    "skills": 'li[data-testid="skill-item"]',
}


def build_payload(title, description, min_exp, education, skills):
    return {"title": title.strip(), "description": description.strip(), "min_experience_years": float(min_exp or 0),
            "education_requirement": education.strip(), "skills": skills, "source": "scraped-demo"}


# ---------------------------------------------------------------- Selenium engine
def scrape_with_selenium(url, headless=True, timeout=15):
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    driver = None
    try:
        driver = webdriver.Chrome(options=options)  # Selenium Manager finds/downloads the driver
        driver.get(url)
        wait = WebDriverWait(driver, timeout)
        title = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, SEL["title"]))).text
        description = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL["description"]))).text
        min_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL["min_exp"])))
        education = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SEL["education"]))).text
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEL["skills"])))
        skills = [{"skill": el.get_attribute("data-skill"), "weight": float(el.get_attribute("data-weight"))}
                  for el in driver.find_elements(By.CSS_SELECTOR, SEL["skills"])]
        log.info("Selenium found %d skills", len(skills))
        return build_payload(title, description, min_el.get_attribute("data-value"), education, skills)
    except TimeoutException as exc:
        raise RuntimeError(f"Expected element not found within {timeout}s - has the page structure changed? ({SEL})") from exc
    except WebDriverException as exc:
        raise RuntimeError(f"Browser could not be started or driven: {exc.msg}") from exc
    finally:
        if driver:
            driver.quit()


# ---------------------------------------------------------------- stdlib fallback engine
class _DemoPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data, self.skills, self._cur, self._buf = {}, [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        tid = a.get("data-testid")
        if tid in ("job-title", "job-description", "min-experience", "education"):
            self._cur, self._buf = tid, []
            if tid == "min-experience":
                self.data["min_exp"] = a.get("data-value", "0")
        elif tid == "skill-item":
            self.skills.append({"skill": a.get("data-skill"), "weight": float(a.get("data-weight", 0))})

    def handle_data(self, text):
        if self._cur:
            self._buf.append(text)

    def handle_endtag(self, tag):
        if self._cur:
            self.data[self._cur] = " ".join(" ".join(self._buf).split())
            self._cur = None


def scrape_with_parser(path):
    parser = _DemoPageParser()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    d = parser.data
    missing = [k for k in ("job-title", "job-description", "education") if k not in d] + ([] if parser.skills else ["skills"])
    if missing:
        raise RuntimeError(f"Missing expected elements: {missing}")
    return build_payload(d["job-title"], d["job-description"], d.get("min_exp", 0), d["education"], parser.skills)


def post_job(base_url, payload):
    import requests
    resp = requests.post(base_url.rstrip("/") + "/api/jobs", json=payload, timeout=15)
    if resp.status_code != 201:
        raise RuntimeError(f"API returned {resp.status_code}: {resp.text[:300]}")
    return resp.json()["job"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=DEFAULT_PAGE.as_uri(), help="page to read (default: local demo page file)")
    ap.add_argument("--engine", choices=["selenium", "html"], default="selenium")
    ap.add_argument("--base-url", default="http://127.0.0.1:5000")
    ap.add_argument("--save", action="store_true", help="POST the extracted job to the API")
    ap.add_argument("--show-browser", action="store_true")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.engine == "selenium":
            payload = scrape_with_selenium(args.url, headless=not args.show_browser, timeout=args.timeout)
        else:
            payload = scrape_with_parser(DEFAULT_PAGE)
        print(json.dumps(payload, indent=2))
        if args.save:
            job = post_job(args.base_url, payload)
            log.info("Saved as job #%s (weights normalised to total %s%%)", job["id"], job["weights_total"])
        else:
            log.info("Dry run - add --save to store this job.")
        return 0
    except Exception as exc:  # noqa: BLE001 - report any failure with a clean exit code
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
