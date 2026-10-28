import pytest

from services.skill_matcher import get_dictionary, normalize_weights, score_resume, extract_skills

D = get_dictionary()


def test_weights_normalise_to_100():
    out = normalize_weights([{"skill": "A", "weight": 1}, {"skill": "B", "weight": 1}, {"skill": "C", "weight": 1}])
    assert sum(w["weight"] for w in out) == pytest.approx(100.0, abs=1e-9)


def test_weights_already_100_unchanged():
    out = normalize_weights([{"skill": "Python", "weight": 40}, {"skill": "SQL", "weight": 25},
                             {"skill": "Excel", "weight": 20}, {"skill": "Communication", "weight": 15}])
    assert [w["weight"] for w in out] == [40, 25, 20, 15]


def test_missing_weights_split_equally():
    out = normalize_weights([{"skill": "A"}, {"skill": "B"}, {"skill": "C"}, {"skill": "D"}])
    assert [w["weight"] for w in out] == [25, 25, 25, 25]


@pytest.mark.parametrize("bad", [
    [], [{"skill": "", "weight": 10}], [{"skill": "A", "weight": -5}], [{"skill": "A", "weight": 0}],
    [{"skill": "A", "weight": "abc"}], [{"skill": "A", "weight": 1}, {"skill": "a", "weight": 2}],
    [{"skill": "A", "weight": 1}, {"skill": "B"}], [{"skill": "A", "weight": float("nan")}],
])
def test_invalid_weights_rejected(bad):
    with pytest.raises(ValueError):
        normalize_weights(bad)


def test_score_is_sum_of_matched_weights():
    job = [{"skill": "Python", "weight": 40}, {"skill": "SQL", "weight": 25},
           {"skill": "Excel", "weight": 20}, {"skill": "Communication", "weight": 15}]
    r = score_resume("I use Python and Excel daily.", job)
    assert r["score"] == 60.0
    assert r["matched"] == ["Python", "Excel"] and r["missing"] == ["SQL", "Communication"]
    assert sum(b["points"] for b in r["breakdown"]) == r["score"]


def test_full_and_zero_score():
    job = [{"skill": "Python", "weight": 1}, {"skill": "SQL", "weight": 1}]
    assert score_resume("python sql", job)["score"] == 100.0
    assert score_resume("nothing relevant here", job)["score"] == 0.0


def test_no_substring_false_positives():
    # 'java' must not match 'javascript'; 'sql' must not match 'mysqlx'; 'r' style words must not match
    assert score_resume("Expert in JavaScript", [{"skill": "Java", "weight": 1}])["score"] == 0
    assert score_resume("We discussed pythonic style", [{"skill": "Python", "weight": 1}])["score"] == 0
    assert score_resume("excellent communicator", [{"skill": "Excel", "weight": 1}])["score"] == 0
    assert score_resume("Experienced with JavaScript", [{"skill": "Java", "weight": 1}])["score"] == 0


def test_cpp_and_csharp_handled():
    assert score_resume("Languages: C++, C#", [{"skill": "C++", "weight": 1}])["score"] == 100
    assert score_resume("Languages: C#", [{"skill": "C++", "weight": 1}])["score"] == 0


def test_aliases():
    assert score_resume("Managed PostgreSQL databases", [{"skill": "SQL", "weight": 1}])["score"] == 100
    assert score_resume("Wrote JS code", [{"skill": "JavaScript", "weight": 1}])["score"] == 100
    assert score_resume("Advanced Excel user", [{"skill": "Microsoft Excel", "weight": 1}])["score"] == 100
    assert score_resume("Used Excel", [{"skill": "Microsoft Excel", "weight": 1}])["score"] == 100


def test_py_requires_context():
    job = [{"skill": "Python", "weight": 1}]
    assert score_resume("Wrote py scripts with pandas", job)["score"] == 100
    assert score_resume("Studied py in the park", job)["score"] == 0


def test_node_js_is_not_javascript_via_js_alias():
    assert score_resume("Built APIs with Node.js", [{"skill": "JavaScript", "weight": 1}])["score"] == 0


def test_custom_skill_not_in_dictionary():
    assert score_resume("Experienced in Cobol mainframes", [{"skill": "COBOL", "weight": 1}])["score"] == 100


def test_extract_skills_lists_evidence():
    found = {s["skill"] for s in extract_skills("Python, SQL and Docker", D)}
    assert {"Python", "SQL", "Docker"} <= found
