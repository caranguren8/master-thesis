#!/usr/bin/env python3
"""
Automated thesis review loop.

Extracts text from thesis_draft.docx and the two reference PDFs,
sends them to the Anthropic API for structured critique, and saves
the feedback to a timestamped markdown file.

Usage:
    python scripts/review_thesis.py                  # single review
    python scripts/review_thesis.py --iterations 3   # 3 back-to-back reviews

Requirements:
    pip install anthropic python-docx pdfplumber

Environment:
    ANTHROPIC_API_KEY must be set.
"""

import argparse
import datetime
import os
import sys
import textwrap

# ---------------------------------------------------------------------------
# PDF / DOCX text extraction
# ---------------------------------------------------------------------------

def extract_docx_text(path: str) -> str:
    """Extract all paragraph text from a .docx file."""
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_pdf_text(path: str) -> str:
    """Extract all text from a PDF using pdfplumber."""
    import pdfplumber
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# Review prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
You are a rigorous academic thesis reviewer for a Master's programme in
Applied Information and Data Science at HSLU (Lucerne University of Applied
Sciences and Arts).  You will receive:

1.  The current thesis draft (extracted from a .docx).
2.  The preliminary study that preceded it.
3.  The official grading rubric with 12 criteria and supervisor comments.

Your job is to produce a structured, actionable review.  For each issue you
find, classify it as one of:
  • FACTUAL ERROR   – incorrect statement or internal contradiction
  • MISSING ELEMENT – something the rubric or supervisor requires that is absent
  • CITATION ISSUE  – reference/citation problems
  • NUMERICAL ISSUE – inconsistent numbers, rounding errors
  • SCOPE / FRAMING – scope changes, missing justifications
  • MINOR           – formatting, style, small wording issues

For each issue:
  1. State the classification tag in CAPS.
  2. Quote the problematic sentence(s) or section heading.
  3. Explain the problem concisely.
  4. Suggest a concrete fix.

At the end, give an overall assessment:
  • How many issues of each severity?
  • Which rubric criteria (1-12) are now well-addressed vs. still weak?
  • A 1-sentence verdict: "CONVERGED" if no FACTUAL ERROR or MISSING ELEMENT
    issues remain, otherwise "NOT YET CONVERGED".
""")


def build_user_message(thesis_text: str, prelim_text: str, rubric_text: str) -> str:
    return textwrap.dedent(f"""\
## THESIS DRAFT
{thesis_text[:100000]}

## PRELIMINARY STUDY
{prelim_text[:30000]}

## GRADING RUBRIC & SUPERVISOR FEEDBACK
{rubric_text[:15000]}

Please review the thesis draft against the preliminary study and grading
rubric.  Produce your structured review now.
""")


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def call_claude(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Send the review request to the Anthropic API and return the response."""
    import anthropic
    client = anthropic.Anthropic()       # uses ANTHROPIC_API_KEY env var
    message = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Automated thesis review")
    parser.add_argument("--iterations", type=int, default=1,
                        help="Number of review iterations (default: 1)")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-20250514",
                        help="Anthropic model to use")
    args = parser.parse_args()

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    thesis_path = os.path.join(base, "docs", "thesis_draft.docx")
    prelim_path = os.path.join(
        base, "docs", "source_materials",
        "Electoral closeness Preliminary Study Aranguren (1).pdf")
    rubric_path = os.path.join(
        base, "docs", "source_materials", "Grading PS.pdf")

    for p in (thesis_path, prelim_path, rubric_path):
        if not os.path.exists(p):
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(1)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.",
              file=sys.stderr)
        sys.exit(1)

    print("Extracting documents …")
    thesis_text = extract_docx_text(thesis_path)
    prelim_text = extract_pdf_text(prelim_path)
    rubric_text = extract_pdf_text(rubric_path)
    print(f"  Thesis:  {len(thesis_text):,} chars")
    print(f"  Prelim:  {len(prelim_text):,} chars")
    print(f"  Rubric:  {len(rubric_text):,} chars")

    reviews_dir = os.path.join(base, "docs", "reviews")
    os.makedirs(reviews_dir, exist_ok=True)

    for i in range(1, args.iterations + 1):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\n{'='*60}")
        print(f"  ITERATION {i}/{args.iterations}  ({ts})")
        print(f"{'='*60}")

        user_msg = build_user_message(thesis_text, prelim_text, rubric_text)
        print(f"Sending to {args.model} ({len(user_msg):,} chars) …")

        review = call_claude(SYSTEM_PROMPT, user_msg, model=args.model)

        out_path = os.path.join(reviews_dir, f"review_{ts}_iter{i}.md")
        with open(out_path, "w") as f:
            f.write(f"# Thesis Review — Iteration {i}\n")
            f.write(f"Generated: {ts}\n")
            f.write(f"Model: {args.model}\n\n")
            f.write(review)

        print(f"Review saved to: {out_path}")
        print(f"\n{review[:500]}…\n")

        if "CONVERGED" in review.split("\n")[-5:]:
            print("✅  Reviewer says CONVERGED — stopping early.")
            break

        # If doing multiple iterations, re-extract thesis in case the
        # caller regenerated it between iterations (manual mode).
        if i < args.iterations:
            print("(Re-reading thesis for next iteration …)")
            thesis_text = extract_docx_text(thesis_path)

    print("\nDone. All reviews saved in:", reviews_dir)


if __name__ == "__main__":
    main()
