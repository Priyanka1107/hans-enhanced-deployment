import json
import re
import csv
from pathlib import Path
from urllib.parse import urlparse

MANIFEST = Path("outputs/manifest.jl")
OUT_CSV = Path("outputs/page_classification.csv")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[’'“”\"().,:;!?]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80] if text else ""

def classify(url: str, title: str) -> tuple[str, str, str]:
    """
    Returns: (page_class, confidence, notes)
    """
    p = urlparse(url)
    path = p.path.lower()

    # Only English scope (safety)
    if not path.startswith("/en/"):
        return ("exclude_non_en", "high", "not under /en/")

    # Common exclusions (you can expand later)
    if any(x in path for x in ["/search/", "/sitemap", "/login", "/newsletter"]):
        return ("exclude", "high", "utility/navigation page")

    # Program pages (English study programmes)
    if "/english-language-study-programmes/" in path:
        # Electives/core course subpages
        if any(x in path for x in ["/elective", "/core-courses", "/modules", "/course"]):
            return ("curriculum_page", "high", "program curriculum subpage")

        # Looks like a program overview page
        if any(x in path for x in ["-bachelor", "-master", "/bachelor", "/master"]):
            return ("degree_program", "high", "program overview page")

        return ("degree_program", "medium", "likely program-related, confirm")

    # Applications section
    if "/studies/applications/" in path:
        if "uni-assist" in path or "uniassist" in path or "uni_assis" in path:
            return ("application_route_rule", "high", "uni-assist/application route page")
        if "deadline" in path or "period" in path:
            return ("deadline_rule", "medium", "deadline-related, confirm content")
        if "/master" in path or "masters" in path:
            return ("application_process", "high", "master applications page")
        return ("application_process", "medium", "application page, confirm")

    # Degree programmes index pages
    if "/studies/degree-programmes/" in path:
        if "/faq" in path:
            return ("faq_support", "high", "FAQ page")
        return ("overview_navigation", "medium", "programme overview/navigation")

    # Fees / cost / semester contribution hints
    if any(x in path for x in ["/fees", "/cost", "/semester-fee", "/semester-contribution", "/contribution"]):
        return ("fees_funding_rule", "medium", "fees-related, confirm content")

    # Language requirements hints
    if any(x in path for x in ["/language", "/english", "/german"]):
        return ("language_proof_rule", "medium", "language-related, confirm content")

    # International / pathways often contain admissions guidance
    if "/international/" in path and any(x in path for x in ["/apply", "/application", "/admission", "/requirements"]):
        return ("application_process", "medium", "international admissions guidance")

    # Default bucket (needs review)
    return ("needs_review", "low", "no strong pattern match")

def suggest_object_id(page_class: str, title: str, url: str) -> str:
    if page_class == "degree_program":
        # Example: "Information Technology (Master)" -> "msc-information-technology"
        t = title.lower()
        if "master" in t:
            prefix = "msc"
        elif "bachelor" in t:
            prefix = "bsc"
        else:
            prefix = "program"
        core = slugify(re.sub(r"\(.*?\)", "", title))
        return f"{prefix}-{core}" if core else ""
    if page_class in ["application_process", "application_route_rule", "deadline_rule", "language_proof_rule", "fees_funding_rule", "transfer_rule", "application_status_support", "foreign_qualification_rule"]:
        core = slugify(title) or slugify(urlparse(url).path.split("/")[-2])
        return f"{page_class}-{core}" if core else ""
    if page_class == "curriculum_page":
        core = slugify(title) or slugify(urlparse(url).path.split("/")[-2])
        return f"curriculum-{core}" if core else ""
    return ""

def main():
    rows = []
    with MANIFEST.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            url = rec.get("url", "")
            title = rec.get("title") or ""
            page_id = rec.get("id", "")
            html_file = rec.get("html_file", "")
            status = rec.get("status", "")

            page_class, confidence, notes = classify(url, title)
            object_id = suggest_object_id(page_class, title, url)

            rows.append({
                "page_id": page_id,
                "status": status,
                "title": title,
                "url": url,
                "html_file": html_file,
                "page_class": page_class,
                "confidence": confidence,
                "object_id_suggested": object_id,
                "notes": notes
            })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved classification to: {OUT_CSV}")
    # Quick summary counts
    counts = {}
    for r in rows:
        counts[r["page_class"]] = counts.get(r["page_class"], 0) + 1
    print("Counts by page_class:")
    for k in sorted(counts, key=counts.get, reverse=True):
        print(f"  {k}: {counts[k]}")

if __name__ == "__main__":
    main()
