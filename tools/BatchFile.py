"""Reading and writing link lists held in a .txt or .csv file.

The two halves belong together: whatever `parse` understands, `mark_statuses`
has to be able to write back in the same shape, and both need the same idea of
where the URL column is. Splitting them across modules is how they drift apart.
"""

import csv
import datetime
import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Used to pull a link out of an arbitrary line of a .txt/.csv file.
URL_IN_TEXT = re.compile(r"https?://\S+")

# Trailing marker appended to a .txt line once its link has been handled:
#   https://... - Artist - Song   # status=success @ 2026-07-29T14:02:11
STATUS_TAG = re.compile(r"\s*#\s*status\s*=\s*(\w+)(?:\s*@[^#]*)?\s*$", re.IGNORECASE)

# Column names recognised when reading/writing a link .csv.
URL_HEADERS = ("url", "link", "uri", "address")
TITLE_HEADERS = ("title", "name", "track", "song")
STATUS_HEADERS = ("status", "state", "downloaded", "result")
KNOWN_STATUSES = {"success", "failed", "pending", "skipped", ""}


class BatchFile:
    """Parse a link file, and record each link's outcome back into it."""

    def __init__(self, on_error: Optional[Callable[[str], None]] = None):
        self._on_error = on_error or (lambda message: None)

    # ---------------- Layout ----------------
    @staticmethod
    def csv_layout(rows: List[List[str]], has_header: bool) -> Tuple[int, Optional[int], Optional[int], int]:
        """Work out (url_idx, title_idx, status_idx, first_data_row) for a CSV."""
        url_idx, title_idx, status_idx, start = None, None, None, 0

        if has_header:
            header = [str(h).strip().lower() for h in rows[0]]
            for i, name in enumerate(header):
                if name in URL_HEADERS:
                    url_idx = i
                elif name in TITLE_HEADERS:
                    title_idx = i
                elif name in STATUS_HEADERS:
                    status_idx = i
            start = 1

        if url_idx is None:
            # No usable header: the URL column is the first one that holds a link.
            for row in rows[start:]:
                found = next((i for i, c in enumerate(row)
                              if URL_IN_TEXT.search(str(c))), None)
                if found is not None:
                    url_idx = found
                    break
            url_idx = url_idx if url_idx is not None else 0

        if status_idx is None and not has_header and rows:
            # Headerless file we have written to before: the last column will
            # contain nothing but known status words.
            last = max(len(r) for r in rows) - 1
            if last > url_idx:
                values = [str(r[last]).strip().lower() for r in rows if len(r) > last]
                if values and all(v in KNOWN_STATUSES for v in values):
                    status_idx = last

        return url_idx, title_idx, status_idx, start

    # ---------------- Reading ----------------
    def parse(self, path: Path) -> List[Dict[str, str]]:
        """
        Pull link records out of a .txt or .csv file.

        Returns a list of dicts: {"url": ..., "title": ..., "status": ...}
        where status is "" for a link that has not been downloaded yet.

        .txt  - one link per line. Blank lines and lines starting with # are
                skipped. Anything else on the line becomes the label, so both a
                bare URL and "https://... - Artist - Song" work. A trailing
                "# status=success" marker is read back and stripped.
        .csv  - delimiter and header are sniffed. Columns named url/link/uri and
                title/name/track/song are preferred, plus a status column if one
                is present; failing that the first cell containing a link wins
                and the first non-link cell becomes the label.
        """
        path = Path(path)
        entries: List[Dict[str, str]] = []
        suffix = path.suffix.lower()
        try:
            if suffix in (".csv", ".tsv"):
                with open(path, newline="", encoding="utf-8-sig") as f:
                    sample = f.read(8192)
                    f.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                    except csv.Error:
                        dialect = csv.excel
                    try:
                        has_header = csv.Sniffer().has_header(sample)
                    except csv.Error:
                        has_header = False
                    rows = [r for r in csv.reader(f, dialect) if r]

                if not rows:
                    return []

                url_idx, title_idx, status_idx, start = self.csv_layout(rows, has_header)

                for row in rows[start:]:
                    cell = row[url_idx] if url_idx < len(row) else ""
                    match = (URL_IN_TEXT.search(str(cell))
                             or URL_IN_TEXT.search(" ".join(map(str, row))))
                    if not match:
                        continue

                    title = ""
                    if title_idx is not None and title_idx < len(row):
                        title = str(row[title_idx]).strip()
                    elif len(row) > 1:
                        # No header to go on: use the first cell that isn't the
                        # link and isn't a status word we wrote ourselves.
                        title = next((str(c).strip() for c in row
                                      if c and not URL_IN_TEXT.search(str(c))
                                      and str(c).strip().lower() not in KNOWN_STATUSES), "")

                    status = ""
                    if status_idx is not None and status_idx < len(row):
                        status = str(row[status_idx]).strip().lower()

                    entries.append({"url": match.group(0).rstrip(",;\"'"),
                                    "title": title, "status": status})
            else:
                with open(path, encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        status = ""
                        tag = STATUS_TAG.search(line)
                        if tag:
                            status = tag.group(1).strip().lower()
                            line = line[:tag.start()].rstrip()

                        match = URL_IN_TEXT.search(line)
                        if not match:
                            continue
                        url = match.group(0).rstrip(",;\"'")
                        title = line.replace(match.group(0), "").strip(" ,|-\t")
                        entries.append({"url": url, "title": title, "status": status})
        except OSError as e:
            self._on_error(f"Could not read {path}: {e}")
            return []
        return entries

    # ---------------- Writing ----------------
    def mark_statuses(self, path: Path, statuses: Dict[str, str]) -> bool:
        """
        Record the outcome of each link back into the source file.

        `statuses` maps url -> "success" / "failed". The file is rewritten via a
        temporary sibling and os.replace, so an interrupted write cannot leave a
        half-written list behind. A one-off .bak copy is kept.
        """
        if not statuses:
            return True

        path = Path(path)
        stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        tmp_path = path.with_name(path.name + ".tmp")
        backup = path.with_name(path.name + ".bak")

        try:
            if not backup.exists():
                backup.write_bytes(path.read_bytes())

            if path.suffix.lower() in (".csv", ".tsv"):
                with open(path, newline="", encoding="utf-8-sig") as f:
                    sample = f.read(8192)
                    f.seek(0)
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                    except csv.Error:
                        dialect = csv.excel
                    try:
                        has_header = csv.Sniffer().has_header(sample)
                    except csv.Error:
                        has_header = False
                    rows = [r for r in csv.reader(f, dialect) if r]

                if not rows:
                    return True

                url_idx, _, status_idx, start = self.csv_layout(rows, has_header)
                width = max(len(r) for r in rows)

                if status_idx is None:
                    status_idx = width
                    width += 1
                    if has_header:
                        rows[0] = (list(rows[0])
                                   + [""] * (status_idx - len(rows[0]))
                                   + ["status"])

                out_rows = []
                for i, row in enumerate(rows):
                    row = list(row) + [""] * (width - len(row))
                    if i >= start:
                        cell = row[url_idx] if url_idx < len(row) else ""
                        match = (URL_IN_TEXT.search(str(cell))
                                 or URL_IN_TEXT.search(" ".join(map(str, row))))
                        if match:
                            url = match.group(0).rstrip(",;\"'")
                            if url in statuses:
                                row[status_idx] = statuses[url]
                    out_rows.append(row)

                with open(tmp_path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f, dialect).writerows(out_rows)

            else:
                with open(path, encoding="utf-8-sig") as f:
                    lines = f.read().splitlines()

                out_lines = []
                for raw in lines:
                    stripped = raw.strip()
                    if not stripped or stripped.startswith("#"):
                        out_lines.append(raw)
                        continue

                    # Only touch lines in this batch - anything else keeps the
                    # marker an earlier run gave it.
                    body = STATUS_TAG.sub("", raw.rstrip())
                    match = URL_IN_TEXT.search(body)
                    url = match.group(0).rstrip(",;\"'") if match else None
                    if url and url in statuses:
                        out_lines.append(f"{body}  # status={statuses[url]} @ {stamp}")
                    else:
                        out_lines.append(raw)

                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(out_lines) + "\n")

            os.replace(tmp_path, path)
            return True

        except (OSError, csv.Error) as e:
            self._on_error(f"Could not update statuses in {path}: {e}")
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return False