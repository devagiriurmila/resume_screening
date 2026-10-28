"""Initialise the database and insert the fictional sample job.

Usage:  python database/seed.py            (creates tables + sample job if no jobs exist)
        python database/seed.py --reset    (deletes the database file first)
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import Config  # noqa: E402
from database import queries  # noqa: E402
from database.db import connect, init_db  # noqa: E402
from services.skill_matcher import get_dictionary, normalize_weights  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="delete the existing database first")
    args = parser.parse_args()
    path = Config.DATABASE_PATH
    if args.reset and os.path.exists(path):
        os.remove(path)
        print(f"Deleted {path}")
    init_db(path)
    conn = connect(path)
    try:
        if conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
            with open(os.path.join(ROOT, "sample_data", "job_description.json"), encoding="utf-8") as fh:
                job = json.load(fh)
            d = get_dictionary(Config.SKILLS_DICTIONARY_PATH)
            job["skills"] = normalize_weights([{"skill": d.canonical(s["skill"]) or s["skill"], "weight": s["weight"]}
                                               for s in job["skills"]])
            job.setdefault("source", "sample")
            job_id = queries.save_job(conn, job)
            print(f"Inserted sample job #{job_id}: {job['title']}")
        else:
            print("Jobs already exist - nothing inserted.")
        print(f"Database ready: {path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
