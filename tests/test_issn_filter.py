"""Tests for the IssnFilter module."""

import json
import tempfile
from pathlib import Path

import pytest

from find_references_scopus.core.issn_filter import (
    IssnFilter,
    build_filter_from_defaults,
    list_quartiles,
    list_subject_areas,
)


# ---------------------------------------------------------------------- #
# Test fixtures
# ---------------------------------------------------------------------- #

@pytest.fixture
def sample_scimago_path(tmp_path):
    """Write a small sample SCImago JSON file."""
    data = [
        {"issn_electronic": "1111-1111", "title": "AI Journal", "quartile": "Q1", "subject_area": "Computer Science"},
        {"issn_electronic": "2222-2222", "title": "ML Journal", "quartile": "Q2", "subject_area": "Computer Science"},
        {"issn_electronic": "3333-3333", "title": "Med Journal", "quartile": "Q1", "subject_area": "Medicine"},
        {"issn_electronic": "4444-4444", "title": "Unranked CS", "quartile": "-", "subject_area": "Computer Science"},
        {"issn_electronic": "5555-5555", "title": "Q3 CS", "quartile": "Q3", "subject_area": "Computer Science"},
    ]
    path = tmp_path / "scimago.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------- #
# IssnFilter
# ---------------------------------------------------------------------- #

def test_filter_all_journals(sample_scimago_path):
    """No filter → all 5 ISSNs."""
    f = IssnFilter()
    f.build(sample_scimago_path)
    assert len(f.issns) == 5
    assert f.stats["total_journals"] == 5


def test_filter_by_subject_area(sample_scimago_path):
    """Filter by Computer Science only."""
    f = IssnFilter(subject_areas={"computer science"})
    f.build(sample_scimago_path)
    # 4 Computer Science journals (Q1, Q2, Q3, -)
    assert len(f.issns) == 4
    assert f.stats["after_subject_filter"] == 4


def test_filter_by_quartile(sample_scimago_path):
    """Filter by Q1 only."""
    f = IssnFilter(quartiles={"Q1"})
    f.build(sample_scimago_path)
    # 2 Q1 journals (AI Journal + Med Journal)
    assert len(f.issns) == 2


def test_filter_by_subject_and_quartile(sample_scimago_path):
    """Filter by Computer Science + Q1 only."""
    f = IssnFilter(subject_areas={"computer science"}, quartiles={"Q1"})
    f.build(sample_scimago_path)
    # Only AI Journal matches both
    assert len(f.issns) == 1
    assert f.issns[0] == "1111-1111"


def test_filter_exclude_unranked(sample_scimago_path):
    """Include unranked=False should drop quartile '-' journals."""
    f = IssnFilter(include_unranked=False)
    f.build(sample_scimago_path)
    # 4 journals (drop Unranked CS)
    assert len(f.issns) == 4
    assert "4444-4444" not in f.issns


def test_filter_include_unranked_explicit(sample_scimago_path):
    """include_unranked=True + quartile filter that includes '-' should keep unranked."""
    f = IssnFilter(quartiles={"Q1", "-"}, include_unranked=True)
    f.build(sample_scimago_path)
    # 2 Q1 + 1 unranked = 3
    assert len(f.issns) == 3
    assert "4444-4444" in f.issns


def test_filter_dedup_issns(tmp_path):
    """Some SCImago entries have '1111-1111, 2222-2222' format — should split + dedup."""
    data = [
        {"issn_electronic": "1111-1111, 2222-2222", "title": "Dual", "quartile": "Q1", "subject_area": "X"},
        {"issn_electronic": "1111-1111", "title": "Dup", "quartile": "Q1", "subject_area": "X"},
    ]
    path = tmp_path / "scimago.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    f = IssnFilter()
    f.build(str(path))
    assert len(f.issns) == 2  # dedup


def test_filter_to_batches(sample_scimago_path):
    """to_batches should split ISSNs into chunks of batch_size."""
    f = IssnFilter()
    f.build(sample_scimago_path)
    batches = f.to_batches(batch_size=2)
    assert len(batches) == 3  # ceil(5 / 2) = 3
    assert sum(len(b) for b in batches) == 5


def test_filter_describe(sample_scimago_path):
    """describe() returns a dict with filter state."""
    f = IssnFilter(subject_areas={"Computer Science"}, quartiles={"Q1"})
    f.build(sample_scimago_path)
    d = f.describe()
    assert "subject_areas" in d
    assert "quartiles" in d
    assert d["issn_count"] == 1


def test_filter_is_empty(tmp_path):
    """Empty result if no journals match."""
    data = []
    path = tmp_path / "empty.json"
    path.write_text("[]", encoding="utf-8")
    f = IssnFilter()
    f.build(str(path))
    assert f.is_empty()


def test_filter_handles_dict_by_subject(tmp_path):
    """Should handle SCImago JSON split by subject area (dict format)."""
    data = {
        "Computer Science": [
            {"issn_electronic": "1111-1111", "quartile": "Q1"},
            {"issn_electronic": "2222-2222", "quartile": "Q2"},
        ],
        "Medicine": [
            {"issn_electronic": "3333-3333", "quartile": "Q1"},
        ],
    }
    path = tmp_path / "scimago.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    f = IssnFilter(subject_areas={"medicine"})
    f.build(str(path))
    assert len(f.issns) == 1
    assert f.issns[0] == "3333-3333"


# ---------------------------------------------------------------------- #
# build_filter_from_defaults
# ---------------------------------------------------------------------- #

def test_build_filter_from_defaults_disabled(sample_scimago_path):
    """Should return None when use_issn_filter is False."""
    result = build_filter_from_defaults(
        use_issn_filter=False,
        scimago_path=sample_scimago_path,
    )
    assert result is None


def test_build_filter_from_defaults_enabled(sample_scimago_path):
    """Should build filter when use_issn_filter is True."""
    result = build_filter_from_defaults(
        use_issn_filter=True,
        subject_areas="Computer Science",
        quartiles="Q1,Q2",
        include_unranked=True,
        scimago_path=sample_scimago_path,
    )
    assert result is not None
    assert len(result.issns) == 2  # Q1 + Q2 CS journals


def test_build_filter_from_defaults_all_quartiles(sample_scimago_path):
    """quartiles='all' or empty → all quartiles."""
    result = build_filter_from_defaults(
        use_issn_filter=True,
        quartiles="",
        scimago_path=sample_scimago_path,
    )
    assert result is not None
    assert len(result.issns) == 5  # all 5 journals


# ---------------------------------------------------------------------- #
# list_subject_areas / list_quartiles
# ---------------------------------------------------------------------- #

def test_list_subject_areas(sample_scimago_path):
    areas = list_subject_areas(sample_scimago_path)
    assert "Computer Science" in areas
    assert "Medicine" in areas
    assert len(areas) == 2  # only 2 unique


def test_list_quartiles(sample_scimago_path):
    qs = list_quartiles(sample_scimago_path)
    assert "Q1" in qs
    assert "Q2" in qs
    assert "Q3" in qs
    assert "-" in qs


def test_list_subject_areas_missing_file():
    """Should return empty list for non-existent file."""
    assert list_subject_areas("/nonexistent.json") == []
