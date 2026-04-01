#!/usr/bin/env python3
"""
PDF-to-Knowledge-Base Ingestion Script

Reads a PDF file, sends content to Claude via AWS Bedrock in chunks,
and generates structured YAML entries ready for the bot data directory.

Usage:
    python3 scripts/pdf_ingest.py <bot_id> <pdf_path> [--output <output.yml>] [--pages-per-chunk N]
"""

import argparse
import os
import re
import sys
import textwrap

import boto3
import yaml

try:
    import pdfplumber
except ImportError:
    print("pdfplumber is required. Install it: pip install pdfplumber")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Bedrock client
# ---------------------------------------------------------------------------

_bedrock_client = None


def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _bedrock_client


# ---------------------------------------------------------------------------
# PDF reading
# ---------------------------------------------------------------------------


def extract_pdf_text(pdf_path: str) -> list[dict]:
    """Extract text from each page of a PDF. Returns list of {page, text}."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append({"page": i, "text": text.strip()})
    return pages


def chunk_pages(pages: list[dict], pages_per_chunk: int) -> list[dict]:
    """Group pages into chunks. Returns list of {start_page, end_page, text}."""
    chunks = []
    for i in range(0, len(pages), pages_per_chunk):
        group = pages[i:i + pages_per_chunk]
        combined_text = "\n\n".join(f"--- Page {p['page']} ---\n{p['text']}" for p in group)
        chunks.append({
            "start_page": group[0]["page"],
            "end_page": group[-1]["page"],
            "text": combined_text,
        })
    return chunks


# ---------------------------------------------------------------------------
# Claude via Bedrock
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = textwrap.dedent("""\
    You are building a knowledge base for an employee-facing chatbot. Employees will ask questions
    in natural, casual language — your job is to make every entry findable by the way real people talk.

    Analyze the PDF content below and generate structured YAML entries.

    Each entry must have these fields:
    - id: a short snake_case identifier (e.g., "pto_policy", "401k_retirement_plan")
    - format: always "text"
    - category: a concise topic category (e.g., "Employee Benefits", "Leave Policies", "Work Policies")
    - heading: a clear heading that includes the most common name employees use for this topic
    - search_terms: a comma-separated string of 15-30 terms and phrases (see rules below)
    - content: a conversational, answer-shaped paragraph that directly answers the questions employees would ask

    CRITICAL — search_terms rules:
    - Think like an employee, not an HR writer. Include the casual ways people actually ask:
      "does the company match", "how much PTO do I get", "when am I vested", "what's the 401k policy"
    - Include the FIRST question someone would ask about this topic AND the follow-ups:
      First: "do we have a 401k" → Follow-ups: "how much is the match", "when am I vested", "how do I sign up"
    - Include short/lazy phrasings people type: "401k", "pto", "sick days", "maternity leave"
    - Include formal AND informal terms: "paid time off" AND "PTO" AND "vacation days" AND "time off"
    - Include question stems: "what is the X policy", "how does X work", "am I eligible for X", "tell me about X"
    - 15-30 terms minimum. More is better. Redundancy is fine — casting a wide net matters more than being concise.

    CRITICAL — content rules:
    - Write as if you're answering an employee's question directly, not summarizing a policy document
    - Lead with the answer, then details. "Yes, Bellese matches 3% of your salary..." not "The plan is a Safe Harbor..."
    - Use "you/your" language, not "employees/the employee"
    - Weave key search terms INTO the content naturally so the embedding captures them
    - Include specific numbers, dates, and requirements — these are what employees actually need
    - Each entry must stand alone — don't reference other entries

    Other rules:
    - Break content into logical entries by topic — one entry per distinct concept or section
    - Do NOT create entries for table of contents, page numbers, headers/footers, or boilerplate
    - If a section covers multiple distinct questions employees would ask, split into separate entries
    - If content is too thin or just a heading with no substance, skip it

    Respond with ONLY a valid YAML list (no markdown fences, no explanation). Example format:

    - id: pto_policy
      format: text
      category: Leave Policies
      heading: Paid Time Off (PTO) Policy
      search_terms: "PTO, paid time off, vacation, vacation days, time off, how much PTO, how many vacation days, do I get vacation, PTO balance, use it or lose it, PTO rollover, can I carry over PTO, how do I request time off, requesting PTO, days off, annual leave, how much time off do I get, PTO policy"
      content: |
        You receive paid time off (PTO) based on your years of service. New employees start with
        15 days per year, and this increases to 20 days after 5 years. PTO covers vacation, personal
        days, and sick time — it's all one bank. You can carry over up to 5 unused days into the
        next year, but anything beyond that is use-it-or-lose-it. To request time off, submit through
        the HR portal at least 2 weeks in advance for planned absences.

    Here is the PDF content to analyze (pages {start_page}-{end_page}):

    {content}
