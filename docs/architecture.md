# Architecture — FolderKnowledgeSiteGeneratorForAI

## Module Relationship Diagram

```
                 ┌─────────────┐
                 │   User      │
                 └──┬──────┬───┘
                    │      │
              ┌─────▼──┐ ┌─▼─────────┐
              │  CLI   │ │   GUI      │
              │generate.py│ │ gui.py   │
              └──┬──┬──┘ └──┬────────┘
                 │  │       │
      ┌──────────┘  │       └──────────┐
      │             │                  │
      ▼             ▼                  ▼
┌──────────┐  ┌──────────┐     ┌──────────────┐
│ scanner  │  │ chunker  │     │ ui/app.py    │
│ scanner.py│ │ chunker/ │     │ ui/server.py │
└────┬─────┘  └────┬─────┘     └──────┬───────┘
     │             │                  │
     ▼             │                  │
┌──────────┐       │                  │
│ parser/  │◄──────┘                  │
│ dispatcher│                          │
│ text/pdf │                          │
│ office   │                          │
└────┬─────┘                          │
     │                                │
     ▼                                │
┌─────────────────────────────────────┘
│               │
│  generator/   │
│  portal.py    │
│  templates.py │
└──────┬────────┘
       │
       ▼
  ┌──────────┐
  │ Output   │
  │ HTML/TXT │
  └──────────┘
```

## Data Flow

```
Scan → Parse → Model → Render → Output

1. SCAN (scanner.py)
   walk_files() → yields (full_path, rel_path) for every parseable candidate
   Applies directory/file filtering rules centrally.
   Returns relative paths for stable downstream naming.

2. PARSE (parser/dispatcher.py)
   parse_file() → routes to text/pdf/office parser based on MIME type
   Falls back to extension-based dispatch when python-magic unavailable.
   Returns ParseResult {extract_type, text, metadata} or None.

3. MODEL (generator/portal.py)
   Collects parsed text into PortalDocMeta + PortalDocText lists.
   Applies truncation, keyword extraction, preview generation.
   Builds docs_meta (for index display) and docs_texts (for content blocks).

4. RENDER (generator/templates.py)
   Wraps data into HTML templates (index_page.html, subpage.html).
   Builds file tree HTML, search index JSON, content blocks.

5. OUTPUT
   Single-page portal: one index.html with all content embedded.
   Split portal: index.html + docs/*.html subpages.
   Chunked mode: part_NNN.txt files + index HTML.
   TXT/MD mode: single text file output.
```

## Chunk Mode vs Portal Mode

| Aspect | Chunk Mode | Portal Mode |
|--------|-----------|-------------|
| Output | part_NNN.txt files | HTML pages |
| Splitting | By character count | Per-file subpages |
| Target consumer | LLM context windows | Human + AI in browser |
| File integrity | Preserved (default) or force-split | Always per-file |
| Index | HTML manifest | Searchable index page |
| Purpose | Fit within token limits | Browse + search + AI read |

## Single Page vs Split Mode (Portal)

| Aspect | Single Page | Split Page |
|--------|------------|------------|
| All content in one file | Yes | No (index + subpages) |
| Browser memory | High for large folders | Low (paginated) |
| AI reading | One file for Copilot | Multiple opened tabs |
| Search | DOM-filter + content | Script-filter + subpage links |
| Recommended for | <50 files | >50 files |

## Optional Dependency Strategy

```
Core (always required):
  pdfminer.six, python-docx, python-pptx, openpyxl, chardet

Optional: python-magic (Linux/macOS only)
  → Content-based MIME detection for better parse routing.
  → On Windows: falls back to extension-based dispatch.
  → No functionality lost on Windows; slight reduction in detection accuracy
    for edge-case files (e.g., .txt file with .html extension).

Optional: tkinterdnd2 (all platforms)
  → GUI drag-and-drop support.
  → Without it: Browse and Paste buttons still work.