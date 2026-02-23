"""
Chunker Module

Reads YAML files in the universal bot data format and produces
text chunks ready for embedding generation.

Handles two format types:
  - "text": content is already readable text, pass through as-is
  - "structured": apply the template string to each item to produce text

Supports optional 'search_terms' field to improve semantic search matching.

Local usage:  load_bot_data(bot_id)          → reads from bots/{bot_id}/data/
S3/Lambda:    chunk_yaml_content(data, bot_id) → takes a pre-parsed YAML dict
"""
import yaml
from pathlib import Path


# ---------------------------------------------------------------------------
# Entry processing (format-agnostic, no I/O)
# ---------------------------------------------------------------------------

def chunk_text_entry(entry: dict) -> str:
    """'text' format: combine heading + content as-is."""
    heading = entry.get('heading', '')
    content = entry.get('content', '')
    if heading and content:
        return f"{heading}\n\n{content}"
    return content or heading


def chunk_structured_entry(entry: dict) -> str:
    """'structured' format: apply template to each item, combine with heading."""
    heading  = entry.get('heading', '')
    template = entry.get('template', '')
    items    = entry.get('items', [])

    if not template or not items:
        print(f"  Warning: structured entry '{entry.get('id')}' missing template or items")
        return heading

    parts = [heading] if heading else []
    for item in items:
        try:
            parts.append(template.format(**item))
        except KeyError as e:
            print(f"  Warning: template key {e} missing in entry '{entry.get('id')}'")

    return '\n'.join(parts)


def chunk_entry(entry: dict) -> str:
    """Route an entry to the correct chunker, prepend search_terms if present."""
    fmt = entry.get('format', 'text')

    if fmt in ('text', 'string'):
        text = chunk_text_entry(entry)
    elif fmt in ('structured', 'object'):
        text = chunk_structured_entry(entry)
    else:
        print(f"  Warning: unknown format '{fmt}' for entry '{entry.get('id')}', treating as text")
        text = chunk_text_entry(entry)

    search_terms = entry.get('search_terms', '')
    if search_terms:
        text = f"Search terms: {search_terms}\n\n{text}"

    return text


def entries_to_chunks(entries: list[dict], bot_id: str) -> list[dict]:
    """
    Convert a list of raw YAML entries into chunk dicts.
    Pure function — no I/O. Used by both local and S3 paths.
    """
    chunks = []
    for entry in entries:
        text = chunk_entry(entry)
        if not text or not text.strip():
            print(f"  Skipping empty entry: {entry.get('id')}")
            continue
        chunks.append({
            'id':       entry['id'],
            'bot_id':   bot_id,
            'category': entry.get('category', 'General'),
            'heading':  entry.get('heading', ''),
            'text':     text,
        })
    return chunks


# ---------------------------------------------------------------------------
# S3 / Lambda entry point  (takes a pre-parsed YAML dict for one file)
# ---------------------------------------------------------------------------

def chunk_yaml_content(data: dict, bot_id: str) -> list[dict]:
    """
    Process a single already-parsed YAML file's contents into chunks.

    Args:
        data:   Result of yaml.safe_load() for one data file
        bot_id: The bot this data belongs to

    Returns:
        List of chunk dicts {id, bot_id, category, heading, text}
    """
    entries = data.get('entries', [])
    return entries_to_chunks(entries, bot_id)


# ---------------------------------------------------------------------------
# Local filesystem entry point
# ---------------------------------------------------------------------------

def get_bot_data_path(bot_id: str) -> Path:
    return Path(__file__).parent.parent / 'bots' / bot_id / 'data'


def load_yaml_files(data_path: Path) -> list[dict]:
    """Load all .yml files from a bot's local data folder, return combined entries."""
    all_entries = []

    if not data_path.exists():
        print(f"  Warning: data folder not found at {data_path}")
        return all_entries

    yml_files = sorted(data_path.glob('*.yml'))
    if not yml_files:
        print(f"  Warning: no .yml files found in {data_path}")
        return all_entries

    for yml_file in yml_files:
        print(f"  Reading {yml_file.name}...")
        with open(yml_file, 'r') as f:
            data = yaml.safe_load(f)
        entries = data.get('entries', [])
        all_entries.extend(entries)
        print(f"    Found {len(entries)} entries")

    return all_entries


def load_bot_data(bot_id: str) -> list[dict]:
    """
    Local dev entry point. Load and chunk all YAML data for a bot.

    Returns:
        List of chunk dicts ready for embedding: {id, bot_id, category, heading, text}
    """
    print(f"Loading data for bot: {bot_id}")
    data_path = get_bot_data_path(bot_id)
    entries   = load_yaml_files(data_path)

    if not entries:
        print(f"  No entries found for bot '{bot_id}'")
        return []

    chunks = entries_to_chunks(entries, bot_id)
    print(f"  Produced {len(chunks)} chunks for bot '{bot_id}'")
    return chunks
