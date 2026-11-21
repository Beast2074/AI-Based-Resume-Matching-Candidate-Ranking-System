"""
Resume Parsing Service.
Supports PDF (PyMuPDF with pdfplumber fallback) and DOCX (paragraphs, tables, headers, footers).
Cleans text, splits into canonical sections, extracts contact details & name, parses experience timeline & total years.
"""

import io
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Section heading keywords mapped to canonical section keys
SECTION_PATTERNS = {
    "summary": [
        r"professional\s+summary",
        r"summary\s+of\s+qualifications",
        r"executive\s+summary",
        r"career\s+summary",
        r"profile",
        r"about\s+me",
        r"summary",
        r"objective",
        r"career\s+objective",
    ],
    "skills": [
        r"technical\s+skills",
        r"core\s+competencies",
        r"skills\s*&\s*expertise",
        r"skills\s*&\s*technologies",
        r"tools\s*&\s*technologies",
        r"technologies",
        r"tech\s+stack",
        r"key\s+skills",
        r"skills",
        r"competencies",
        r"areas\s+of\s+expertise",
    ],
    "experience": [
        r"work\s+experience",
        r"professional\s+experience",
        r"employment\s+history",
        r"work\s+history",
        r"relevant\s+experience",
        r"experience",
        r"career\s+history",
    ],
    "projects": [
        r"key\s+projects",
        r"featured\s+projects",
        r"technical\s+projects",
        r"personal\s+projects",
        r"academic\s+projects",
        r"projects",
    ],
    "education": [
        r"education\s*&\s*credentials",
        r"academic\s+background",
        r"academic\s+history",
        r"qualifications",
        r"education",
    ],
    "certifications": [
        r"licenses\s*&\s*certifications",
        r"certifications",
        r"certificates",
        r"credentials",
        r"accreditations",
    ],
}

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Regex to detect date ranges:
# 1) Mon YYYY - Mon YYYY / Present
# 2) MM/YYYY - MM/YYYY / Present
# 3) YYYY - YYYY / Present
MONTH_NAMES_REGEX = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE_RANGE_REGEX = re.compile(
    rf"(?P<start_m>{MONTH_NAMES_REGEX})?\.?\s*(?P<start_y>\b20\d\d|19\d\d)\b"
    rf"\s*(?:-|–|—|to)\s*"
    rf"(?:(?P<end_m>{MONTH_NAMES_REGEX})?\.?\s*(?P<end_y>\b20\d\d|19\d\d)\b|(?P<present>present|current|now|ongoing))\b",
    re.IGNORECASE,
)
NUMERIC_DATE_RANGE_REGEX = re.compile(
    r"\b(?P<start_m>0?[1-9]|1[0-2])/(?P<start_y>19\d\d|20\d\d)\b"
    r"\s*(?:-|–|—|to)\s*"
    r"(?:\b(?P<end_m>0?[1-9]|1[0-2])/(?P<end_y>19\d\d|20\d\d)\b|(?P<present>present|current|now|ongoing))\b",
    re.IGNORECASE,
)
YEAR_ONLY_RANGE_REGEX = re.compile(
    r"\b(?P<start_y>19\d\d|20\d\d)\b\s*(?:-|–|—|to)\s*(?:\b(?P<end_y>19\d\d|20\d\d)\b|(?P<present>present|current|now|ongoing))\b",
    re.IGNORECASE,
)


def clean_text(raw: str) -> str:
    """
    Normalise unicode, replace bullet glyphs, join hyphenated line breaks, collapse whitespace.
    """
    if not raw:
        return ""
    # Normalise unicode
    text = unicodedata.normalize("NFKD", raw)
    
    # Replace bullet glyphs with standard dash
    bullet_glyphs = ["\u2022", "\u2023", "\u25E6", "\u2043", "\u2219", "\u25CF", "\u25CB", "\u25AA", "\u25AB", "\uf0b7", "\xb7"]
    for b in bullet_glyphs:
        text = text.replace(b, "- ")
    
    # Normalize carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Join hyphenated line breaks (e.g. "experi-\nence" -> "experience")
    text = re.sub(r"(\b[a-zA-Z]+)-\n\s*([a-zA-Z]+\b)", r"\1\2", text)
    
    # Clean whitespace per line
    lines = []
    for line in text.split("\n"):
        cleaned = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(cleaned)
    
    # Collapse multiple consecutive blank lines
    result_lines = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                result_lines.append("")
                prev_blank = True
        else:
            result_lines.append(line)
            prev_blank = False
            
    return "\n".join(result_lines).strip()


