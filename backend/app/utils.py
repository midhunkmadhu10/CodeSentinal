import re
from typing import List


def parse_diff(diff_text: str) -> str:
    """Clean and normalize a diff for analysis.
    Strips excessive whitespace, removes binary diffs, returns clean text."""
    lines = diff_text.split("\n")
    cleaned = []
    for line in lines:
        # Skip binary file diffs
        if line.startswith("Binary files"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks at sentence/paragraph boundaries."""
    if not text.strip():
        return []

    # Split by paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 1 <= chunk_size:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If a single paragraph is too long, split by sentences
            if len(para) > chunk_size:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                temp = ""
                for sent in sentences:
                    if len(temp) + len(sent) + 1 <= chunk_size:
                        temp = (temp + " " + sent).strip()
                    else:
                        if temp:
                            chunks.append(temp)
                        temp = sent
                if temp:
                    current_chunk = temp
                else:
                    current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    # Apply overlap by merging tail of previous chunk into next
    if len(chunks) > 1 and overlap > 0:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                # Prepend the last `overlap` chars from previous chunk
                prev_tail = chunks[i - 1][-overlap:]
                chunk = prev_tail + chunk
            overlapped.append(chunk)
        chunks = overlapped

    return chunks


def extract_code_snippets(diff: str) -> str:
    """Extract only the added/changed lines from a diff for more focused analysis."""
    lines = diff.split("\n")
    added_lines = []
    current_file = ""

    for line in lines:
        # Track file names
        if line.startswith("+++ b/"):
            current_file = line[6:]  # Remove "+++ b/"
        elif line.startswith("--- a/"):
            continue
        # Track added lines (starting with + but not +++)
        elif line.startswith("+") and not line.startswith("+++"):
            added_lines.append(f"{current_file}: {line[1:]}")

    return "\n".join(added_lines)