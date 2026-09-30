"""Tests for find_references_scopus.core.scimago."""

import json

import pytest

from find_references_scopus.core.scimago import (
    build_issn_index,
    clear_cache,
    load_journals,
    normalize_issn,
    parse_journal,
    split_issns,
)


@pytest.fixture(autouse=True)
def _clear_scimago_cache():
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------- #
# normalize_issn / split_issns
# ---------------------------------------------------------------------- #

def test_normalize_issn_accepts_hyphenated():
    assert normalize_issn("0007-9235") == "0007-9235"


def test_normalize_issn_accepts_no_hyphen():
    assert normalize_issn("00079235") == "0007-9235"


def test_normalize_issn_uppercases_x_check_digit():
    assert normalize_issn("1234-567x") == "1234-567X"


def test_normalize_issn_rejects_garbage():
    assert normalize_issn("not-an-issn") == ""
    assert normalize_issn("") == ""
    assert normalize_issn(None) == ""


def test_split_issns_from_csv_string():
    assert split_issns("1234-5678, 9876-5432") == ["1234-5678", "9876-5432"]


def test_split_issns_drops_invalid_tokens():
    assert split_issns("1234-5678, garbage, 9876-5432") == ["1234-5678", "9876-5432"]


def test_split_issns_from_list_dedupes():
    assert split_issns(["1234-5678", "1234-5678", "9876-5432"]) == ["1234-5678", "9876-5432"]


def test_split_issns_none_is_empty():
    assert split_issns(None) == []


# ---------------------------------------------------------------------- #
# parse_journal
# ---------------------------------------------------------------------- #

def test_parse_journal_collects_both_issns():
    raw = {"journal": "Nature", "issn_print": "0028-0836", "issn_electronic": "1476-4687", "quartile": "Q1"}
    j = parse_journal(raw)
    assert j.title == "Nature"
    assert set(j.issns) == {"0028-0836", "1476-4687"}
    assert j.quartile == "Q1"


def test_parse_journal_handles_swapped_or_single_issn():
    """SCImago's print/electronic labels are unreliable; findref must not depend on them."""
    raw = {"journal": "Solo ISSN Journal", "issn_electronic": "1234-5678", "issn_print": ""}
    j = parse_journal(raw)
    assert j.issns == ("1234-5678",)


def test_parse_journal_accepts_title_key():
    j = parse_journal({"title": "Old Style", "Issn": "1234-5678"})
    assert j.title == "Old Style"
    assert j.issns == ("1234-5678",)


def test_parse_journal_normalizes_quartile_case():
    j = parse_journal({"journal": "X", "quartile": "q2"})
    assert j.quartile == "Q2"


# ---------------------------------------------------------------------- #
# load_journals
# ---------------------------------------------------------------------- #

def test_load_journals_list_format(tmp_path):
    data = [
        {"journal": "A", "issn_electronic": "1111-1111", "quartile": "Q1", "subject_area": "Medicine"},
        {"journal": "B", "issn_print": "2222-2222", "quartile": "Q3", "subject_area": "Physics"},
    ]
    p = tmp_path / "scimago.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    journals = load_journals(p)
    assert len(journals) == 2
    titles = {j.title for j in journals}
    assert titles == {"A", "B"}
    # The print-only journal must still be loaded with its ISSN.
    b = next(j for j in journals if j.title == "B")
    assert b.issns == ("2222-2222",)


def test_load_journals_dict_by_subject_area(tmp_path):
    data = {
        "Computer Science": [{"journal": "CS Journal", "issn_electronic": "3333-3333"}],
        "Medicine": [{"journal": "Med Journal", "issn_electronic": "4444-4444"}],
    }
    p = tmp_path / "scimago.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    journals = load_journals(p)
    assert len(journals) == 2
    cs = next(j for j in journals if j.title == "CS Journal")
    assert cs.subject_areas == ("Computer Science",)


def test_load_journals_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_journals(tmp_path / "does-not-exist.json")


def test_load_journals_invalid_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_journals(p)


def test_load_journals_is_cached_by_mtime_and_size(tmp_path):
    p = tmp_path / "scimago.json"
    p.write_text(json.dumps([{"journal": "A", "issn_electronic": "1111-1111"}]), encoding="utf-8")

    first = load_journals(p)
    second = load_journals(p)
    assert first is second  # same cached tuple, no re-parse

    # Changing the file (and its mtime/size) must invalidate the cache.
    import time

    time.sleep(0.01)
    p.write_text(json.dumps([{"journal": "A", "issn_electronic": "1111-1111"}, {"journal": "B"}]), encoding="utf-8")
    third = load_journals(p)
    assert len(third) == 2


# ---------------------------------------------------------------------- #
# build_issn_index
# ---------------------------------------------------------------------- #

def test_build_issn_index_covers_print_and_electronic(tmp_path):
    data = [{"journal": "Dual ISSN", "issn_print": "1111-1111", "issn_electronic": "2222-2222"}]
    p = tmp_path / "scimago.json"
    p.write_text(json.dumps(data), encoding="utf-8")

    journals = load_journals(p)
    index = build_issn_index(journals)
    assert index["1111-1111"].title == "Dual ISSN"
    assert index["2222-2222"].title == "Dual ISSN"
