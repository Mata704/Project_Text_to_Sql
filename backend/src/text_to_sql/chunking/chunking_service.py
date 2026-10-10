import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import tiktoken

from text_to_sql.chunking.chunking_model import ChunkingConfig, DocumentChunk
from text_to_sql.chunking.constants import (
    HEADING_PATTERN,
    SENTENCE_PATTERN,
    TABLE_SEPARATOR_PATTERN,
    TOKENIZER_ENCODING,
)


@dataclass(frozen=True)
class _TextUnit:
    content: str
    start_line: int
    end_line: int


class ChunkingService:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()
        self._tokenizer = tiktoken.get_encoding(TOKENIZER_ENCODING)

    def chunk_file(self, path: Path) -> list[DocumentChunk]:
        if not path.is_file():
            raise FileNotFoundError(f"Markdown document does not exist: {path}")
        if path.suffix.casefold() != ".md":
            raise ValueError(f"Only Markdown documents are supported: {path}")

        content = path.read_text(encoding="utf-8")
        return self.chunk_markdown(source=path.name, content=content)

    def chunk_directory(self, path: Path) -> list[DocumentChunk]:
        if not path.is_dir():
            raise NotADirectoryError(f"Documentation directory does not exist: {path}")

        chunks: list[DocumentChunk] = []
        for document_path in sorted(path.rglob("*.md")):
            relative_source = document_path.relative_to(path).as_posix()
            chunks.extend(
                self.chunk_markdown(
                    source=relative_source,
                    content=document_path.read_text(encoding="utf-8"),
                )
            )
        return chunks

    def chunk_markdown(self, source: str, content: str) -> list[DocumentChunk]:
        source = source.strip()
        if not source:
            raise ValueError("The Markdown document source cannot be empty.")
        if not content.strip():
            raise ValueError(f"The Markdown document is empty: {source}")

        document_title = self._document_title(source, content)
        raw_chunks: list[tuple[str, tuple[str, ...], int, int]] = []
        lines = content.splitlines()
        for section_path, section_lines in self._sections(lines):
            raw_chunks.extend(
                (chunk_content, section_path, start_line, end_line)
                for chunk_content, start_line, end_line in self._chunk_section(
                    section_path,
                    section_lines,
                )
            )

        total_chunks = len(raw_chunks)
        chunks: list[DocumentChunk] = []
        for chunk_index, (chunk_content, section_path, start_line, end_line) in enumerate(
            raw_chunks
        ):
            digest = hashlib.sha256(
                f"{source}\0{chunk_index}\0{chunk_content}".encode()
            ).hexdigest()
            chunks.append(
                DocumentChunk(
                    chunk_id=digest,
                    content=chunk_content,
                    source=source,
                    document_title=document_title,
                    section_path=section_path,
                    chunk_index=chunk_index,
                    total_chunks=total_chunks,
                    start_line=start_line,
                    end_line=end_line,
                    token_count=len(self._tokenizer.encode(chunk_content)),
                )
            )
        return chunks

    def _document_title(self, source: str, content: str) -> str:
        in_fenced_block = False
        for line in content.splitlines():
            if line.lstrip().startswith("```"):
                in_fenced_block = not in_fenced_block
                continue
            if in_fenced_block:
                continue
            heading_match = HEADING_PATTERN.match(line)
            if heading_match and len(heading_match.group(1)) == 1:
                return heading_match.group(2).strip()
        return Path(source).stem

    def _sections(
        self,
        lines: Sequence[str],
    ) -> Iterable[tuple[tuple[str, ...], list[tuple[int, str]]]]:
        heading_stack: list[tuple[int, str]] = []
        section_lines: list[tuple[int, str]] = []
        in_fenced_block = False

        for line_number, line in enumerate(lines, start=1):
            if line.lstrip().startswith("```"):
                in_fenced_block = not in_fenced_block

            heading_match = None if in_fenced_block else HEADING_PATTERN.match(line)
            if heading_match is not None:
                if section_lines:
                    yield tuple(title for _, title in heading_stack), section_lines
                    section_lines = []

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
            else:
                section_lines.append((line_number, line))

        if section_lines:
            yield tuple(title for _, title in heading_stack), section_lines

    def _chunk_section(
        self,
        section_path: tuple[str, ...],
        lines: Sequence[tuple[int, str]],
    ) -> list[tuple[str, int, int]]:
        heading = self._heading_prefix(section_path)
        content_budget = self.config.max_chunk_chars
        if heading:
            content_budget -= len(heading) + 2
        if content_budget < 1:
            raise ValueError("Section headings exceed max_chunk_chars.")

        blocks = self._blocks(lines)
        units = [unit for block in blocks for unit in self._split_block(block, content_budget)]
        if not units:
            return []

        chunks: list[tuple[str, int, int]] = []
        current_units: list[_TextUnit] = []
        current_content = heading
        has_new_units = False

        for unit in units:
            candidate = self._join(current_content, unit.content)
            if len(candidate) <= self.config.max_chunk_chars:
                current_units.append(unit)
                current_content = candidate
                has_new_units = True
                continue

            if has_new_units:
                chunks.append(self._make_chunk(current_content, current_units))
                current_units = self._overlap_units(current_units)
                current_content = heading
                for overlap_unit in current_units:
                    current_content = self._join(current_content, overlap_unit.content)
                has_new_units = False
            else:
                current_units = []
                current_content = heading

            candidate = self._join(current_content, unit.content)
            if len(candidate) > self.config.max_chunk_chars and current_units:
                current_units = []
                current_content = heading
                candidate = self._join(current_content, unit.content)
            if len(candidate) > self.config.max_chunk_chars:
                raise ValueError("A Markdown block could not be split within max_chunk_chars.")
            current_units.append(unit)
            current_content = candidate
            has_new_units = True

        if has_new_units:
            chunks.append(self._make_chunk(current_content, current_units))
        return chunks

    def _make_chunk(self, content: str, units: Sequence[_TextUnit]) -> tuple[str, int, int]:
        return (
            content,
            min(unit.start_line for unit in units),
            max(unit.end_line for unit in units),
        )

    def _split_block(
        self,
        block: Sequence[tuple[int, str]],
        max_chars: int,
    ) -> list[_TextUnit]:
        text = "\n".join(line for _, line in block).strip()
        start_line = block[0][0]
        end_line = block[-1][0]
        if len(text) <= max_chars:
            return [_TextUnit(text, start_line, end_line)]

        lines = [line for _, line in block]
        if self._is_table(lines):
            return self._split_table(block, max_chars)

        if text.lstrip().startswith("```"):
            return self._split_fenced_block(block, max_chars)

        sentences = [
            sentence.strip() for sentence in SENTENCE_PATTERN.split(text) if sentence.strip()
        ]
        return [
            unit
            for sentence in sentences
            for unit in self._split_oversized_text(sentence, start_line, end_line, max_chars)
        ]

    def _split_table(
        self,
        lines: Sequence[tuple[int, str]],
        max_chars: int,
    ) -> list[_TextUnit]:
        table_lines = [line for _, line in lines]
        if len(table_lines) < 2 or not TABLE_SEPARATOR_PATTERN.match(table_lines[1]):
            return self._split_oversized_text(
                "\n".join(table_lines),
                lines[0][0],
                lines[-1][0],
                max_chars,
            )

        header = "\n".join(table_lines[:2])
        header_start = lines[0][0]
        header_end = lines[1][0]
        units: list[_TextUnit] = []
        current_rows: list[tuple[int, str]] = []
        for line_number, row in lines[2:]:
            candidate = "\n".join([header, *(text for _, text in current_rows), row])
            if len(candidate) <= max_chars:
                current_rows.append((line_number, row))
                continue
            if current_rows:
                units.append(
                    _TextUnit(
                        "\n".join([header, *(text for _, text in current_rows)]),
                        header_start,
                        current_rows[-1][0],
                    )
                )
                current_rows = []
            row_with_header = f"{header}\n{row}"
            if len(row_with_header) > max_chars:
                units.extend(
                    self._split_oversized_text(
                        row_with_header,
                        header_start,
                        line_number,
                        max_chars,
                    )
                )
            else:
                current_rows.append((line_number, row))
        if current_rows:
            units.append(
                _TextUnit(
                    "\n".join([header, *(text for _, text in current_rows)]),
                    header_start,
                    current_rows[-1][0],
                )
            )
        elif not units and len(lines) >= 2:
            units.append(_TextUnit(header, header_start, header_end))
        return units

    def _split_fenced_block(
        self,
        lines: Sequence[tuple[int, str]],
        max_chars: int,
    ) -> list[_TextUnit]:
        fence = lines[0][1].strip()
        closing_fence = "```"
        body = list(lines[1:-1]) if lines[-1][1].strip().startswith("```") else list(lines[1:])
        pieces: list[_TextUnit] = []
        current_lines: list[tuple[int, str]] = []

        for line_number, line in body:
            candidate = "\n".join(
                [fence, *(text for _, text in current_lines), line, closing_fence]
            )
            if len(candidate) <= max_chars:
                current_lines.append((line_number, line))
                continue
            if current_lines:
                pieces.append(
                    _TextUnit(
                        "\n".join([fence, *(text for _, text in current_lines), closing_fence]),
                        current_lines[0][0] - 1,
                        current_lines[-1][0],
                    )
                )
                current_lines = []
            single_line = "\n".join([fence, line, closing_fence])
            if len(single_line) > max_chars:
                pieces.extend(
                    self._split_oversized_text(
                        single_line,
                        line_number,
                        line_number,
                        max_chars,
                    )
                )
            else:
                current_lines.append((line_number, line))

        if current_lines:
            pieces.append(
                _TextUnit(
                    "\n".join([fence, *(text for _, text in current_lines), closing_fence]),
                    current_lines[0][0] - 1,
                    current_lines[-1][0] + 1,
                )
            )
        return pieces

    def _split_oversized_text(
        self,
        text: str,
        start_line: int,
        end_line: int,
        max_chars: int,
    ) -> list[_TextUnit]:
        words = text.split()
        pieces: list[_TextUnit] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                pieces.append(_TextUnit(current, start_line, end_line))
            if len(word) > max_chars:
                raise ValueError("A Markdown word exceeds max_chunk_chars.")
            current = word
        if current:
            pieces.append(_TextUnit(current, start_line, end_line))
        return pieces

    def _blocks(self, lines: Sequence[tuple[int, str]]) -> list[list[tuple[int, str]]]:
        blocks: list[list[tuple[int, str]]] = []
        current_lines: list[tuple[int, str]] = []
        in_fenced_block = False
        for line_number, line in lines:
            if line.lstrip().startswith("```"):
                in_fenced_block = not in_fenced_block
            if not line.strip() and not in_fenced_block:
                if current_lines:
                    blocks.append(current_lines)
                    current_lines = []
            else:
                current_lines.append((line_number, line))
        if current_lines:
            blocks.append(current_lines)
        return blocks

    def _is_table(self, lines: Sequence[str]) -> bool:
        return (
            len(lines) >= 2
            and TABLE_SEPARATOR_PATTERN.match(lines[1]) is not None
            and all("|" in line for line in lines)
        )

    def _overlap_units(self, units: Sequence[_TextUnit]) -> list[_TextUnit]:
        overlap_units: list[_TextUnit] = []
        overlap_length = 0
        for unit in reversed(units):
            unit_length = len(unit.content) + (2 if overlap_units else 0)
            if overlap_units and overlap_length + unit_length > self.config.overlap_chars:
                break
            overlap_units.insert(0, unit)
            overlap_length += unit_length
            if overlap_length >= self.config.overlap_chars:
                break
        return overlap_units

    def _heading_prefix(self, section_path: tuple[str, ...]) -> str:
        return "\n".join(f"# {heading}" for heading in section_path)

    def _join(self, current: str, unit: str) -> str:
        if not current:
            return unit
        if not unit:
            return current
        return f"{current}\n\n{unit}"
