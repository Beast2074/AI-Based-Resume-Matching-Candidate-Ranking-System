"""
Skill Matching Service.
Features:
- Regex-based matcher with custom boundaries for C++, C#, .NET, Node.js
- Guaranteed isolation: Java never matches JavaScript
- Context gating for short ambiguous skills (R, C, Go)
- Evidence tier labeling ('experience' vs 'skills_list' vs 'other') with context snippets
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

AMBIGUOUS_SHORT_SKILLS = {"c", "r", "go"}

PROGRAMMING_CONTEXT_WORDS = {
    "programming", "language", "developer", "engineer", "software", "code",
    "coding", "development", "backend", "frontend", "fullstack", "script",
    "runtime", "compiler", "sdk", "api", "framework", "library", "syntax",
    "stack", "proficient", "proficiency", "skills"
}


def load_skills_data() -> Dict[str, Dict[str, Any]]:
    skills_path = Path(__file__).resolve().parent.parent / "data" / "skills.json"
    with open(skills_path, "r", encoding="utf-8") as f:
        return json.load(f)


class SkillMatcher:
    def __init__(self, skills_dict: Optional[Dict[str, Dict[str, Any]]] = None):
        if skills_dict is None:
            skills_dict = load_skills_data()
        self.skills_dict = skills_dict
        
        # Build mapping of alias -> canonical_name and category
        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_categories: Dict[str, str] = {}
        
        # We will compile regex patterns for every alias
        # Sort aliases by length descending so longer phrases match first (e.g. 'javascript' before 'java')
        all_aliases = []
        for canonical, data in self.skills_dict.items():
            self.canonical_categories[canonical] = data.get("category", "software")
            aliases = data.get("aliases", [])
            for alias in aliases:
                norm_alias = alias.lower().strip()
                self.alias_to_canonical[norm_alias] = canonical
                all_aliases.append(norm_alias)

        # Remove duplicates while preserving order
        unique_aliases = sorted(list(set(all_aliases)), key=lambda x: len(x), reverse=True)
        self.compiled_matchers: List[Tuple[str, str, re.Pattern]] = []

        for alias in unique_aliases:
            canonical = self.alias_to_canonical[alias]
            pattern = self._build_pattern(alias)
            self.compiled_matchers.append((alias, canonical, pattern))

    def _build_pattern(self, alias: str) -> re.Pattern:
        """
        Builds a robust regex pattern respecting boundaries for special symbols like +, #, ., -
        """
        escaped = re.escape(alias)
        
        # Prefix boundary: not preceded by word character or special skill chars
        # For .NET or similar starting with dot
        if alias.startswith("."):
            prefix = r"(?<![a-zA-Z0-9_])"
        else:
            prefix = r"(?<![a-zA-Z0-9_])"
            
        # Suffix boundary: not followed by word character or +/#
        if alias.endswith("+") or alias.endswith("#"):
            suffix = r"(?![a-zA-Z0-9_+])"
        else:
            suffix = r"(?![a-zA-Z0-9_])"

        # Explicit safeguard: if alias is 'java', ensure next characters are not 'script'
        if alias == "java":
            pattern_str = rf"{prefix}java(?!script){suffix}"
        else:
            pattern_str = rf"{prefix}{escaped}{suffix}"

        return re.compile(pattern_str, re.IGNORECASE)

    def _is_ambiguous_valid(self, alias: str, text: str, match_start: int, match_end: int, is_skills_section: bool) -> bool:
        """
        Ambiguous names (R, C, Go) only count in the skills section or next to programming words.
        """
        if alias.lower() not in AMBIGUOUS_SHORT_SKILLS:
            return True
        if is_skills_section:
            return True
            
        # Check window around match (100 characters before and after)
        start_w = max(0, match_start - 100)
        end_w = min(len(text), match_end + 100)
        window = text[start_w:end_w].lower()
        
        # Tokenize window and check for presence of programming words
        window_words = set(re.findall(r"[a-z]+", window))
        if window_words.intersection(PROGRAMMING_CONTEXT_WORDS):
            return True
            
        return False

    def _is_negated(self, text: str, match_start: int) -> bool:
        """
        Check if skill occurrence is negated (e.g. 'no experience with Kubernetes',
        'never worked with AWS', 'did not work with MySQL').
        """
        prefix = text[max(0, match_start - 60):match_start]
        clauses = re.split(r"[.;!\n]", prefix)
        curr_clause = clauses[-1].strip().lower()

        neg_pattern = re.compile(
            r"\b("
            r"no|not|never|without|lack\s+of|lacking|little\s+to\s+no|minimal|"
            r"(?:did|have|had|do)\s+not|(?:didn't|haven't|hadn't|don't)"
            r")\s+"
            r"(?:"
            r"(?:any\s+)?(?:prior|direct|hands[- ]on|formal|practical|commercial|production)?\s*"
            r"(?:experience|exposure|knowledge|skills?|familiarity|background)?\s*"
            r"(?:in|with|of|to|using|on)?|"
            r"(?:worked\s+with|used|utilize|work\s+with|familiar\s+with)\s*"
            r")$",
            re.IGNORECASE,
        )
        return bool(neg_pattern.search(curr_clause))

    def extract_skills_from_text(self, text: str, is_skills_section: bool = False) -> List[Dict[str, Any]]:
        """Extract skills from a single text block."""
        if not text:
            return []
            
        matches = []
        seen_aliases = set()

        for alias, canonical, pattern in self.compiled_matchers:
            for m in pattern.finditer(text):
                if not self._is_ambiguous_valid(alias, text, m.start(), m.end(), is_skills_section):
                    continue
                if self._is_negated(text, m.start()):
                    try:
                        from app.services.logger import record_log
                        record_log("SKILLS", "INFO", f"Negation trap blocked: 0 credit awarded for negated '{canonical}'")
                    except Exception:
                        pass
                    continue  # Negation trap defended: no false-positive credit granted

                snippet_start = max(0, m.start() - 40)
                snippet_end = min(len(text), m.end() + 40)
                snippet = text[snippet_start:snippet_end].replace("\n", " ").strip()

                matches.append({
                    "canonical": canonical,
                    "alias": alias,
                    "start": m.start(),
                    "end": m.end(),
                    "snippet": f"...{snippet}..." if snippet_start > 0 else f"{snippet}..."
                })
                seen_aliases.add(alias)

        return matches

    def match_resume_skills(self, sections: Dict[str, str], raw_text: str = "") -> List[Dict[str, Any]]:
        """
        Finds all skills and assigns an evidence label:
        - 'experience' if it appears inside experience or projects text
        - 'skills_list' if it appears only in the skills section
        - 'other' otherwise (e.g. summary, education, other)
        """
        # Tiered extraction
        exp_text = f"{sections.get('experience', '')}\n{sections.get('projects', '')}".strip()
        skills_text = sections.get("skills", "").strip()
        other_text = f"{sections.get('summary', '')}\n{sections.get('education', '')}\n{sections.get('certifications', '')}".strip()
        if not (exp_text or skills_text or other_text):
            other_text = raw_text

        # 1. Experience matches
        exp_matches = self.extract_skills_from_text(exp_text, is_skills_section=False)
        # 2. Skills list matches
        skills_matches = self.extract_skills_from_text(skills_text, is_skills_section=True)
        # 3. Other matches
        other_matches = self.extract_skills_from_text(other_text, is_skills_section=False)

        # Merge evidence per canonical skill: experience > skills_list > other
        best_per_canonical: Dict[str, Dict[str, Any]] = {}

        for m in exp_matches:
            can = m["canonical"]
            if can not in best_per_canonical:
                best_per_canonical[can] = {
                    "skill": can,
                    "matched_alias": m["alias"],
                    "evidence": "experience",
                    "category": self.canonical_categories.get(can, "software"),
                    "snippet": m["snippet"]
                }

        for m in skills_matches:
            can = m["canonical"]
            if can not in best_per_canonical:
                best_per_canonical[can] = {
                    "skill": can,
                    "matched_alias": m["alias"],
                    "evidence": "skills_list",
                    "category": self.canonical_categories.get(can, "software"),
                    "snippet": m["snippet"]
                }

        for m in other_matches:
            can = m["canonical"]
            if can not in best_per_canonical:
                best_per_canonical[can] = {
                    "skill": can,
                    "matched_alias": m["alias"],
                    "evidence": "other",
                    "category": self.canonical_categories.get(can, "software"),
                    "snippet": m["snippet"]
                }

        return list(best_per_canonical.values())


# Singleton instance
_skill_matcher_instance = None

def get_skill_matcher() -> SkillMatcher:
    global _skill_matcher_instance
    if _skill_matcher_instance is None:
        _skill_matcher_instance = SkillMatcher()
    return _skill_matcher_instance
