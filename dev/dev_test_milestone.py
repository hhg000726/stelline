from stelline.background_tasks import monitoring
from stelline.database.connection import get_connection
import pprint

# Replace notification sender with a noop that logs
def fake_send(cursor, access_token, song):
    print("[FAKE FCM] would notify for", song["video_id"], "count", song["count"]) 

monitoring.send_milestone_notifications = fake_send

conn = get_connection()
try:
    with conn.cursor() as cursor:
        # Ensure test row exists with lower count
        test_video_id = "TEST_VIDEO_123"
        cursor.execute("SELECT count FROM song_counts WHERE video_id = %s", (test_video_id,))
        existing = cursor.fetchone()
        if existing is None:
            cursor.execute(
                "INSERT INTO song_counts (video_id, title, count, counted_time) VALUES (%s, %s, %s, NOW())",
                (test_video_id, "Test Song", 90000),
            )
            conn.commit()
            print("Inserted initial test row with count=90000")
        else:
            print("Existing row:", existing)

        # Now simulate playlist having a song with 190000 (crosses 100k boundary)
        songs = [{"video_id": test_video_id, "title": "Test Song", "count": 190000}]
        monitoring.update_song_counts(cursor, songs, access_token=None)
        conn.commit()

        cursor.execute("SELECT * FROM song_counts WHERE video_id = %s", (test_video_id,))
        row = cursor.fetchone()
        print("After update:")
        pprint.pprint(row)
finally:
    conn.close()
