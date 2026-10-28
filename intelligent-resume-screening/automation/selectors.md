# Stable selectors for the local demo job page

The page (`scraper/demo_job_page.html`, also served at `/demo-job`) marks every important element with a
`data-testid` attribute. These do not change when text, colours or layout change, unlike indexes, XPath positions or CSS classes.

| Data | CSS selector (Selenium) | UiPath selector |
|------|-------------------------|-----------------|
| Job title | `[data-testid="job-title"]` | `<html app='chrome.exe' title='Demo Job Posting*' /><webctrl css-selector='[data-testid="job-title"]' />` |
| Description | `[data-testid="job-description"]` | `<webctrl css-selector='[data-testid="job-description"]' />` |
| Min. experience | `[data-testid="min-experience"]` (value in `data-value`) | `<webctrl css-selector='[data-testid="min-experience"]' />` |
| Education | `[data-testid="education"]` | `<webctrl css-selector='[data-testid="education"]' />` |
| Skill rows | `li[data-testid="skill-item"]` (`data-skill`, `data-weight`) | `<webctrl css-selector='li[data-testid="skill-item"]' />` (use **For Each UI Element**) |

Tips
* In UiPath use **Indicate on screen**, then edit the selector to the form above; remove `idx`, `aaname` with changing text, and wildcards you do not need.
* For the title bar use a wildcard: `title='Demo Job Posting*'`.
* Selenium side: `WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.CSS_SELECTOR, ...)))` - never `time.sleep`.
* If a selector times out the scraper prints which selectors it expected, so a changed page is easy to diagnose.

The web application's own UI is automatable too: every control has a stable `id` (`#job`, `#files`, `#start`, `#q`, `#session`, ...).
