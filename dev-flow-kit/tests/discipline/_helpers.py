from __future__ import annotations


def extract_section(text: str, heading: str) -> str:
    """Return a top-level markdown section body.

    Only ``## `` headings terminate the section; nested ``### `` headings
    remain part of the section body.
    """

    marker = f"## {heading}"
    section: list[str] = []
    in_section = False
    for line in text.splitlines():
        if line == marker:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            section.append(line)
    return "\n".join(section)


def split_paragraphs(text: str) -> list[str]:
    """Split text on blank-line boundaries and drop empty blocks."""

    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            paragraphs.append("\n".join(current).strip())
            current = []
    if current:
        paragraphs.append("\n".join(current).strip())
    return paragraphs


def parse_markdown_table_rows(text: str) -> list[list[str]]:
    """Parse markdown table data rows with a deliberately small parser."""

    rows: list[list[str]] = []
    seen_separator = False
    for line in text.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not seen_separator:
            if _is_separator_row(cells):
                seen_separator = True
            continue
        rows.append(cells)
    return rows


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(cell and set(cell.replace(":", "")) <= {"-"} for cell in cells)