""")


def analyze_chunk(chunk: dict, chunk_num: int, total_chunks: int) -> str:
    """Send a chunk of PDF content to Claude and get structured YAML entries back."""
    client = get_bedrock_client()

    prompt = ANALYSIS_PROMPT.format(
        start_page=chunk["start_page"],
        end_page=chunk["end_page"],
        content=chunk["text"],
    )

    print(f"  Processing chunk {chunk_num}/{total_chunks} (pages {chunk['start_page']}-{chunk['end_page']})...")

    response = client.converse(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
        inferenceConfig={"maxTokens": 4096},
        messages=[{"role": "user", "content": [{"text": prompt}]}],
    )

    result = response["output"]["message"]["content"][0]["text"]
    usage = response.get("usage", {})
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    print(f"    -> {input_tokens} input tokens, {output_tokens} output tokens")

    return result


# ---------------------------------------------------------------------------
# Search term enrichment (second pass)
# ---------------------------------------------------------------------------

ENRICHMENT_PROMPT = textwrap.dedent("""\
    You are improving search terms for an employee-facing chatbot knowledge base.

    For each entry below, generate EXPANDED search_terms that cover how real employees actually ask questions.
    The current search terms are too formal — employees type casually in a chat box.

    For EACH entry, your new search_terms MUST include:
    1. The short/lazy version people type: "401k", "pto", "dental"
    2. First questions: "do we have X", "what's our X policy", "tell me about X"
    3. Follow-up questions: "how much", "when does it start", "am I eligible", "how do I sign up"
    4. Casual phrasings: "does the company match", "how many days off", "can I get fired"
    5. All synonyms: formal AND informal names for the same thing
    6. Minimum 20 terms per entry. More is better. Redundancy across entries is fine.

    Respond with ONLY a valid YAML list of objects with "id" and "search_terms" fields.
    Do NOT include any other fields. Example:

    - id: pto_policy
      search_terms: "PTO, paid time off, vacation, vacation days, time off, how much PTO, how many vacation days, do I get vacation, PTO balance, use it or lose it, PTO rollover, can I carry over PTO, how do I request time off, requesting PTO, days off, annual leave, how much time off do I get, PTO policy, what is the PTO policy, how does PTO work, vacation policy"

    Here are the entries to enrich:

    {entries_yaml}
