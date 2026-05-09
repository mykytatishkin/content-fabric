"""Unit tests for shared.ingestion.dle.sources — per-source URL builders."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from shared.ingestion.dle import sources as S


class TestImgUrl:
    @pytest.mark.parametrize("inp,expected", [
        (1, "1/"),
        (12, "1/2/"),
        (275374, "2/7/5/3/7/4/"),
        ("115455", "1/1/5/4/5/5/"),
        (0, "0/"),
    ])
    def test_imgurl_splits_each_digit(self, inp, expected):
        assert S.imgurl(inp) == expected


class TestCoverBuilders:
    def test_bazaknig_uses_redirectto_with_baza_knig_info_id(self):
        post = {"xfields_parsed": {"baza_knig_info_id": "41790", "cover": "book.jpg"}}
        url, ref = S.build_cover_url("bazaknig_net", post)
        assert url == f"{S.CDN_REDIRECTTO}/s01/4/1/7/9/0/book.jpg"
        assert ref == "https://cdn.bazaknig.net"

    def test_bazaknig_returns_none_without_required_fields(self):
        assert S.build_cover_url("bazaknig_net", {"xfields_parsed": {"cover": "x.jpg"}}) == (None, "")
        assert S.build_cover_url("bazaknig_net", {"xfields_parsed": {"baza_knig_info_id": "1"}}) == (None, "")

    def test_club_books_uses_s20_slot_with_tr_id(self):
        url, ref = S.build_cover_url("club_books_ru", {"xfields_parsed": {"tr_id": "313087"}})
        assert url == f"{S.CDN_REDIRECTTO}/s20/3/1/3/0/8/7/313087.jpg"
        assert ref == S.CDN_REDIRECTTO

    def test_knigi_online_club_same_pattern_as_club_books(self):
        url, _ = S.build_cover_url("knigi_online_club", {"xfields_parsed": {"tr_id": "386262"}})
        assert url == f"{S.CDN_REDIRECTTO}/s20/3/8/6/2/6/2/386262.jpg"

    def test_books_online_uses_cdn_my_library_via_wallpaper(self):
        url, ref = S.build_cover_url("books_online_info", {"xfields_parsed": {"wallpaper": "books/7/7.jpg"}})
        assert url == f"{S.CDN_MY_LIBRARY}/books/7/7.jpg"
        assert ref == S.CDN_MY_LIBRARY

    def test_books_online_falls_back_to_cover_field(self):
        url, _ = S.build_cover_url("books_online_info", {"xfields_parsed": {"cover": "x/y.jpg"}})
        assert url == f"{S.CDN_MY_LIBRARY}/x/y.jpg"

    def test_slushat_uses_public_site_uploads(self):
        url, ref = S.build_cover_url("slushat_knigi_com", {"xfields_parsed": {"cover": "books/70036/70036.jpg"}})
        assert url == "https://slushat-knigi.com/uploads/posts/books/70036/70036.jpg"
        assert ref == "https://slushat-knigi.com/"

    def test_audiokniga_one_passes_xfields_cover_through_redirectto(self):
        url, _ = S.build_cover_url("audiokniga_one_com", {"xfields_parsed": {"cover": "abc/def.jpg"}})
        assert url == f"{S.CDN_REDIRECTTO}/abc/def.jpg"

    def test_audiokniga_one_skips_no_cover_placeholder(self):
        url, _ = S.build_cover_url("audiokniga_one_com", {"xfields_parsed": {"cover": "images/no-cover.jpg"}})
        assert url is None

    def test_unknown_slug_returns_none(self):
        assert S.build_cover_url("unknown_site", {"xfields_parsed": {}}) == (None, "")

    def test_absolute_cover_url_passthrough(self):
        url, _ = S.build_cover_url(
            "audiokniga_one_com",
            {"xfields_parsed": {"cover": "https://other.cdn/x.jpg"}},
        )
        assert url == "https://other.cdn/x.jpg"


class TestPlaylistFetcher:
    def test_playlist_sources_set_only_audio_book_sites(self):
        assert S.PLAYLIST_SOURCES == {"audiokniga_one_com", "knigi_audio_biz"}

    def test_fetch_playlist_parses_php_regex(self, tmp_path):
        sample_pl = (
            '[{"title":"1","file":"https://cdn/0.mp3"},'
            '{"title":"2","file":"https:\\/\\/cdn\\/1.mp3"}]'
        )

        class Resp:
            text = sample_pl
            status_code = 200
            content = sample_pl.encode()
            def raise_for_status(self): pass

        with patch.object(S.requests, "get", return_value=Resp()):
            mp3s = S.fetch_playlist_mp3s(115455, str(tmp_path))
        assert mp3s == ["https://cdn/0.mp3", "https://cdn/1.mp3"]

    def test_fetch_playlist_returns_none_on_http_error(self, tmp_path):
        class Resp:
            text = ""
            status_code = 500
            def raise_for_status(self): raise RuntimeError("500")

        with patch.object(S.requests, "get", return_value=Resp()):
            assert S.fetch_playlist_mp3s(1, str(tmp_path)) is None

    def test_fetch_playlist_returns_none_when_empty(self, tmp_path):
        class Resp:
            text = "[]"
            status_code = 200
            def raise_for_status(self): pass

        with patch.object(S.requests, "get", return_value=Resp()):
            assert S.fetch_playlist_mp3s(1, str(tmp_path)) is None
