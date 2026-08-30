"""노래방 일괄 등록 입력 파싱 검증. DB 불필요."""

import pytest

from stelline.database.karaoke_seed import KNOWN_MEMBERS, MEMBER_SEED, SeedError, load_seed_text, parse_rows


def test_header_line_allows_any_column_order():
    rows, warnings = parse_rows("가수\tTJ\t곡명\tKY\n아이리 칸나\t111\t테스트곡\t222")
    assert warnings == []
    assert rows == [{
        "title": "테스트곡", "title_alt": None, "artist": "아이리 칸나", "members": None,
        "section": "solo", "category": "cover", "tj": "111", "ky": "222",
        "release_date": None, "note": None, "sort_order": None,
    }]


def test_without_header_assumes_title_artist_tj_ky():
    rows, _ = parse_rows("테스트곡\t아이리 칸나\t111\t222")
    assert (rows[0]["title"], rows[0]["artist"], rows[0]["tj"], rows[0]["ky"]) == ("테스트곡", "아이리 칸나", "111", "222")


def test_comma_separated_input_is_accepted():
    rows, _ = parse_rows("테스트곡,아이리 칸나,111,222")
    assert rows[0]["ky"] == "222"


@pytest.mark.parametrize("mark", ["-", "", "없음", "–"])
def test_missing_number_marks_become_null(mark):
    rows, _ = parse_rows(f"테스트곡\t아이리 칸나\t{mark}\t222")
    assert rows[0]["tj"] is None


def test_korean_section_and_category_labels_are_translated():
    rows, _ = parse_rows("곡명\t가수\t구분\t종류\n테스트곡\t스텔라이브\t단체\t오리지널")
    assert rows[0]["section"] == "group"
    assert rows[0]["category"] == "original"


def test_english_section_and_category_values_are_accepted():
    rows, _ = parse_rows("곡명\t가수\tsection\tcategory\n테스트곡\t스텔라이브\tunit\tcover")
    assert (rows[0]["section"], rows[0]["category"]) == ("unit", "cover")


def test_members_are_normalized_and_deduplicated():
    rows, warnings = parse_rows("곡명\t가수\t멤버\n테스트곡\t유닛\t아이리 칸나, 아이리 칸나 / 유즈하 리코")
    assert rows[0]["members"] == "아이리 칸나, 유즈하 리코"
    assert warnings == []


def test_unknown_member_is_kept_but_warned():
    rows, warnings = parse_rows("곡명\t가수\t멤버\n테스트곡\t콜라보\t아이리 칸나, 외부 게스트")
    assert rows[0]["members"] == "아이리 칸나, 외부 게스트"
    assert any("외부 게스트" in warning for warning in warnings)


def test_duplicate_rows_are_warned():
    _, warnings = parse_rows("테스트곡\t칸나\t1\t2\n테스트곡\t칸나\t3\t4")
    assert any("중복" in warning for warning in warnings)


@pytest.mark.parametrize("text,message", [
    ("", "입력한 내용이 없습니다"),
    ("곡명\t가수\tTJ\tKY", "데이터 줄이 없습니다"),
    ("테스트곡\t칸나\tABC\t2", "숫자만"),
    ("\t칸나\t1\t2", "곡명이 비어"),
    ("테스트곡\t\t1\t2", "가수가 비어"),
    ("곡명\t가수\t구분\n테스트곡\t칸나\t알수없음", "구분 값"),
    ("곡명\t가수\t종류\n테스트곡\t칸나\t알수없음", "종류 값"),
    ("곡명\t가수\t순서\n테스트곡\t칸나\t첫번째", "순서는 정수"),
])
def test_invalid_input_raises_seed_error(text, message):
    with pytest.raises(SeedError) as error:
        parse_rows(text)
    assert message in str(error.value)


def test_overlong_title_is_rejected():
    with pytest.raises(SeedError):
        parse_rows(f"{'가' * 256}\t칸나\t1\t2")


def test_bundled_seed_file_parses_cleanly():
    rows, warnings = parse_rows(load_seed_text())
    assert len(rows) > 200
    assert warnings == []
    assert all(row["title"] and row["artist"] for row in rows)
    assert all(row["tj"] is None or row["tj"].isdigit() for row in rows)
    assert all(row["ky"] is None or row["ky"].isdigit() for row in rows)
    assert all(row["section"] in {"group", "unit", "collab", "gift", "solo"} for row in rows)
    assert all(row["category"] in {"original", "cover"} for row in rows)
    # 시드는 순서를 직접 지정해 "최신순" 정렬이 원본 글과 같은 차례를 유지한다.
    assert [row["sort_order"] for row in rows] == sorted(row["sort_order"] for row in rows)


# ---------- 발매일 ----------

