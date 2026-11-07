"""MySQL 스키마의 코드 기준(source of truth)."""

from datetime import datetime, timedelta, timezone

# 예전 위험도의 최댓값. 기본 검색에 실패한 곡은 늘 이 값이 됐다(015 에서 옛 값을 읽을 때만 쓴다).
LEGACY_MAX_RISK = 28
# 015 를 만들 때(2026-11) 한 회차는 10분 남짓 걸렸고 회차 사이는 8시간이었다. recent_data 의 시각과
# 곡의 마지막 검사 시각이 이만큼 안에 있으면 같은 회차의 같은 검사로 본다.
LEGACY_SAME_RUN = timedelta(hours=1)
# 016 전에 쌓인 검사 기록이 나온 정기 회차의 간격. 지금 설정(config.SEARCH_API_INTERVAL)을 읽지 않는 것은,
# 나중에 간격을 바꿔도 이미 지난 기록은 그때의 간격으로 회차를 정해야 하기 때문이다.
LEGACY_RUN_INTERVAL = 8 * 3600


def migrate_song_infos_primary_key(cursor):
    cursor.execute("DELETE FROM song_infos WHERE query IS NULL")
    cursor.execute("DELETE s1 FROM song_infos s1 INNER JOIN song_infos s2 ON s1.query = s2.query AND s1.video_id > s2.video_id")
    cursor.execute(
        """SELECT COUNT(*) AS primary_key_count
           FROM information_schema.TABLE_CONSTRAINTS
          WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'song_infos'
            AND CONSTRAINT_TYPE = 'PRIMARY KEY'"""
    )
    if cursor.fetchone()["primary_key_count"]:
        cursor.execute("ALTER TABLE song_infos DROP PRIMARY KEY")
    cursor.execute("ALTER TABLE song_infos MODIFY query VARCHAR(512) NOT NULL")
    cursor.execute(
        """SELECT COUNT(*) AS primary_key_count
           FROM information_schema.KEY_COLUMN_USAGE
          WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'song_infos'
            AND CONSTRAINT_NAME = 'PRIMARY'"""
    )
    if not cursor.fetchone()["primary_key_count"]:
        cursor.execute("ALTER TABLE song_infos ADD PRIMARY KEY (query)")