def extract_pdf_text(file_bytes: bytes) -> Tuple[str, str, List[str]]:
    """
    Extract text using PyMuPDF (blocks with sort=True).
    Fallback to pdfplumber if characters < 200.
    Returns (cleaned_text, parse_status, warnings).
    """
    warnings = []
    text_parts = []
    parse_status = "ok"

    try:
        import pymupdf as fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            # sort=True ensures proper reading order for multi-column layouts
            blocks = page.get_text("blocks", sort=True)
            for b in blocks:
                block_text = b[4].strip()
                if block_text:
                    text_parts.append(block_text)
        doc.close()
    except Exception as e:
        warnings.append(f"PyMuPDF error: {str(e)}")

    extracted = "\n".join(text_parts).strip()

    # If fewer than 200 characters, fallback to pdfplumber
    if len(extracted) < 200:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                plumber_parts = []
                for p in pdf.pages:
                    ptxt = p.extract_text()
                    if ptxt:
                        plumber_parts.append(ptxt.strip())
                if plumber_parts:
                    plumber_text = "\n".join(plumber_parts).strip()
                    if len(plumber_text) > len(extracted):
                        extracted = plumber_text
                        warnings.append("Used pdfplumber fallback due to low text yield from primary extractor.")
        except Exception as e:
            warnings.append(f"pdfplumber fallback error: {str(e)}")

    if len(extracted) < 200:
        parse_status = "no_text_layer"
        warnings.append("Document has fewer than 200 extractable characters; likely a scanned image or empty document.")

    return clean_text(extracted), parse_status, warnings


def extract_docx_text(file_bytes: bytes) -> Tuple[str, str, List[str]]:
    """
    Extract DOCX text reading paragraphs AND table cells in document order,
    plus headers and footers.
    """
    import docx
    warnings = []
    parse_status = "ok"
    text_parts = []

    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        
        # 1. Header text
        for section in doc.sections:
            for p in section.header.paragraphs:
                txt = p.text.strip()
                if txt:
                    text_parts.append(txt)

        # 2. Body elements in document order (paragraphs and tables)
        for child in doc.element.body:
            tag = child.tag.lower()
            if tag.endswith("p"):
                # Find matching paragraph object
                for p in doc.paragraphs:
                    if p._p is child:
                        t = p.text.strip()
                        if t:
                            text_parts.append(t)
                        break
            elif tag.endswith("tbl"):
                # Find matching table object
                for tbl in doc.tables:
                    if tbl._tbl is child:
                        for row in tbl.rows:
                            row_cells = []
                            for cell in row.cells:
                                ctxt = cell.text.strip()
                                if ctxt and ctxt not in row_cells:
                                    row_cells.append(ctxt)
                            if row_cells:
                                text_parts.append(" | ".join(row_cells))
                        break

        # 3. Footer text
        for section in doc.sections:
            for p in section.footer.paragraphs:
                txt = p.text.strip()
                if txt:
                    text_parts.append(txt)

    except Exception as e:
        warnings.append(f"DOCX extraction error: {str(e)}")
        parse_status = "error"

    extracted = "\n".join(text_parts).strip()
    if len(extracted) < 50:
        parse_status = "no_text_layer"
        warnings.append("DOCX contains minimal or no extractable text.")

    return clean_text(extracted), parse_status, warnings


