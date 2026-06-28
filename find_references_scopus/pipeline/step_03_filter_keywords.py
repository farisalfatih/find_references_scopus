"""Step 03: Filter artikel berdasarkan keyword di abstrak.

Input  : data/02_openalex_raw.json    (output step 02)
Output : data/03_filtered.json

Perilaku:
   - Untuk setiap search_group, evaluasi query boolean terhadap
     abstrak setiap artikel (sama seperti pencarian di step 02)
   - Artikel yang tidak match dengan query group-nya akan dihapus
   - Text dinormalisasi terlebih dahulu (lowercase, normalisasi tanda baca)
     sebelum pencocokan agar lebih akurat
   - Format query yang didukung (parser recursive-descent):
       "quoted phrase"     -> pencocokan substring literal (case-insensitive)
       word                -> pencocokan word-boundary (tidak match substring)
       (a OR b OR c)       -> salah satu harus ada
       X AND Y             -> keduanya harus ada
       X AND NOT Y         -> X harus ada, Y tidak boleh ada
       ((a OR b) AND c) OR d  -> nested parentheses didukung
       "phrase with AND inside"  -> AND di dalam quote literal, tidak di-parse

Setara dengan script lama: filter_keywords_abstrac.py
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from typing import Callable, Dict, List

from ..config import get_config
from ..utils import load_json, print_done, print_header, save_json, setup_logging


DESCRIPTION = "Filter artikel berdasarkan keyword di abstrak (query boolean)"

# Tag untuk find-refs list (M13: auto-derived dari module attribute)
MANUAL_OR_AUTO = "AUTO"


# =============================================================================
# Text normalization
# =============================================================================

def normalize_text(text: str) -> str:
    """Normalisasi teks sebelum pencocokan keyword.

    Lakukan:
      1. Lowercase
      2. Normalisasi Unicode (NFKC) -> tanda baca seperti em-dash jadi regular dash
      3. Ganti berbagai jenis dash/hyphen dengan spasi
      4. Ganti karakter non-alphanumeric (kecuali spasi) dengan spasi
      5. Collapse multiple spaces jadi satu spasi

    Args:
        text: Teks asli (abstract).

    Returns:
        Teks yang sudah dinormalisasi.
    """
    if not text:
        return ""
    # Lowercase
    text = text.lower()
    # NFKC normalization: em-dash -> regular dash, ligatures, dll
    text = unicodedata.normalize("NFKC", text)
    # Ganti dash/hyphen varieties dengan spasi (agar "XG-Boost" match "XGBoost")
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\-]+", " ", text)
    # Hapus karakter non-alphanumeric (kecuali spasi)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_query_term(term: str) -> str:
    """Normalisasi satu term/phrase dari query agar cocok dengan normalize_text.

    Args:
        term: Term dari query (mis. "XGBoost", "Bollinger Bands").

    Returns:
        Term yang sudah dinormalisasi (lowercase, tanpa tanda baca).
    """
    if not term:
        return ""
    term = term.lower()
    term = unicodedata.normalize("NFKC", term)
    term = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\-]+", " ", term)
    term = re.sub(r"[^a-z0-9\s]", " ", term)
    term = re.sub(r"\s+", " ", term).strip()
    return term


# =============================================================================
# Tokenizer untuk query boolean
# =============================================================================

# Token types
TOKEN_QUOTED = "QUOTED"   # "phrase"
TOKEN_WORD = "WORD"       # kata biasa
TOKEN_AND = "AND"
TOKEN_OR = "OR"
TOKEN_NOT = "NOT"
TOKEN_LPAREN = "LPAREN"   # (
TOKEN_RPAREN = "RPAREN"   # )


def _tokenize_query(query_str: str) -> List[tuple]:
    """Tokenize query boolean menjadi list of (type, value) tuples.

    Args:
        query_str: Query boolean, mis. '("XGBoost") AND (MACD OR RSI)'.

    Returns:
        List tuple (TOKEN_TYPE, value). value kosong untuk keyword operator.

    Raises:
        ValueError: jika ada karakter tidak dikenali atau quote tidak tertutup.
    """
    tokens: List[tuple] = []
    i = 0
    n = len(query_str)
    while i < n:
        c = query_str[i]

        # Skip whitespace
        if c.isspace():
            i += 1
            continue

        # Quoted phrase
        if c == '"':
            j = i + 1
            while j < n and query_str[j] != '"':
                j += 1
            if j >= n:
                raise ValueError(
                    f"Query tidak valid: quoted phrase tidak ditutup di posisi {i}."
                )
            phrase = query_str[i + 1:j]
            tokens.append((TOKEN_QUOTED, phrase))
            i = j + 1
            continue

        # Parentheses
        if c == "(":
            tokens.append((TOKEN_LPAREN, ""))
            i += 1
            continue
        if c == ")":
            tokens.append((TOKEN_RPAREN, ""))
            i += 1
            continue

        # Identifier (keyword operator atau kata biasa)
        # Ambil sampai whitespace/paren/quote berikutnya
        j = i
        while j < n and not query_str[j].isspace() and query_str[j] not in '()"':
            j += 1
        word = query_str[i:j]
        upper = word.upper()
        if upper == "AND":
            tokens.append((TOKEN_AND, ""))
        elif upper == "OR":
            tokens.append((TOKEN_OR, ""))
        elif upper == "NOT":
            tokens.append((TOKEN_NOT, ""))
        else:
            tokens.append((TOKEN_WORD, word))
        i = j

    return tokens


# =============================================================================
# Recursive-descent parser
#
# Grammar:
#   expr      := or_expr
#   or_expr   := and_expr (OR and_expr)*
#   and_expr  := not_expr (AND not_expr)*
#   not_expr  := NOT not_expr | primary
#   primary   := QUOTED | WORD | LPAREN expr RPAREN
#
# Menghasilkan AST berupa nested tuple:
#   ("or", left, right)
#   ("and", left, right)
#   ("not", child)
#   ("phrase", value)   # untuk QUOTED
#   ("word", value)     # untuk WORD
# =============================================================================

class _Parser:
    """Parser recursive-descent untuk query boolean."""

    def __init__(self, tokens: List[tuple]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        """Lihat token berikutnya tanpa consume."""
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def _consume(self):
        """Consume dan return token berikutnya."""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self):
        """Parse seluruh expr. Return AST."""
        if not self.tokens:
            return None  # empty query = match all
        ast = self._parse_or()
        if self.pos != len(self.tokens):
            raise ValueError(
                f"Query tidak valid: token tersisa di posisi {self.pos}: "
                f"{self.tokens[self.pos:]}"
            )
        return ast

    def _parse_or(self):
        """or_expr := and_expr (OR and_expr)*"""
        left = self._parse_and()
        while True:
            tok = self._peek()
            if tok is None or tok[0] != TOKEN_OR:
                break
            self._consume()  # consume OR
            right = self._parse_and()
            left = ("or", left, right)
        return left

    def _parse_and(self):
        """and_expr := not_expr (AND not_expr)*"""
        left = self._parse_not()
        while True:
            tok = self._peek()
            if tok is None or tok[0] != TOKEN_AND:
                break
            self._consume()  # consume AND
            right = self._parse_not()
            left = ("and", left, right)
        return left

    def _parse_not(self):
        """not_expr := NOT not_expr | primary"""
        tok = self._peek()
        if tok is not None and tok[0] == TOKEN_NOT:
            self._consume()  # consume NOT
            child = self._parse_not()
            return ("not", child)
        return self._parse_primary()

    def _parse_primary(self):
        """primary := QUOTED | WORD | LPAREN expr RPAREN"""
        tok = self._peek()
        if tok is None:
            raise ValueError("Query tidak valid: expected primary, got end of input.")
        tok_type, tok_val = tok

        if tok_type == TOKEN_QUOTED:
            self._consume()
            return ("phrase", tok_val)
        if tok_type == TOKEN_WORD:
            self._consume()
            return ("word", tok_val)
        if tok_type == TOKEN_LPAREN:
            self._consume()  # consume (
            inner = self._parse_or()
            close_tok = self._peek()
            if close_tok is None or close_tok[0] != TOKEN_RPAREN:
                raise ValueError("Query tidak valid: paren tidak tertutup dengan ).")
            self._consume()  # consume )
            return inner
        raise ValueError(
            f"Query tidak valid: expected quoted/word/(, got {tok_type} at pos {self.pos}."
        )


# =============================================================================
# Evaluator: AST -> callable(text -> bool)
# =============================================================================

def _evaluate_ast(node) -> Callable[[str], bool]:
    """Build evaluator function dari AST.

    Evaluator bekerja pada teks yang SUDAH dinormalisasi (lowercase,
    tanpa tanda baca khusus). Setiap term juga dinormalisasi sebelum
    pencocokan agar konsisten.

    Args:
        node: AST node berupa tuple.

    Returns:
        Fungsi (text: str) -> bool. text sudah dinormalisasi.
    """
    if node is None:
        # Empty query = match all
        return lambda text: True

    node_type = node[0]

    if node_type == "phrase":
        phrase_norm = normalize_query_term(node[1])
        return lambda text: phrase_norm in text

    if node_type == "word":
        word_norm = normalize_query_term(node[1])
        # Gunakan word-boundary yang disesuaikan: hanya alphanumeric
        # sebagai word boundary (karena teks sudah dinormalisasi)
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(word_norm) + r"(?![a-z0-9])", re.IGNORECASE)
        return lambda text: bool(pattern.search(text))

    if node_type == "not":
        child_fn = _evaluate_ast(node[1])
        return lambda text: not child_fn(text)

    if node_type == "and":
        left_fn = _evaluate_ast(node[1])
        right_fn = _evaluate_ast(node[2])
        return lambda text: left_fn(text) and right_fn(text)

    if node_type == "or":
        left_fn = _evaluate_ast(node[1])
        right_fn = _evaluate_ast(node[2])
        return lambda text: left_fn(text) or right_fn(text)

    raise ValueError(f"AST node type tidak dikenal: {node_type}")


# =============================================================================
# Public API
# =============================================================================

def parse_simple_query(query_str: str) -> Callable[[str], bool]:
    """Parse query boolean menjadi fungsi evaluator.

    Sintaks yang didukung (parser recursive-descent):
        - "quoted phrase"     -> pencocokan substring literal (case-insensitive)
        - word                -> pencocokan word-boundary (mis. "eth" TIDAK match "method")
        - (a OR b OR c)       -> salah satu harus ada
        - X AND Y             -> keduanya harus ada
        - X AND NOT Y         -> X harus ada, Y tidak boleh ada
        - ((a OR b) AND c) OR d  -> nested parentheses didukung penuh
        - "phrase with AND inside"  -> AND di dalam quote dianggap literal

    Args:
        query_str: Query boolean, mis. '("XGBoost") AND (MACD OR RSI)'.

    Returns:
        Fungsi yang menerima teks (sudah dinormalisasi) dan mengembalikan True jika match.

    Raises:
        ValueError: jika query tidak valid (paren tidak seimbang, quote tidak
            tertutup, sintaks salah).
    """
    query_str = query_str.strip()
    if not query_str:
        return lambda text: True

    tokens = _tokenize_query(query_str)
    parser = _Parser(tokens)
    ast = parser.parse()
    return _evaluate_ast(ast)


# =============================================================================
# Entry point
# =============================================================================

def run(input_file: str | None = None, output_file: str | None = None) -> int:
    """Entry point step 03.

    Args:
        input_file: Path input JSON. None = pakai config (step_02_openalex_raw).
        output_file: Path output JSON. None = pakai config (step_03_filtered).

    Returns:
        Jumlah total artikel setelah filter.
    """
    log = setup_logging()
    cfg = get_config()
    input_path = input_file or cfg["paths"]["step_02_openalex_raw"]
    output_path = output_file or cfg["paths"]["step_03_filtered"]
    search_groups = cfg.get("search_groups", {})

    print_header("Step 03: Filter Artikel Berdasarkan Keyword")
    log.info(f"Input  : {input_path}")
    log.info(f"Output : {output_path}")

    try:
        data = load_json(input_path)
    except FileNotFoundError:
        log.error(f"File input tidak ditemukan: {input_path}")
        return 0

    filtered_data: Dict[str, List[dict]] = {}
    removal_summary: Dict[str, int] = {}

    for group_name, articles in data.items():
        if group_name not in search_groups:
            log.warning(f"Group '{group_name}' tidak dikenal di config, disalin apa adanya.")
            filtered_data[group_name] = articles
            removal_summary[group_name] = 0
            continue

        query_str = search_groups[group_name].get("query", "")
        try:
            evaluator = parse_simple_query(query_str)
        except ValueError as e:
            log.error(f"Query group '{group_name}' tidak valid: {e}")
            log.error(f"  Query: {query_str}")
            log.error(f"  Group ini dilewati (artikel disalin apa adanya).")
            filtered_data[group_name] = articles
            removal_summary[group_name] = 0
            continue

        kept: List[dict] = []
        removed_count = 0
        for article in articles:
            abstract = article.get("abstract", "") or ""

            # Hanya cocokkan di abstract (sama seperti step 02)
            text = normalize_text(abstract)

            if evaluator(text):
                kept.append(article)
            else:
                removed_count += 1

        filtered_data[group_name] = kept
        removal_summary[group_name] = removed_count
        print(f"  {group_name}: {len(articles)} -> {len(kept)} (hapus {removed_count})")

    save_json(filtered_data, output_path)

    total_kept = sum(len(arts) for arts in filtered_data.values())
    total_removed = sum(removal_summary.values())
    print(f"\nTotal artikel setelah filter: {total_kept}")
    print(f"Total artikel dihapus       : {total_removed}")

    print_done(f"Step 03 selesai — {total_kept} artikel disimpan")
    return total_kept


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register subcommand untuk step 03."""
    parser = subparsers.add_parser(
        "filter",
        help=DESCRIPTION,
        description=DESCRIPTION,
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="File JSON input (default: output step 02 dari config.yaml)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="File JSON output (default: output step 03 dari config.yaml)",
    )
    parser.set_defaults(func=lambda args: run(input_file=args.input, output_file=args.output))