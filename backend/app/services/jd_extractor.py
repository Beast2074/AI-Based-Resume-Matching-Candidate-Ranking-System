"""
Job Description (JD) Extraction Service.
Extracts:
- Section splitting: requirements, preferred, responsibilities
- Skill extraction with importance classification (must_have vs nice_to_have)
- Required experience years (lower bound of ranges like 3-5)
- Degree level hierarchy (0=none, 1=diploma, 2=bachelor, 3=master, 4=phd)
- Free-text requirement lines (lines with no recognized skill)
- Responsibilities lines for max-similarity semantic matching
"""

import re
from typing import Dict, List, Optional, Set, Any
from app.services.skills import get_skill_matcher

JD_SECTION_PATTERNS = {
    "preferred": [
        r"preferred\s+qualifications",
        r"nice\s+to\s+have",
        r"bonus\s+points",
        r"bonus\s+qualifications",
        r"desired\s+skills",
        r"preferred",
        r"what\s+gives\s+you\s+an\s+edge",
        r"good\s+to\s+have",
    ],
    "requirements": [
        r"requirements\s*\(must\s+have\)",
        r"required\s+qualifications",
        r"minimum\s+qualifications",
        r"what\s+you\s+bring",
        r"what\s+you\s+need",
        r"must\s+have",
        r"basic\s+qualifications",
        r"requirements",
        r"qualifications",
    ],
    "responsibilities": [
        r"responsibilities",
        r"what\s+you'll\s+do",
        r"what\s+you\s+will\s+do",
        r"day\s+to\s+day",
        r"duties",
        r"key\s+responsibilities",
        r"the\s+role",
        r"role\s+overview",
    ],
}

MUST_HAVE_KEYWORDS = {"required", "must", "proficient", "proficiency", "strong", "essential", "core", "mandatory"}
NICE_TO_HAVE_KEYWORDS = {"preferred", "nice to have", "bonus", "plus", "optional", "advantageous", "desirable"}