def split_sections(text: str) -> Tuple[str, Dict[str, str]]:
    """
    Split text into sections by headings.
    Text before the first heading is the header block.
    Returns (header_block, {section_name: section_text}).
    """
    lines = text.split("\n")
    header_lines = []
    sections: Dict[str, List[str]] = {}
    current_section: Optional[str] = None
    
    # Compile regexes for section headings
    compiled_patterns = {}
    for sec_name, pats in SECTION_PATTERNS.items():
        compiled_patterns[sec_name] = [
            re.compile(rf"^[\s#*\-_]*(?:{pat})[\s:*#\-_]*$", re.IGNORECASE)
            for pat in pats
        ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section and sections[current_section]:
                sections[current_section].append("")
            elif not current_section:
                header_lines.append("")
            continue

        # Check if line matches any section heading
        matched_section = None
        # Must be reasonably short to be a section heading (typically <= 60 chars)
        if len(stripped) <= 60:
            for sec_name, regex_list in compiled_patterns.items():
                for rgx in regex_list:
                    if rgx.match(stripped):
                        matched_section = sec_name
                        break
                if matched_section:
                    break

        if matched_section:
            current_section = matched_section
            if current_section not in sections:
                sections[current_section] = []
        else:
            if current_section is None:
                header_lines.append(line)
            else:
                sections[current_section].append(line)

    header_block = "\n".join(header_lines).strip()
    final_sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    return header_block, final_sections


def extract_contacts(text: str, header_block: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract email and phone number from text (prioritizing header block)."""
    search_scope = f"{header_block}\n\n{text}"
    
    # Email regex
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", search_scope)
    email = email_match.group(0) if email_match else None

    # Phone regex
    phone_match = re.search(
        r"(?:\+?\d{1,3}[\s.-]*)?(?:\(?\d{3}\)?[\s.-]*)?\b\d{3}[\s.-]*\d{4}\b",
        search_scope,
    )
    phone = phone_match.group(0).strip() if phone_match else None

    return email, phone


def extract_name(text: str, header_block: str, filename: str) -> str:
    """
    Name is the first of the top 5 non-empty lines that is not an email,
    phone or URL and has 2 to 4 alphabetic words. Fall back to the filename.
    """
    candidate_lines = []
    source = header_block if header_block else text
    for line in source.split("\n"):
        clean_l = line.strip()
        if clean_l:
            candidate_lines.append(clean_l)
        if len(candidate_lines) >= 5:
            break

    for line in candidate_lines:
        # Skip if contains @ (email)
        if "@" in line:
            continue
        # Skip if contains URL or www or http
        if "http" in line.lower() or "www." in line.lower() or ".com" in line.lower() or "github.com" in line.lower() or "linkedin.com" in line.lower():
            continue
        # Skip if contains phone numbers (more than 5 digits)
        if len(re.findall(r"\d", line)) >= 5:
            continue
        # Remove extra punctuation
        cleaned = re.sub(r"[^a-zA-Z\s'-]", " ", line).strip()
        words = cleaned.split()
        if 2 <= len(words) <= 4:
            # Check that words look like name parts (mostly titlecase or uppercase, alphabetic)
            if all(w.isalpha() for w in words):
                return " ".join(words)

    # Fallback to filename (strip extension and separators)
    fallback = Path(filename).stem
    fallback = re.sub(r"[_\-]+", " ", fallback)
    fallback = re.sub(r"\b(resume|cv|synthetic|gold|final|v\d+)\b", "", fallback, flags=re.I).strip()
    return fallback.title() if fallback else Path(filename).stem


def parse_date_range_match(match: re.Match) -> Optional[Tuple[datetime, datetime]]:
    """Convert regex match groups into start and end datetime objects."""
    gd = match.groupdict()
    now = datetime.now()
    
    # Start date
    start_y = int(gd["start_y"])
    start_m_raw = gd.get("start_m")
    if start_m_raw:
        start_m_raw = start_m_raw.lower().rstrip(".")
        start_m = MONTH_MAP.get(start_m_raw, 1) if not start_m_raw.isdigit() else int(start_m_raw)
    else:
        start_m = 1
    
    start_date = datetime(start_y, start_m, 1)

    # End date
    if gd.get("present"):
        end_date = now
    else:
        end_y = int(gd["end_y"])
        end_m_raw = gd.get("end_m")
        if end_m_raw:
            end_m_raw = end_m_raw.lower().rstrip(".")
            end_m = MONTH_MAP.get(end_m_raw, 12) if not end_m_raw.isdigit() else int(end_m_raw)
        else:
            end_m = 12
        end_date = datetime(end_y, end_m, 1)

    if start_date <= end_date:
        return start_date, end_date
    return None


def extract_date_ranges_from_line(line: str) -> List[Tuple[datetime, datetime]]:
    """Extract any valid date ranges from a line."""
    ranges = []
    
    # Check month name date range first
    for m in DATE_RANGE_REGEX.finditer(line):
        dr = parse_date_range_match(m)
        if dr:
            ranges.append(dr)
            
    # Check numeric MM/YYYY - MM/YYYY
    if not ranges:
        for m in NUMERIC_DATE_RANGE_REGEX.finditer(line):
            dr = parse_date_range_match(m)
            if dr:
                ranges.append(dr)

    # Check YYYY - YYYY
    if not ranges:
        for m in YEAR_ONLY_RANGE_REGEX.finditer(line):
            dr = parse_date_range_match(m)
            if dr:
                ranges.append(dr)

    return ranges


def parse_experience_entries(
    sections: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], List[Tuple[datetime, datetime]]]:
    """
    Experience entries: a line with a date range starts a new entry.
    Only count ranges inside experience and projects sections, never education.
    """
    entries = []
    all_ranges: List[Tuple[datetime, datetime]] = []

    # Target only experience and projects sections
    target_sections = []
    if "experience" in sections:
        target_sections.append(("experience", sections["experience"]))
    if "projects" in sections:
        target_sections.append(("projects", sections["projects"]))

    for sec_type, sec_text in target_sections:
        lines = sec_text.split("\n")
        current_entry: Optional[Dict[str, Any]] = None

        for idx, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            ranges_in_line = extract_date_ranges_from_line(line_stripped)

            if ranges_in_line:
                # Starts a new entry
                if current_entry:
                    current_entry["text"] = "\n".join(current_entry["lines"]).strip()
                    entries.append(current_entry)

                date_range = ranges_in_line[0]
                all_ranges.append(date_range)

                # Title is either this line or the previous non-empty line
                title = line_stripped
                if idx > 0 and len(lines[idx - 1].strip()) > 0 and len(lines[idx - 1].strip()) < 80:
                    prev_line = lines[idx - 1].strip()
                    if not extract_date_ranges_from_line(prev_line):
                        title = f"{prev_line} - {line_stripped}"

                current_entry = {
                    "section": sec_type,
                    "title": title,
                    "start_date": date_range[0].strftime("%Y-%m"),
                    "end_date": date_range[1].strftime("%Y-%m"),
                    "date_tuple": (date_range[0], date_range[1]),
                    "lines": [line_stripped],
                }
            else:
                if current_entry is not None:
                    current_entry["lines"].append(line_stripped)
                else:
                    # Content before the first date range in the section
                    current_entry = {
                        "section": sec_type,
                        "title": line_stripped,
                        "start_date": None,
                        "end_date": None,
                        "date_tuple": None,
                        "lines": [line_stripped],
                    }

        if current_entry:
            current_entry["text"] = "\n".join(current_entry["lines"]).strip()
            entries.append(current_entry)

    return entries, all_ranges


def calculate_total_years(date_ranges: List[Tuple[datetime, datetime]]) -> float:
    """
    total_years: merge overlapping date ranges, add up the months, divide by 12, round to 1 decimal.
    'Present' means today.
    """
    if not date_ranges:
        return 0.0

    # Convert each date range into discrete [start_month_index, end_month_index]
    intervals: List[Tuple[int, int]] = []
    for start_d, end_d in date_ranges:
        start_idx = start_d.year * 12 + start_d.month
        end_idx = end_d.year * 12 + end_d.month
        if start_idx <= end_idx:
            intervals.append((start_idx, end_idx))

    if not intervals:
        return 0.0

    # Sort intervals by start month
    intervals.sort(key=lambda x: (x[0], x[1]))

    # Merge overlapping or contiguous intervals
    merged: List[Tuple[int, int]] = []
    curr_start, curr_end = intervals[0]

    for next_start, next_end in intervals[1:]:
        if next_start <= curr_end + 1:  # overlapping or directly consecutive
            curr_end = max(curr_end, next_end)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = next_start, next_end
    merged.append((curr_start, curr_end))

    # Calculate total distinct months
    total_months = sum((end - start + 1) for start, end in merged)
    return round(total_months / 12.0, 1)


def parse_resume(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Main parser entrypoint. Parses PDF or DOCX file bytes into structured candidate data.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        raw_text, parse_status, warnings = extract_pdf_text(file_bytes)
    elif ext in [".docx", ".doc"]:
        raw_text, parse_status, warnings = extract_docx_text(file_bytes)
    else:
        # Try raw text
        raw_text = clean_text(file_bytes.decode("utf-8", errors="ignore"))
        parse_status = "ok" if len(raw_text) >= 100 else "no_text_layer"
        warnings = []

    if parse_status == "no_text_layer":
        return {
            "filename": filename,
            "parse_status": parse_status,
            "parse_warnings": warnings,
            "name": extract_name("", "", filename),
            "email": None,
            "phone": None,
            "total_years": 0.0,
            "sections": {},
            "header_block": "",
            "entries": [],
            "raw_text": raw_text,
        }

    # Split into sections
    header_block, sections = split_sections(raw_text)
    email, phone = extract_contacts(raw_text, header_block)
    name = extract_name(raw_text, header_block, filename)

    # Parse experience entries and calculate total years
    entries, date_ranges = parse_experience_entries(sections)
    total_years = calculate_total_years(date_ranges)

    return {
        "filename": filename,
        "parse_status": parse_status,
        "parse_warnings": warnings,
        "name": name,
        "email": email,
        "phone": phone,
        "total_years": total_years,
        "sections": sections,
        "header_block": header_block,
        "entries": [
            {
                "section": e["section"],
                "title": e["title"],
                "start_date": e["start_date"],
                "end_date": e["end_date"],
                "text": e["text"],
            }
            for e in entries
        ],
        "raw_text": raw_text,
    }
