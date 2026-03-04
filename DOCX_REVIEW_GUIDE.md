# Reviewing `.docx` files in this repo

GitHub does not render binary Office files inline, so `.docx` files must be reviewed by downloading or converting.

## Option 1: Download from GitHub (quickest)
1. Open the `.docx` file in the GitHub web UI.
2. Click **Download raw file** (or **Raw**).
3. Open the file in Word, Google Docs, or LibreOffice.

## Option 2: Review text in terminal (no GUI)
If you need a quick textual diff/review from this environment:

```bash
python - <<'PY'
from zipfile import ZipFile
from xml.etree import ElementTree as ET

path = 'story/TARS-Newsletter.docx'
with ZipFile(path) as z:
    xml = z.read('word/document.xml')

root = ET.fromstring(xml)
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
texts = [t.text for t in root.findall('.//w:t', ns) if t.text]
print(' '.join(texts))
PY
```

## Option 3: Compare revisions between commits
Use git to restore two versions and extract both texts, then compare:

```bash
git show <old_commit>:story/TARS-Newsletter.docx > /tmp/old.docx
git show <new_commit>:story/TARS-Newsletter.docx > /tmp/new.docx
```

Then run the Python extractor above against each file and diff outputs.

## Option 4: Better PR reviews going forward
For easier code review on GitHub, store an additional text export alongside the binary file, for example:

- `story/TARS-Newsletter.docx` (authoritative source)
- `story/TARS-Newsletter.md` (review-friendly mirror)

That lets reviewers comment inline on readable content while still keeping the Word document.