""")

ENRICHMENT_BATCH_SIZE = 15


def enrich_search_terms(entries: list[dict]) -> list[dict]:
    """Second pass: expand search terms with employee-perspective phrasings."""
    client = get_bedrock_client()

    # Build a slim version of entries for the prompt (id, heading, search_terms, first 100 chars of content)
    batches = [entries[i:i + ENRICHMENT_BATCH_SIZE] for i in range(0, len(entries), ENRICHMENT_BATCH_SIZE)]

    enrichments = {}  # id -> new search_terms

    for batch_num, batch in enumerate(batches, start=1):
        slim = []
        for e in batch:
            slim.append({
                "id": e["id"],
                "heading": e.get("heading", ""),
                "category": e.get("category", ""),
                "search_terms": e.get("search_terms", ""),
                "content_preview": e.get("content", "")[:150],
            })

        entries_yaml = yaml.dump(slim, default_flow_style=False, allow_unicode=True, width=120)
        prompt = ENRICHMENT_PROMPT.format(entries_yaml=entries_yaml)

        print(f"  Enriching batch {batch_num}/{len(batches)} ({len(batch)} entries)...")

        response = client.converse(
            modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
            inferenceConfig={"maxTokens": 4096},
            messages=[{"role": "user", "content": [{"text": prompt}]}],
        )

        result = response["output"]["message"]["content"][0]["text"]
        usage = response.get("usage", {})
        print(f"    -> {usage.get('inputTokens', 0)} input, {usage.get('outputTokens', 0)} output tokens")

        parsed = parse_entries_from_response(result)
        for item in parsed:
            if isinstance(item, dict) and "id" in item and "search_terms" in item:
                enrichments[item["id"]] = item["search_terms"]

    # Merge enriched search terms back into entries
    updated = 0
    for entry in entries:
        if entry["id"] in enrichments:
            entry["search_terms"] = enrichments[entry["id"]]
            updated += 1

    print(f"  Enriched search terms for {updated}/{len(entries)} entries")
    return entries


# ---------------------------------------------------------------------------
# YAML parsing and assembly
# ---------------------------------------------------------------------------


def parse_entries_from_response(response_text: str) -> list[dict]:
    """Parse YAML entries from Claude's response, handling common formatting issues."""
    # Strip markdown fences if Claude included them despite instructions
    cleaned = response_text.strip()
    cleaned = re.sub(r"^```ya?ml\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        entries = yaml.safe_load(cleaned)
        if isinstance(entries, list):
            return entries
        return []
    except yaml.YAMLError as e:
        print(f"    WARNING: Failed to parse YAML response: {e}")
        print(f"    Raw response (first 200 chars): {cleaned[:200]}")
        return []


def validate_entry(entry: dict) -> bool:
    """Check that an entry has all required fields."""
    required = {"id", "format", "category", "heading", "search_terms", "content"}
    if not isinstance(entry, dict):
        return False
    missing = required - set(entry.keys())
    if missing:
        print(f"    WARNING: Skipping entry missing fields {missing}: {entry.get('id', '?')}")
        return False
    return True


def build_output(bot_id: str, entries: list[dict], pdf_name: str) -> dict:
    """Assemble the final YAML structure matching the bot data format."""
    from datetime import date

    return {
        "meta": {
            "bot_id": bot_id,
            "title": f"Ingested from {pdf_name}",
            "version": "1",
            "date": str(date.today()),
        },
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Ingest a PDF into bot knowledge base YAML")
    parser.add_argument("bot_id", help="Bot identifier (e.g., 'the-fret-detective')")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument(
        "--output", "-o", help="Output YAML file path (default: scripts/bots/{bot_id}/data/{pdf_name}.yml)"
    )
    parser.add_argument("--pages-per-chunk", type=int, default=5, help="Pages per chunk sent to Claude (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Extract text only, don't call Claude")
    parser.add_argument("--skip-enrichment", action="store_true", help="Skip the search term enrichment pass")
    args = parser.parse_args()

    # Validate PDF exists
    if not os.path.isfile(args.pdf_path):
        print(f"Error: PDF not found: {args.pdf_path}")
        sys.exit(1)

    pdf_name = os.path.splitext(os.path.basename(args.pdf_path))[0]
    pdf_name_clean = re.sub(r"[^a-zA-Z0-9_-]", "-", pdf_name).lower()

    # Default output path
    if not args.output:
        bot_data_dir = os.path.join("scripts", "bots", args.bot_id, "data")
        if not os.path.isdir(bot_data_dir):
            print(f"Error: Bot data directory not found: {bot_data_dir}")
            print(f"  Run 'make scaffold bot={args.bot_id}' first, or specify --output")
            sys.exit(1)
        args.output = os.path.join(bot_data_dir, f"pdf-{pdf_name_clean}.yml")

    # Extract PDF text
    print(f"Reading PDF: {args.pdf_path}")
    pages = extract_pdf_text(args.pdf_path)
    if not pages:
        print("Error: No text content found in PDF")
        sys.exit(1)
    print(f"  Extracted {len(pages)} pages with text content")

    if args.dry_run:
        for p in pages:
            print(f"\n--- Page {p['page']} ---")
            print(p["text"][:500])
        print(f"\nDry run complete. {len(pages)} pages would be processed in "
              f"{len(chunk_pages(pages, args.pages_per_chunk))} chunks.")
        return

    # Chunk pages and process
    chunks = chunk_pages(pages, args.pages_per_chunk)
    print(f"  Split into {len(chunks)} chunks ({args.pages_per_chunk} pages each)")
    print()

    all_entries = []
    for i, chunk in enumerate(chunks, start=1):
        response_text = analyze_chunk(chunk, i, len(chunks))
        entries = parse_entries_from_response(response_text)
        valid = [e for e in entries if validate_entry(e)]
        all_entries.extend(valid)
        print(f"    -> {len(valid)} entries extracted")

    if not all_entries:
        print("\nError: No valid entries were generated")
        sys.exit(1)

    # Deduplicate by id (later chunks win if there's overlap)
    seen_ids = {}
    for entry in all_entries:
        seen_ids[entry["id"]] = entry
    deduped = list(seen_ids.values())
    if len(deduped) < len(all_entries):
        print(f"\n  Deduplicated: {len(all_entries)} -> {len(deduped)} entries")

    # Second pass: enrich search terms with employee-perspective phrasings
    if not args.skip_enrichment:
        print("\nPass 2: Enriching search terms...")
        deduped = enrich_search_terms(deduped)

    # Build and write output
    output = build_output(args.bot_id, deduped, os.path.basename(args.pdf_path))

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    with open(args.output, "w") as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)

    print(f"\nDone! {len(deduped)} entries written to: {args.output}")
    print("  Next steps:")
    print(f"    make load-bot bot={args.bot_id}    # Upload to S3")
    print(f"    make embed bot={args.bot_id}       # Generate embeddings")


if __name__ == "__main__":
    main()
