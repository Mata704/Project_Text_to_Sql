import re

DEFAULT_MAX_CHUNK_CHARS = 2400
DEFAULT_OVERLAP_CHARS = 300
TOKENIZER_ENCODING = "cl100k_base"

HEADING_PATTERN = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*#*\s*$")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