def split_jd_sections(jd_text: str) -> Dict[str, List[str]]:
    """Split JD into sections: requirements, preferred, responsibilities, header/other."""
    lines = jd_text.split("\n")
    sections: Dict[str, List[str]] = {
        "header": [],
        "requirements": [],
        "preferred": [],
        "responsibilities": [],
        "other": []
    }
    current_sec = "header"

    # Precompile section heading matchers
    compiled_headings = {}
    for sec_name, pats in JD_SECTION_PATTERNS.items():
        compiled_headings[sec_name] = [
            re.compile(rf"^[\s#*\-_]*(?:{p})(?:\s*\(.*?\))?[\s:*#\-_]*$", re.IGNORECASE)
            for p in pats
        ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        matched_sec = None
        if len(stripped) <= 60:
            for sec_name, regexes in compiled_headings.items():
                for rgx in regexes:
                    if rgx.match(stripped):
                        matched_sec = sec_name
                        break
                if matched_sec:
                    break

        if matched_sec:
            current_sec = matched_sec
        else:
            sections[current_sec].append(stripped)

    return sections


def extract_required_years(jd_text: str) -> Optional[float]:
    """
    Extract required years of experience:
    - Lower bound of ranges like 3-5 years -> 3.0
    - '4+ years of experience' -> 4.0
    - Defaults to None if no mention of years near experience.
    """
    # Range: e.g. 3-5 years, 4 to 6 years
    range_match = re.search(
        r"\b(\d+)\s*(?:-|–|—|to)\s*(\d+)\s*\+?\s*years?(?:\s+of)?\s*(?:relevant\s+|professional\s+)?experience\b",
        jd_text,
        re.IGNORECASE,
    )
    if range_match:
        return float(range_match.group(1))

    # Single number: e.g. 4+ years of experience, 3 years experience, minimum 5 years
    single_match = re.search(
        r"(?:at least|minimum|min\.?)?\s*(\d+)\s*\+?\s*years?(?:\s+of)?\s*(?:relevant\s+|professional\s+)?experience\b",
        jd_text,
        re.IGNORECASE,
    )
    if single_match:
        return float(single_match.group(1))

    # Fallback: any mention of N years of experience anywhere
    general_match = re.search(r"\b(\d+)\s*\+?\s*years?\b", jd_text, re.IGNORECASE)
    if general_match:
        return float(general_match.group(1))

    return None


def extract_degree_level(jd_text: str) -> int:
    """
    Degree level hierarchy:
    0: None
    1: Diploma / Associate
    2: Bachelor (BS, BA, B.S., B.A., Undergraduate)
    3: Master (MS, M.S., MBA, Master's, Postgraduate)
    4: PhD (Doctorate, Ph.D., Doctoral)
    """
    text = jd_text.lower()
    
    # 4. PhD
    if re.search(r"\b(?:ph\.?d\.?|doctorate|doctoral)\b", text):
        return 4
    # 3. Master
    if re.search(r"\b(?:master'?s?|m\.?s\.?|mba|postgraduate)\b", text):
        return 3
    # 2. Bachelor
    if re.search(r"\b(?:bachelor'?s?|b\.?s\.?|b\.?a\.?|undergraduate|b\.?tech|b\.?e\.)\b", text):
        return 2
    # 1. Diploma / Associate
    if re.search(r"\b(?:diploma|associate'?s?|vocational)\b", text):
        return 1

    return 0


def group_any_of_skills(
    line: str,
    matches: List[Dict[str, Any]],
    canonical_categories: Dict[str, str],
    default_importance: str
) -> List[Dict[str, Any]]:
    """
    Groups skills in a line if they are connected by 'or', 'either', or '/'.
    E.g. 'Strong proficiency in Java or Kotlin' -> name: 'Java / Kotlin', any_of: ['Java', 'Kotlin'].
    Otherwise returns them as individual skill requirements.
    """
    if not matches:
        return []

    line_lower = line.lower()
    has_or = bool(re.search(r"\b(?:or|either)\b|/", line_lower))

    seen = set()
    unique_matches = []
    for m in sorted(matches, key=lambda x: x["start"]):
        can = m["canonical"]
        if can not in seen:
            seen.add(can)
            unique_matches.append(m)

    if len(unique_matches) >= 2 and has_or:
        names = [m["canonical"] for m in unique_matches]
        display_name = " / ".join(names)
        primary_cat = canonical_categories.get(names[0], "software")
        return [{
            "name": display_name,
            "skill": display_name,
            "importance": default_importance,
            "any_of": names,
            "category": primary_cat,
        }]

    items = []
    for m in unique_matches:
        can = m["canonical"]
        items.append({
            "name": can,
            "skill": can,
            "importance": default_importance,
            "any_of": [can],
            "category": canonical_categories.get(can, "software"),
        })
    return items


def extract_jd(jd_text: str) -> Dict[str, Any]:
    """
    Parses a job description and extracts:
    - title
    - sections
    - required_years
    - degree_level
    - skills: list of {name, importance: 'must_have'|'nice_to_have', any_of: [...], category}
    - free_text_lines: requirement lines with no matched skills
    - responsibilities_lines: lines under responsibilities section
    """
    sections = split_jd_sections(jd_text)
    required_years = extract_required_years(jd_text)
    degree_level = extract_degree_level(jd_text)

    # Job title from header or first line
    title = "Job Position"
    for line in sections["header"][:3]:
        if "title" in line.lower() or "engineer" in line.lower() or "developer" in line.lower() or "scientist" in line.lower():
            clean_title = re.sub(r"^[\s#*\-_]*job\s+title[\s:*#\-_]*", "", line, flags=re.I).strip()
            if clean_title:
                title = clean_title
                break

    matcher = get_skill_matcher()

    skills_map: Dict[str, Dict[str, Any]] = {}
    free_text_lines: List[str] = []

    # Has explicit requirements or preferred sections?
    has_req = len(sections["requirements"]) > 0
    has_pref = len(sections["preferred"]) > 0

    # 1. Process Requirements Lines
    for line in sections["requirements"]:
        matches = matcher.extract_skills_from_text(line)
        if matches:
            line_lower = line.lower()
            importance = "must_have"
            if any(w in line_lower for w in NICE_TO_HAVE_KEYWORDS) and not any(w in line_lower for w in MUST_HAVE_KEYWORDS):
                importance = "nice_to_have"
            
            grouped = group_any_of_skills(line, matches, matcher.canonical_categories, importance)
            for item in grouped:
                k = item["name"]
                if k not in skills_map:
                    skills_map[k] = item
                elif importance == "must_have":
                    skills_map[k]["importance"] = "must_have"
        else:
            # Only keep substantial requirement lines as free_text
            if len(line.split()) >= 4:
                free_text_lines.append(line)

    # 2. Process Preferred Lines
    for line in sections["preferred"]:
        matches = matcher.extract_skills_from_text(line)
        if matches:
            line_lower = line.lower()
            importance = "nice_to_have"
            if any(w in line_lower for w in MUST_HAVE_KEYWORDS) and not any(w in line_lower for w in NICE_TO_HAVE_KEYWORDS):
                importance = "must_have"
            
            grouped = group_any_of_skills(line, matches, matcher.canonical_categories, importance)
            for item in grouped:
                k = item["name"]
                if k not in skills_map:
                    skills_map[k] = item
                elif importance == "must_have":
                    skills_map[k]["importance"] = "must_have"
        else:
            if len(line.split()) >= 4:
                free_text_lines.append(line)

    # 3. Fallback: if no sections were identified, process entire JD text
    if not has_req and not has_pref:
        for line in jd_text.split("\n"):
            line_str = line.strip()
            if not line_str:
                continue
            matches = matcher.extract_skills_from_text(line_str)
            if matches:
                line_lower = line_str.lower()
                if any(w in line_lower for w in NICE_TO_HAVE_KEYWORDS):
                    importance = "nice_to_have"
                else:
                    importance = "must_have"
                
                grouped = group_any_of_skills(line_str, matches, matcher.canonical_categories, importance)
                for item in grouped:
                    k = item["name"]
                    if k not in skills_map:
                        skills_map[k] = item
                    elif importance == "must_have":
                        skills_map[k]["importance"] = "must_have"

    # Responsibilities lines
    resp_lines = [l for l in sections["responsibilities"] if len(l.split()) >= 3]

    # Collect must-have and nice-to-have skill names (including any_of alternatives)
    must_have_skills = []
    for s in skills_map.values():
        if s["importance"] == "must_have":
            if s["name"] not in must_have_skills:
                must_have_skills.append(s["name"])
            for sub in s.get("any_of", []):
                if sub not in must_have_skills:
                    must_have_skills.append(sub)

    nice_to_have_skills = []
    for s in skills_map.values():
        if s["importance"] == "nice_to_have":
            if s["name"] not in nice_to_have_skills:
                nice_to_have_skills.append(s["name"])
            for sub in s.get("any_of", []):
                if sub not in nice_to_have_skills:
                    nice_to_have_skills.append(sub)

    return {
        "title": title,
        "required_years": required_years,
        "degree_level": degree_level,
        "skills": list(skills_map.values()),
        "must_have_skills": must_have_skills,
        "nice_to_have_skills": nice_to_have_skills,
        "free_text_lines": free_text_lines,
        "responsibilities_lines": resp_lines,
        "sections": sections,
    }
