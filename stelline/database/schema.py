"""MySQL 스키마의 코드 기준(source of truth)."""

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
        "DELETE FROM song_infos WHERE query IS NULL",
        "DELETE s1 FROM song_infos s1 INNER JOIN song_infos s2 ON s1.query = s2.query AND s1.video_id > s2.video_id",
        "ALTER TABLE song_infos DROP PRIMARY KEY",
        "ALTER TABLE song_infos MODIFY query VARCHAR(512) NOT NULL",
        "ALTER TABLE song_infos ADD PRIMARY KEY (query)",
    ]),
    ("003_song_reports", [
        """CREATE TABLE IF NOT EXISTS song_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
    ]),
    ("004_view_reports", [
        """CREATE TABLE IF NOT EXISTS view_reports (id BIGINT AUTO_INCREMENT PRIMARY KEY, content TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP) CHARACTER SET utf8mb4""",
    ]),
]
