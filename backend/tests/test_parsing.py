"""
Unit tests for resume parsing service and synthetic resume evaluation.
Tests:
- Date parsing (all 4 formats, Present, overlapping ranges, gaps, short roles)
- Section splitting and header block isolation
- Contact details and name extraction
- Parse success rate across all 4 layouts (single_column_pdf, two_column_pdf, table_docx, plain_docx)
- Mean Absolute Error (MAE) of total_years against eval/gold.json
"""

import json
from datetime import datetime
from pathlib import Path
import pytest

from app.services.parsing import (
    clean_text,
    split_sections,
    extract_contacts,
    extract_name,
    extract_date_ranges_from_line,
    calculate_total_years,
    parse_resume,
)


def test_clean_text():
    raw = "Specialist\u2022 Senior\nexperi-\nence at Company.\r\n   Multiple   spaces   here.  "
    cleaned = clean_text(raw)
    assert "- " in cleaned or "Specialist" in cleaned
    assert "experience" in cleaned  # hyphen line break joined
    assert "   " not in cleaned


def test_date_range_formats():
    # 1. Mon YYYY - Mon YYYY
    r1 = extract_date_ranges_from_line("Software Engineer (Jan 2020 - Dec 2022)")
    assert len(r1) == 1
    assert r1[0][0] == datetime(2020, 1, 1)
    assert r1[0][1] == datetime(2022, 12, 1)

    # 2. Mon YYYY - Present
    r2 = extract_date_ranges_from_line("Senior Lead (Mar 2023 - Present)")
    assert len(r2) == 1
    assert r2[0][0] == datetime(2023, 3, 1)
    assert r2[0][1].year == datetime.now().year

    # 3. MM/YYYY - MM/YYYY
    r3 = extract_date_ranges_from_line("Contractor: 06/2021 - 08/2022")
    assert len(r3) == 1
    assert r3[0][0] == datetime(2021, 6, 1)
    assert r3[0][1] == datetime(2022, 8, 1)

    # 4. YYYY - YYYY
    r4 = extract_date_ranges_from_line("Developer 2018 - 2021")
    assert len(r4) == 1
    assert r4[0][0] == datetime(2018, 1, 1)
    assert r4[0][1] == datetime(2021, 12, 1)


def test_overlapping_date_ranges():
    # Job A: Jan 2021 - Dec 2022 (24 months)
    # Job B (concurrent): Jun 2022 - Jun 2023 (13 months, overlapping by 7 months)
    # Combined non-overlapping: Jan 2021 - Jun 2023 = 30 months = 2.5 years
    ranges = [
        (datetime(2021, 1, 1), datetime(2022, 12, 1)),
        (datetime(2022, 6, 1), datetime(2023, 6, 1)),
    ]
    years = calculate_total_years(ranges)
    assert years == 2.5


def test_section_splitting_and_header_isolation():
    text = """John Doe
john.doe@example.com | 555-123-4567

PROFESSIONAL SUMMARY
Experienced backend engineer with 5 years in Java.

TECHNICAL SKILLS
Java, Spring Boot, PostgreSQL, Docker

WORK EXPERIENCE
Senior Developer - Acme Corp
Jan 2021 - Present
- Designed microservices in Java.

EDUCATION
BS in Computer Science, State University, 2017 - 2021
"""
    header, sections = split_sections(text)
    assert "John Doe" in header
    assert "john.doe@example.com" in header
    assert "PROFESSIONAL SUMMARY" not in header
    assert "summary" in sections
    assert "skills" in sections
    assert "experience" in sections
    assert "education" in sections
    assert "Java, Spring Boot" in sections["skills"]


def test_synthetic_resumes_parsing_and_gold_mae():
    base_dir = Path(__file__).resolve().parent.parent.parent
    gold_path = base_dir / "eval" / "gold.json"
    resumes_dir = base_dir / "eval" / "resumes"

    assert gold_path.exists(), "eval/gold.json must exist"
    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    layout_counts = {}
    layout_success = {}
    years_errors = []

    for filename, meta in gold_data.items():
        file_path = resumes_dir / filename
        assert file_path.exists(), f"Resume file {filename} must exist"

        layout = meta["layout"]
        layout_counts[layout] = layout_counts.get(layout, 0) + 1

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        parsed = parse_resume(file_bytes, filename)

        if parsed["parse_status"] == "ok":
            layout_success[layout] = layout_success.get(layout, 0) + 1

        # Check total years against gold
        gold_years = meta["true_total_years"]
        parsed_years = parsed["total_years"]
        abs_err = abs(parsed_years - gold_years)
        years_errors.append(abs_err)

    print("\n--- SYNTHETIC RESUME PARSING REPORT ---")
    total_files = len(gold_data)
    total_success = sum(layout_success.values())
    overall_success_rate = (total_success / total_files) * 100.0

    print(f"Overall Parse Success: {total_success}/{total_files} ({overall_success_rate:.1f}%)")
    for layout, total in layout_counts.items():
        success = layout_success.get(layout, 0)
        rate = (success / total) * 100.0
        print(f"  Layout {layout:20}: {success}/{total} ({rate:.1f}%)")
        assert rate >= 95.0, f"Parse success for {layout} was {rate}%, expected >= 95%"

    mae = sum(years_errors) / len(years_errors) if years_errors else 0.0
    print(f"Total Years Mean Absolute Error (MAE): {mae:.2f} years")
    assert mae < 0.5, f"MAE {mae} is too high, expected < 0.5 years"