def add_column_if_missing(table, column, definition):
    """ALTER TABLE은 되돌릴 수 없어, 중간에 실패해도 다시 실행할 수 있게 존재 여부를 먼저 본다."""
    def migrate(cursor):
        cursor.execute(
            """SELECT COUNT(*) AS column_count
                 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
            (table, column),
        )
        if not cursor.fetchone()["column_count"]:
            cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}")
    return migrate


def backfill_search_checks(cursor):
    """예전 검색 점검 상태값을 새 검사 기록(search_checks)으로 옮긴다(015).

    예전에는 곡마다 마지막 결과를 song_infos 의 열(risk·fallback_query·last_checked_at)에 덮어쓰고,
    최종 실패한 곡은 recent_data 에 7일 동안 남겼다. 그 값에서 확실히 알 수 있는 것만 옮긴다.

    - last_checked_at 이 있는 곡: 그때 나온 결과 한 건. fallback_query 가 있으면 cover로만,
      위험도가 28 이면 막힘(기본 검색에 실패하면 늘 28 이 됐고, 웹 검색에서 찾으면 28 아래로 내렸다),
      그 밖에는 정상.
    - recent_data 의 행: 그 회차에 막혔다는 기록. 위의 마지막 결과와 같은 회차면 겹치므로 건너뛴다.

    last_checked_at 이 없는 곡(그 열이 생긴 10/20 이후 한 번도 검사하지 않은 곡)은 기록 없이 두어
    새 기준에서 가장 먼저 검사한다. 옛 표와 열은 지우지 않는다(코드를 되돌려도 돌아가게).
    """
    cursor.execute("SELECT COUNT(*) AS row_count FROM search_checks")
    if cursor.fetchone()["row_count"]:
        return  # 이미 옮겼다. 마이그레이션을 다시 돌려도 두 번 넣지 않는다.

    # last_checked_at 은 DB 의 CURRENT_TIMESTAMP(세션 시간대)로 저장됐다. 새 기록은 UTC 로 맞춘다.
    cursor.execute("SELECT TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), NOW()) AS offset_seconds")
    offset = timedelta(seconds=int(cursor.fetchone()["offset_seconds"]))

    cursor.execute("SELECT query, video_id, risk, fallback_query, last_checked_at FROM song_infos")
    songs, latest, rows = {}, {}, []
    for song in cursor.fetchall():
        query, video_id = song["query"], song["video_id"]
        if not query or not video_id:
            continue
        songs[query] = song
        if song["last_checked_at"] is None:
            continue
        checked_at = song["last_checked_at"] - offset
        if song["fallback_query"]:
            result, fallback = "cover_only", song["fallback_query"]
        elif (song["risk"] or 0) >= LEGACY_MAX_RISK:
            result, fallback = "blocked", None
        else:
            result, fallback = "visible", None
        rows.append((query, video_id, result, fallback, checked_at))
        latest[query] = checked_at

    # 운영 DB 의 recent_data 는 코드 스키마와 열 구성이 달라(id 없음, query 가 기본키) 쓰는 열만 고른다.
    cursor.execute("SELECT query, video_id, searched_time FROM recent_data")
    seen = set()
    for row in cursor.fetchall():
        song = songs.get(row["query"])
        if song is None or song["video_id"] != row["video_id"] or row["searched_time"] is None:
            continue  # 지금 목록에 없거나 영상이 바뀐 곡의 기록은 다른 대상을 검사한 것이다.
        failed_at = datetime.fromtimestamp(float(row["searched_time"]), timezone.utc).replace(tzinfo=None)
        known = latest.get(row["query"])
        if (known is not None and abs(known - failed_at) < LEGACY_SAME_RUN) or (row["query"], failed_at) in seen:
            continue
        seen.add((row["query"], failed_at))
        rows.append((row["query"], row["video_id"], "blocked", None, failed_at))

    if rows:
        cursor.executemany(
            """INSERT INTO search_checks (query, video_id, result, fallback_query, checked_at)
               VALUES (%s, %s, %s, %s, %s)""",
            rows,
        )


def backfill_search_run_started_at(cursor):
    """016 전에 쌓인 검사 기록에 회차 시작 시각을 채운다.

    그때까지의 기록(015 로 옮긴 것 포함)은 모두 정기 회차에서 나왔다. 정기 회차는 UTC 기준 8시간
    경계에서 시작하므로 검사 시각을 그 경계로 내린다. 한 회차는 10분 남짓이라 경계를 넘지 않는다.
    """
    cursor.execute("SELECT id, checked_at FROM search_checks WHERE run_started_at IS NULL")
    updates = []
    for row in cursor.fetchall():
        epoch = int(row["checked_at"].replace(tzinfo=timezone.utc).timestamp())
        started = datetime.fromtimestamp(epoch - epoch % LEGACY_RUN_INTERVAL, timezone.utc).replace(tzinfo=None)
        updates.append((started, row["id"]))
    if updates:
        cursor.executemany("UPDATE search_checks SET run_started_at = %s WHERE id = %s", updates)


def drop_column_if_present(table, column):
    """없는 열을 지우려 하면 실패하므로 존재 여부를 먼저 본다."""
    def migrate(cursor):
        cursor.execute(
            """SELECT COUNT(*) AS column_count
                 FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
            (table, column),
        )
        if cursor.fetchone()["column_count"]:
            cursor.execute(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")
    return migrate


MIGRATIONS = [
    ("001_initial_schema", [
        """CREATE TABLE IF NOT EXISTS song_infos (video_id VARCHAR(32) NOT NULL, query VARCHAR(512) PRIMARY KEY, risk INT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS songs_data (video_id VARCHAR(32) PRIMARY KEY, query VARCHAR(512) NOT NULL, searched_time DOUBLE NOT NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS recent_data (id BIGINT AUTO_INCREMENT PRIMARY KEY, video_id VARCHAR(32) NOT NULL, query VARCHAR(512) NOT NULL, searched_time DOUBLE NOT NULL, INDEX recent_data_searched_time_idx (searched_time)) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS record_main (copy_count BIGINT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        "INSERT INTO record_main (copy_count) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM record_main)",
        """CREATE TABLE IF NOT EXISTS record_search (total_plays BIGINT NOT NULL DEFAULT 0, total_play_time DOUBLE NOT NULL DEFAULT 0, copy_count BIGINT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        "INSERT INTO record_search (total_plays, total_play_time, copy_count) SELECT 0, 0, 0 WHERE NOT EXISTS (SELECT 1 FROM record_search)",
        """CREATE TABLE IF NOT EXISTS targets (name VARCHAR(255) PRIMARY KEY, title VARCHAR(255) NOT NULL, url_number INT NOT NULL, expires_at DATETIME NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS events (title VARCHAR(255) PRIMARY KEY, link TEXT NOT NULL, expires_at DATETIME NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS twits (title VARCHAR(255) PRIMARY KEY, time VARCHAR(255) NULL, tags TEXT NOT NULL, keywords TEXT NOT NULL, expires_at DATETIME NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS song_counts (video_id VARCHAR(32) PRIMARY KEY, title VARCHAR(512) NOT NULL, count BIGINT NOT NULL DEFAULT 0, counted_time DATETIME NOT NULL) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS fcm_tokens (id BIGINT AUTO_INCREMENT PRIMARY KEY, token TEXT NOT NULL, registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY fcm_tokens_token_idx (token(255))) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS offline (name VARCHAR(255) PRIMARY KEY, location_name VARCHAR(255) NULL, description TEXT NULL, latitude DOUBLE NOT NULL DEFAULT 0, longitude DOUBLE NOT NULL DEFAULT 0, start_date DATETIME NULL, end_date DATETIME NULL, address TEXT NULL, always BOOLEAN NOT NULL DEFAULT FALSE) CHARACTER SET utf8mb4""",
    ]),
    ("002_change_song_infos_pk", [
        migrate_song_infos_primary_key,
    ]),
    ("003_song_reports", [
        """CREATE TABLE IF NOT EXISTS song_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
    ]),
    ("004_view_reports", [
        """CREATE TABLE IF NOT EXISTS view_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
    ]),
    ("005_karaoke", [
        """CREATE TABLE IF NOT EXISTS karaoke_songs (id BIGINT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255) NOT NULL, title_alt VARCHAR(255) NULL, artist VARCHAR(255) NOT NULL, members VARCHAR(512) NULL, section VARCHAR(16) NOT NULL DEFAULT 'solo', category VARCHAR(16) NOT NULL DEFAULT 'cover', tj VARCHAR(16) NULL, ky VARCHAR(16) NULL, note VARCHAR(255) NULL, sort_order INT NOT NULL DEFAULT 0, updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, UNIQUE KEY karaoke_songs_title_artist_idx (title, artist), INDEX karaoke_songs_sort_idx (sort_order)) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS karaoke_members (name VARCHAR(64) PRIMARY KEY, unit VARCHAR(64) NULL, display_order INT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS karaoke_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
        """CREATE TABLE IF NOT EXISTS record_karaoke (copy_count BIGINT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        "INSERT INTO record_karaoke (copy_count) SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM record_karaoke)",
    ]),
    ("006_karaoke_member_history", [
        add_column_if_missing("karaoke_songs", "release_date", "DATE NULL AFTER ky"),
        add_column_if_missing("karaoke_members", "former_units", "VARCHAR(128) NULL"),
        add_column_if_missing("karaoke_members", "debut_date", "DATE NULL"),
        add_column_if_missing("karaoke_members", "graduated_at", "DATE NULL"),
        """ALTER TABLE karaoke_members MODIFY unit VARCHAR(64) NULL""",
    ]),
    ("007_main_buttons", [
        """CREATE TABLE IF NOT EXISTS main_buttons (button_key VARCHAR(64) PRIMARY KEY, label VARCHAR(255) NOT NULL, visible BOOLEAN NOT NULL DEFAULT TRUE, display_order INT NOT NULL DEFAULT 0) CHARACTER SET utf8mb4""",
        # 메인 화면에 이미 있는 버튼을 기본값(표시)으로 등록한다.
        """INSERT INTO main_buttons (button_key, label, visible, display_order)
           VALUES ('search', '검색 안되는 노래 보기', TRUE, 1),
                  ('karaoke', '노래방 번호 찾기', TRUE, 2),
                  ('congratulation', '조회수 축하 알림', TRUE, 3)
           ON DUPLICATE KEY UPDATE button_key = button_key""",
    ]),
    ("008_karaoke_youtube_video", [
        # 커버 곡의 발매일을 유튜브 업로드 날짜로 채우려면 어느 영상인지 알아야 한다.
        add_column_if_missing("karaoke_songs", "youtube_video_id", "VARCHAR(32) NULL AFTER release_date"),
    ]),
    ("009_drop_karaoke_youtube_video", [
        # 유튜브 영상은 노래방 화면에서 쓰지 않기로 해서 되돌린다.
        # (008을 지우지 않고 새 마이그레이션으로 되돌려야 이미 적용한 DB도 맞춰진다.)
        drop_column_if_present("karaoke_songs", "youtube_video_id"),
    ]),
    ("010_drop_karaoke_note_and_order", [
        # 비고와 정렬 순서는 화면에서 쓰지 않기로 했다. 목록은 랜덤·가나다순으로만 본다.
        drop_column_if_present("karaoke_songs", "note"),
        drop_column_if_present("karaoke_songs", "sort_order"),
    ]),
    ("011_site_contents", [
        # 화면에 박아 둔 문구·그림 중 관리자가 바꾼 것만 담는다.
        # 행이 없으면 stelline/content/registry.py 의 기본값이 그대로 쓰이므로,
        # 이 표가 비어 있어도(또는 조회에 실패해도) 화면은 지금과 똑같이 보인다.
        #
        # cleared=1 은 "관리자가 일부러 비웠다"는 뜻이고, 그 자리는 화면에서 사라진다.
        # 그림은 파일이 아니라 여기에 넣는다. 컨테이너를 다시 올려도 남아 있어야 하기 때문이다.
        """CREATE TABLE IF NOT EXISTS site_contents (
             content_key VARCHAR(64) PRIMARY KEY,
             cleared BOOLEAN NOT NULL DEFAULT FALSE,
             text_value TEXT NULL,
             image_data MEDIUMBLOB NULL,
             image_mime VARCHAR(32) NULL,
             image_width INT NULL,
             image_height INT NULL,
             updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
           ) CHARACTER SET utf8mb4""",
    ]),
    ("012_drop_karaoke_footer_content", [
        # 노래방 꼬리말은 공통 꼬리말과 사실상 같은 문구라 항목을 하나로 합쳤다.
        # 코드에서 사라진 키의 행이 남아 있으면 나중에 이게 뭔지 알 수 없다.
        "DELETE FROM site_contents WHERE content_key = 'karaoke_footer_note'",
    ]),
    ("013_drop_congratulation_hero_subtitle", [
        # 조회수 축하 화면에 안내 문구를 새로 만드는 대신, 이미 있던 알림 안내 문구를
        # 고칠 수 있게 바꿨다(`congratulation_notify_prompt`). 잠깐 있었던 키를 지운다.
        "DELETE FROM site_contents WHERE content_key = 'congratulation_hero_subtitle'",
    ]),
    ("014_search_cover_fallback", [
        add_column_if_missing("song_infos", "fallback_query", "VARCHAR(512) NULL"),
        add_column_if_missing("song_infos", "last_checked_at", "DATETIME NULL"),
    ]),
    ("015_search_checks", [
        # 검색 노출 판정의 원천. 곡 하나를 검사할 때마다 한 줄씩 쌓는다(stelline/apis/search/history.py).
        # 현재 상태·최근 7일·재시도 여부는 모두 이 기록에서 계산하고 따로 저장하지 않는다.
        # 예전처럼 회차가 끝날 때 목록 표를 비우고 다시 채우지 않으므로, 회차가 중간에 끊겨도
        # 그때까지 검사한 결과가 남는다. checked_at 은 UTC 다.
        #
        # 이제 쓰지 않는 songs_data·recent_data 표와 song_infos 의 risk·fallback_query·last_checked_at
        # 열은 코드를 되돌릴 때를 대비해 이번에는 남겨 둔다.
        """CREATE TABLE IF NOT EXISTS search_checks (
             id BIGINT AUTO_INCREMENT PRIMARY KEY,
             query VARCHAR(512) NOT NULL,
             video_id VARCHAR(100) NOT NULL,
             result VARCHAR(16) NOT NULL,
             fallback_query VARCHAR(512) NULL,
             checked_at DATETIME NOT NULL,
             INDEX search_checks_checked_at_idx (checked_at)
           ) CHARACTER SET utf8mb4""",
        backfill_search_checks,
    ]),
    ("016_search_runs_and_requests", [
        # 검사 기록마다 그 곡을 검사한 회차의 시작 시각. 화면의 '마지막 검색'이 이것으로 한 회차를 묶는다.
        add_column_if_missing("search_checks", "run_started_at", "DATETIME NULL"),
        backfill_search_run_started_at,
        # 관리자가 다음 회차를 조정한 내용. 곡마다 하나(검색어가 기본키)이고 한 번 쓰면 지운다.
        #   first: 다음 회차 맨 앞에서 검사한다. 그 곡을 실제로 검사하면 지운다.
        #   skip : 다음 회차 순서에서 뺀다. 그 회차가 돌고 나면 지운다.
        """CREATE TABLE IF NOT EXISTS search_requests (
             query VARCHAR(512) PRIMARY KEY,
             action VARCHAR(8) NOT NULL,
             requested_at DATETIME NOT NULL
           ) CHARACTER SET utf8mb4""",
    ]),
]
