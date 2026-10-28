# Sample data

* `job_description.json` - a fictional "Junior Data Analyst" job (Python 40, SQL 25, Excel 20, Communication 15).
* `GenerateSampleResumes.py` - creates fictional resumes in `sample_data/resumes/`:
  six text PDFs, one scanned (image-only) PDF to exercise OCR, and one invalid file to exercise validation.

All people, e-mail addresses (example.com / example.org) and phone numbers are made up.

```powershell
python sample_data\GenerateSampleResumes.py
```