@pytest.mark.parametrize("text,expected", [
    ("곡명\t가수\t발매일\n곡\t칸나\t2026-05-08", "2026-05-08"),
    ("곡명\t가수\t발매일\n곡\t칸나\t2026.05.08", "2026-05-08"),
    ("곡명\t가수\t발매일\n곡\t칸나\t2026/5/8", "2026-05-08"),
    ("곡명\t가수\t발매일\n곡\t칸나\t", None),
])
def test_release_date_is_normalized(text, expected):
    rows, _ = parse_rows(text)
    assert rows[0]["release_date"] == expected


@pytest.mark.parametrize("value", ["2026년 5월", "20260508", "2026-13-01"])
def test_invalid_release_date_is_rejected(value):
    with pytest.raises(SeedError):
        parse_rows(f"곡명\t가수\t발매일\n곡\t칸나\t{value}")


# ---------- 시드 데이터의 사실 관계 ----------

def _seed_rows():
    rows, _ = parse_rows(load_seed_text())
    return rows


def _member_facts():
    return {row[0]: {"debut": row[3], "graduated": row[4]} for row in MEMBER_SEED}


def test_member_master_reflects_unit_history():
    facts = {row[0]: row for row in MEMBER_SEED}
    # 아이리 칸나는 미스틱 소속이었고 2024-12-02에 졸업했다.
    # 졸업일은 곡의 참여 멤버를 검증하는 데만 쓰고 화면에는 표시하지 않는다.
    assert facts["아이리 칸나"][1] == "MYSTIC"
    assert facts["아이리 칸나"][4] == "2024-12-02"
    # 아야츠노 유니는 미스틱에서 에버리스로 옮겼으므로 두 유닛 모두에 걸쳐 있다.
    assert facts["아야츠노 유니"][1] == "EVERYS"
    assert facts["아야츠노 유니"][2] == "MYSTIC"
    # 사키하네 후야는 개편 때 합류했다.
    assert facts["사키하네 후야"][3] == "2025-09-20"


def test_seed_members_were_active_when_the_song_was_released():
    """발매일이 적힌 곡에는 그 시점에 활동 중이던 멤버만 있어야 한다.

    졸업한 멤버를 이후 곡에 넣거나, 아직 데뷔하지 않은 멤버를 과거 곡에 넣는 실수를 막는다.
    """
    facts = _member_facts()
    problems = []
    for row in _seed_rows():
        released = row["release_date"]
        if not released or not row["members"]:
            continue
        for name in row["members"].split(", "):
            fact = facts.get(name)
            if fact is None:
                continue
            if fact["debut"] and released < fact["debut"]:
                problems.append(f"{row['title']}({released}): {name}은 {fact['debut']} 데뷔")
            if fact["graduated"] and released > fact["graduated"]:
                problems.append(f"{row['title']}({released}): {name}은 {fact['graduated']} 졸업")
    assert not problems, problems


def test_graduated_member_is_absent_from_later_group_songs():
    later = [row for row in _seed_rows()
             if row["section"] == "group" and row["release_date"] and row["release_date"] > "2024-12-02"]
    assert later, "졸업 이후 발매된 단체곡이 시드에 있어야 이 검사가 의미를 가진다"
    assert all("아이리 칸나" not in (row["members"] or "") for row in later)


def test_first_single_credits_only_the_six_members_active_in_2024():
    singles = [row for row in _seed_rows() if row["title"] in {"Milky Way", "Starry Way"}]
    assert len(singles) == 2
    for row in singles:
        assert row["release_date"] == "2024-02-21"
        assert row["members"].split(", ") == [
            "아이리 칸나", "아야츠노 유니", "시라유키 히나", "네네코 마시로", "아카네 리제", "아라하시 타비",
        ]



def test_tooniverse_medley_is_not_in_the_seed():
    """투니버스 메들리는 원본 표의 번호가 한 칸씩 밀려 있어 시드에서 제외했다."""
    rows = _seed_rows()
    assert all("메들리" not in row["title"] for row in rows)
    assert all("메들리" not in (row["note"] or "") for row in rows)


def test_every_member_name_in_the_seed_is_registered():
    """오타 난 멤버 이름이 조용히 섞여 들어가지 않도록 막는다."""
    unknown = sorted({
        name
        for row in _seed_rows()
        for name in (row["members"] or "").split(", ")
        if name and name not in KNOWN_MEMBERS
    })
    assert not unknown, unknown


def test_star_trail_ep_tracks_credit_the_members_who_sang_them():
    tracks = {row["title"]: row for row in _seed_rows() if row["note"] == "1st EP"}
    assert set(tracks) == {"STAR TRAIL (스타트레일)", "별을 쫓던 빛에게", "히로인이 되고싶어"}
    for row in tracks.values():
        assert row["release_date"] == "2026-05-08"
    # 트랙마다 참여 멤버가 다르다. 타이틀곡 크레딧을 앨범 전체에 적용하면 안 된다.
    assert "사키하네 후야" in tracks["별을 쫓던 빛에게"]["members"]
