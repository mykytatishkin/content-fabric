"""Tests for DLE ingestion logic (xfields parser and client)."""

import pytest
from shared.ingestion.dle.xfields_parser import parse_xfields, get_normalized_fields

def test_parse_xfields_simple():
    s = "author|John Doe||cover|cover.jpg"
    res = parse_xfields(s)
    assert res == {"author": "John Doe", "cover": "cover.jpg"}

def test_parse_xfields_empty():
    assert parse_xfields("") == {}
    assert parse_xfields(None) == {}

def test_parse_xfields_complex():
    s = "namebook|Book Title||avtor|Writer||tr_id|12345||chtec|Narrator"
    res = parse_xfields(s)
    assert res["namebook"] == "Book Title"
    assert res["avtor"] == "Writer"
    assert res["tr_id"] == "12345"
    assert res["chtec"] == "Narrator"

def test_normalize_fields_variants():
    # Test variant 1: author + cover
    x1 = {"author": "Author 1", "cover": "c1.jpg", "namebook": "Book 1"}
    n1 = get_normalized_fields(x1, "source1")
    assert n1["author"] == "Author 1"
    assert n1["cover"] == "c1.jpg"
    assert n1["book_name"] == "Book 1"

    # Test variant 2: avtor + wallpaper + chtec (slushat_knigi_com style)
    x2 = {"avtor": "Author 2", "wallpaper": "c2.jpg", "chtec": "Narrator 2"}
    n2 = get_normalized_fields(x2, "slushat_knigi_com")
    assert n2["author"] == "Author 2"
    assert n2["cover"] == "c2.jpg"
    assert n2["narrator"] == "Narrator 2"

    # Test variant 3: tr_cover + tr_id + tr_cnt_p (audiokniga_one style)
    x3 = {"avtor": "Author 3", "tr_cover": "c3.jpg", "tr_id": "999", "tr_cnt_p": "10"}
    n3 = get_normalized_fields(x3, "audiokniga_one_com")
    assert n3["author"] == "Author 3"
    assert n3["cover"] == "c3.jpg"
    assert n3["external_id"] == "999"
    assert n3["page_count"] == "10"
