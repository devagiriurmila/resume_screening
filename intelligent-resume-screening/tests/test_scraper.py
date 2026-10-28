import json

from scraper.scrape_job import DEFAULT_PAGE, scrape_with_parser


def test_demo_page_parsed_with_stable_selectors():
    payload = scrape_with_parser(DEFAULT_PAGE)
    assert payload["title"].startswith("Data Analyst")
    assert payload["min_experience_years"] == 2
    assert payload["education_requirement"] == "Bachelor's degree"
    assert [s["skill"] for s in payload["skills"]] == ["Python", "SQL", "Excel", "Communication"]
    json.dumps(payload)


def test_scraped_payload_accepted_by_api(client):
    payload = scrape_with_parser(DEFAULT_PAGE)
    r = client.post("/api/jobs", json=payload)
    assert r.status_code == 201 and r.get_json()["job"]["weights_total"] == 100
