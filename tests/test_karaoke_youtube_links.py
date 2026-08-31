"""노래방 곡 <-> 유튜브 영상 짝짓기 로직. DB·네트워크 불필요."""

import unicodedata

from stelline.database import karaoke_youtube_links as links

KNOWN = ["아이리 칸나", "시라유키 히나", "네네코 마시로", "아오쿠모 린", "텐코 시부키", "아라하시 타비", "아카네 리제"]


def _song(title, artist, members="", section="solo", title_alt=None):
    return {"id": 1, "title": title, "title_alt": title_alt, "artist": artist,
            "members": members, "section": section, "category": "cover", "youtube_video_id": None}


def _video(video_id, title):
    return {"video_id": video_id, "title": title}


def test_matches_a_cover_by_title_and_member():
    songs = [_song("KING", "텐코 시부키, 아오쿠모 린", "텐코 시부키, 아오쿠모 린")]
    videos = [_video("aaaaaaaaaaa", "KING (Kanaria) / 텐코 시부키 x 아오쿠모 린 Cover")]

    confirmed, review, missing = links.match_songs(songs, videos, KNOWN)

    assert not review and not missing
    assert confirmed[0]["video"]["video_id"] == "aaaaaaaaaaa"


def test_original_title_in_parentheses_is_matched_on_its_own():
    """'역광 (逆光)'처럼 원제를 괄호로 붙인 곡은 영상 제목에 원제만 있을 때가 많다."""
    songs = [_song("역광 (逆光)", "아이리 칸나", "아이리 칸나")]
    videos = [_video("aaaaaaaaaaa", "逆光 (Ado) from ONE PIECE FILM RED ㅣ 藍璃かんな Cover")]

    confirmed, _, _ = links.match_songs(songs, videos, KNOWN)

    assert confirmed[0]["video"]["video_id"] == "aaaaaaaaaaa"


def test_group_song_is_matched_by_team_name():
    songs = [_song("STAR TRAIL (스타트레일)", "스텔라이브", "시라유키 히나, 아오쿠모 린", section="group")]
    videos = [_video("aaaaaaaaaaa", "스텔라이브 (StelLive) | 'STAR TRAIL'")]

    confirmed, _, _ = links.match_songs(songs, videos, KNOWN)

    assert confirmed[0]["video"]["video_id"] == "aaaaaaaaaaa"


def test_unit_song_is_matched_by_unit_name():
    songs = [_song("유성우", "CLICHÉ(텐코 시부키, 아오쿠모 린)", "텐코 시부키, 아오쿠모 린", section="unit")]
    videos = [_video("aaaaaaaaaaa", "스텔라이브 (StelLive) Cliché | '유성우'")]

    confirmed, _, _ = links.match_songs(songs, videos, KNOWN)

    assert confirmed[0]["video"]["video_id"] == "aaaaaaaaaaa"


def test_same_title_by_another_member_is_not_confirmed():
    """제목만 같고 부른 사람이 다르면 채우지 않는다. 잘못 채우면 발매일까지 틀어진다."""
    songs = [_song("사랑해줘 (愛して)", "시라유키 히나", "시라유키 히나")]
    videos = [_video("aaaaaaaaaaa", "愛して (Kikuo) / 藍璃かんな Cover")]

    confirmed, review, _ = links.match_songs(songs, videos, KNOWN)

    assert not confirmed
    assert review[0]["candidates"][0]["other_members"] is True


def test_two_candidates_are_left_for_a_person_to_pick():
    songs = [_song("최종화 (最終花)", "아이리 칸나", "아이리 칸나")]
    videos = [
        _video("aaaaaaaaaaa", "아이리 칸나(Airi Kanna) | 최종화 (Acoustic Ver.)"),
        _video("bbbbbbbbbbb", "藍璃かんな(Airi Kanna) | '最終花'"),
    ]

    confirmed, review, _ = links.match_songs(songs, videos, KNOWN)

    assert not confirmed
    assert len(review[0]["candidates"]) == 2


def test_title_without_any_person_named_is_left_for_review():
    songs = [_song("Milky Way", "스텔라이브", "시라유키 히나", section="group")]
    videos = [_video("aaaaaaaaaaa", "Milky Way")]

    confirmed, review, _ = links.match_songs(songs, videos, KNOWN)

    assert not confirmed and review


def test_short_english_title_does_not_match_a_longer_word():
    """'ray'가 'Gray'에 걸리면 엉뚱한 영상이 붙는다."""
    songs = [_song("ray", "시라유키 히나", "시라유키 히나")]
    videos = [_video("aaaaaaaaaaa", "Grayscale / 시라유키 히나 Cover")]

    confirmed, review, missing = links.match_songs(songs, videos, KNOWN)

    assert not confirmed and not review
    assert missing[0]["title"] == "ray"


def test_decomposed_hangul_in_a_video_title_still_matches():
    """유튜브 제목에는 자모가 분리된 한글이 섞여 있다."""
    raw = unicodedata.normalize("NFD", "SODA POP - 아라하시 타비 Cover")
    assert raw != "SODA POP - 아라하시 타비 Cover"
    songs = [_song("SODA POP", "아라하시 타비", "아라하시 타비")]

    confirmed, _, _ = links.match_songs(songs, [_video("aaaaaaaaaaa", raw)], KNOWN)

    assert confirmed[0]["video"]["video_id"] == "aaaaaaaaaaa"


def test_song_with_no_video_is_reported_as_missing():
    songs = [_song("아무도 안 부른 곡", "아이리 칸나", "아이리 칸나")]

    confirmed, review, missing = links.match_songs(songs, [_video("aaaaaaaaaaa", "다른 곡 Cover")], KNOWN)

    assert not confirmed and not review
    assert missing[0]["title"] == "아무도 안 부른 곡"


def test_report_lines_can_be_pasted_into_the_admin_form():
    songs = [_song("KING", "텐코 시부키", "텐코 시부키")]
    videos = [_video("aaaaaaaaaaa", "KING / 텐코 시부키 Cover")]
    confirmed, review, missing = links.match_songs(songs, videos, KNOWN)

    lines = links.report_lines(confirmed, review, missing)

    assert lines[0].split("\t")[:3] == ["곡명", "가수", "유튜브"]
    assert lines[1].split("\t")[:4] == ["KING", "텐코 시부키", "aaaaaaaaaaa", "확정"]
