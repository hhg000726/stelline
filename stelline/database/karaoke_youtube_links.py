"""노래방 곡에 유튜브 영상을 이어 붙인다.

발매일 채우기(`karaoke_release_dates`)는 곡마다 영상 ID가 있어야 동작한다.
공식 재생목록을 훑어 두는 `song_counts` 테이블에 영상 제목과 ID가 이미 쌓여 있으므로,
곡명과 참여 멤버가 맞아떨어지는 영상을 찾아 `karaoke_songs.youtube_video_id`를 채운다.

**곡을 새로 만들지 않는다.** 이미 있는 곡의 빈 칸만 채우고, 애매한 것은 사람이 보도록 남긴다.
영상이 틀리면 발매일도 틀리게 되므로, 근거가 약하면 채우지 않고 '확인 필요'로 분류한다.

    python -m stelline.database.karaoke_youtube_links                # 무엇이 채워질지 미리 본다
    python -m stelline.database.karaoke_youtube_links --apply        # 확정된 것만 저장한다
    python -m stelline.database.karaoke_youtube_links --report links.tsv

운영 DB에 붙지 않는 곳에서는 관리자 페이지를 저장한 HTML을 대신 쓸 수 있다.

    python -m stelline.database.karaoke_youtube_links --from-html "관리자 페이지.html"
"""

import argparse
import io
import logging
import re
import unicodedata

from stelline.database.connection import get_connection

# 영상 제목에 실제로 쓰이는 다른 표기. 한글 전체 이름과 성을 뺀 이름은 자동으로 넣는다.
EXTRA_ALIASES = {
    "아이리 칸나": ("藍璃かんな", "kanna", "airi"),
    "아야츠노 유니": ("yuni", "ayatsuno"),
    "사키하네 후야": ("fuya", "sakihane"),
    "시라유키 히나": ("白雪ひな", "hina", "shirayuki"),
    "네네코 마시로": ("mashiro", "neneko"),
    "아카네 리제": ("lize", "rize", "akane"),
    "아라하시 타비": ("tabi", "arahashi"),
    "텐코 시부키": ("shibuki", "tenko"),
    "아오쿠모 린": ("aokumo",),
    "하나코 나나": ("hanako",),
    "유즈하 리코": ("riko", "yuzuha"),
}

# 단체곡 영상은 멤버 이름 대신 팀 이름만 적는다.
TEAM_ALIASES = ("스텔라이브", "stellive")

# 이름이 너무 짧으면 다른 낱말에 우연히 걸린다(예: '린'은 '린다'에도 들어간다).
MIN_ALIAS_LENGTH = 2


KEEP = "0-9a-z가-힣ぁ-んァ-ヺ一-龥"


def _prepare(text):
    """유튜브 제목에는 자모가 분리된 한글(NFD)이 섞여 있어 그대로 비교하면 어긋난다."""
    return unicodedata.normalize("NFC", str(text or "")).lower()


def normalize(text):
    """비교용으로 글자만 남긴다. 'Tell Your World!' -> 'tellyourworld'"""
    return re.sub(r"[^" + KEEP + r"]", "", _prepare(text))


def loosen(text):
    """낱말 경계를 살린 형태. 'SODA POP [Saja Boys]' -> 'soda pop saja boys'"""
    return re.sub(r"[^" + KEEP + r"]+", " ", _prepare(text)).strip()


def aliases(member):
    """'아라하시 타비' -> {아라하시타비, 타비, tabi, ...}"""
    values = {member, member.split()[-1], *EXTRA_ALIASES.get(member, ())}
    return {
        normalized for value in values
        if len(normalized := normalize(value)) >= MIN_ALIAS_LENGTH
    }


def title_variants(song):
    """'악마가 아닌걸 (デビルじゃないもん)'처럼 원제를 괄호로 붙인 곡은 조각별로도 찾는다."""
    raw = song.get("title") or ""
    parts = [raw, re.sub(r"[(（\[][^)）\]]*[)）\]]", "", raw), song.get("title_alt") or ""]
    parts += re.findall(r"[(（\[]([^)）\]]+)[)）\]]", raw)
    # 짧은 조각은 아무 영상에나 걸리므로 버린다. 다만 '逆光'처럼 두 글자로 끝나는
    # 한자·한글 제목은 그 자체로 충분히 드문 말이라 남긴다.
    variants = {
        (tight, loosen(part)) for part in parts
        if len(tight := normalize(part)) >= (3 if tight.isascii() else 2)
    }
    return sorted(variants, key=lambda pair: len(pair[0]), reverse=True)


def title_matches(variant, video):
    """짧은 영문 제목은 낱말 단위로 봐야 한다. 'ray'가 'Gray'에 걸리면 곤란하다."""
    tight, loose = variant
    if len(tight) <= 5 and tight.isascii():
        return re.search(r"(?<![0-9a-z])" + re.escape(loose) + r"(?![0-9a-z])", video["loose"]) is not None
    return tight in video["tight"]


def song_members(song):
    """참여 멤버 칸. 비어 있으면 가수 칸에 적힌 이름을 대신 쓴다(솔로 곡은 대개 비어 있다)."""
    names = [name.strip() for name in (song.get("members") or "").split(",") if name.strip()]
    if names:
        return names
    artist = song.get("artist") or ""
    if "(" in artist or "（" in artist:
        return []
    return [name.strip() for name in artist.split(",") if name.strip()]


def unit_name(song):
    """'CLICHÉ(텐코 시부키, ...)'처럼 가수 칸 앞에 붙은 유닛 이름."""
    match = re.match(r"\s*([0-9A-Za-z가-힣À-ɏ]+)\s*[(（]", song.get("artist") or "")
    return normalize(match.group(1)) if match else ""


def evidence(song, video_title, known_members):
    """영상 제목이 이 곡의 사람들을 가리키는지 본다.

    반환값은 (곡의 멤버가 몇 명 나왔는지, 곡에 없는 멤버가 나왔는지)이다.
    """
    members = song_members(song)
    mine = sum(1 for member in members if any(alias in video_title for alias in aliases(member)))
    if not mine and song.get("section") == "group" and any(normalize(team) in video_title for team in TEAM_ALIASES):
        mine = len(members) or 1
    unit = unit_name(song)
    if not mine and unit and unit in video_title:
        mine = len(members) or 1
    others = any(
        any(alias in video_title for alias in aliases(other))
        for other in known_members
        if other not in members
    )
    return mine, others


def match_songs(songs, videos, known_members=()):
    """곡마다 영상을 짝지어 (확정, 확인 필요, 못 찾음)으로 나눈다."""
    known_members = tuple(known_members) or tuple(EXTRA_ALIASES)
    prepared = [
        {"video": video, "tight": normalize(video.get("title")), "loose": loosen(video.get("title"))}
        for video in videos
    ]
    confirmed, review, missing = [], [], []

    for song in songs:
        variants = title_variants(song)
        candidates = []
        for entry in prepared:
            if not any(title_matches(variant, entry) for variant in variants):
                continue
            matched, others = evidence(song, entry["tight"], known_members)
            candidates.append({"video": entry["video"], "members_matched": matched, "other_members": others})

        # 곡의 멤버가 제목에 있고 다른 멤버는 없는 후보만 믿는다.
        strong = [item for item in candidates if item["members_matched"] and not item["other_members"]]
        if not candidates:
            missing.append(song)
        elif len({item["video"]["video_id"] for item in strong}) == 1:
            confirmed.append({"song": song, **strong[0]})
        else:
            review.append({"song": song, "candidates": candidates})
    return confirmed, review, missing


def load_videos_from_db():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT video_id, title FROM song_counts")
            return cursor.fetchall()
    finally:
        connection.close()


def load_videos_from_html(path):
    from stelline.database.import_admin_html import parse_snapshot

    return parse_snapshot(path).get("song_counts", [])


def load_songs():
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, title_alt, artist, members, section, category, youtube_video_id"
                " FROM karaoke_songs ORDER BY sort_order, id"
            )
            songs = cursor.fetchall()
            cursor.execute("SELECT name FROM karaoke_members")
            known = [row["name"] for row in cursor.fetchall()]
    finally:
        connection.close()
    return songs, known or list(EXTRA_ALIASES)


def save_links(pairs):
    """(영상 ID, 곡 id) 목록을 저장한다. 이미 영상이 적힌 곡은 건드리지 않는다."""
    if not pairs:
        return 0
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE karaoke_songs SET youtube_video_id = %s"
                " WHERE id = %s AND (youtube_video_id IS NULL OR youtube_video_id = '')",
                pairs,
            )
            saved = cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return saved


def report_lines(confirmed, review, missing):
    """관리자 화면에 그대로 붙여 넣을 수 있는 표를 만든다(확정 줄만 남기면 된다)."""
    lines = ["곡명\t가수\t유튜브\t분류\t영상 제목"]
    for item in confirmed:
        song, video = item["song"], item["video"]
        lines.append(f"{song['title']}\t{song['artist']}\t{video['video_id']}\t확정\t{video['title']}")
    for item in review:
        song = item["song"]
        for candidate in item["candidates"]:
            video = candidate["video"]
            lines.append(f"{song['title']}\t{song['artist']}\t{video['video_id']}\t확인 필요\t{video['title']}")
    for song in missing:
        lines.append(f"{song['title']}\t{song['artist']}\t\t못 찾음\t")
    return lines


def main():
    parser = argparse.ArgumentParser(description="공식 재생목록 기록에서 노래방 곡의 유튜브 영상을 찾아 채웁니다.")
    parser.add_argument("--from-html", dest="html_path", help="관리자 페이지를 저장한 HTML에서 영상 목록을 읽습니다.")
    parser.add_argument("--apply", action="store_true", help="확정된 영상만 실제로 저장합니다. 없으면 미리 보기만 합니다.")
    parser.add_argument("--report", help="검토용 표(TSV)를 파일로 저장합니다.")
    args = parser.parse_args()

    songs, known_members = load_songs()
    targets = [song for song in songs if not (song.get("youtube_video_id") or "").strip()]
    videos = load_videos_from_html(args.html_path) if args.html_path else load_videos_from_db()
    if not videos:
        print("영상 목록이 비어 있습니다. song_counts에 재생목록 기록이 쌓였는지 확인하세요.")
        return

    confirmed, review, missing = match_songs(targets, videos, known_members)

    if args.report:
        io.open(args.report, "w", encoding="utf-8").write("\n".join(report_lines(confirmed, review, missing)))
        print(f"검토용 표를 저장했습니다: {args.report}")

    saved = 0
    if args.apply:
        saved = save_links([(item["video"]["video_id"], item["song"]["id"]) for item in confirmed])
        logging.info("유튜브 영상 연결 저장: %s건", saved)

    print(
        f"영상이 없는 곡 {len(targets)}곡 중 확정 {len(confirmed)}, 확인 필요 {len(review)}, 못 찾음 {len(missing)}"
        + (f" · {saved}곡 저장했습니다." if args.apply else " · 미리 보기라 저장하지 않았습니다.")
    )


if __name__ == "__main__":
    main()
