import os
import unittest
from unittest.mock import patch

os.environ.setdefault('APP_ENV', 'development')
os.environ.setdefault('START_BACKGROUND_TASKS', 'false')
os.environ.setdefault('AUTO_CREATE_SCHEMA', 'false')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('SERVICE_ACCOUNT_FILE', '')

from stelline import app


class AdminPageAutoFillTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_admin_rows_include_row_data_for_autofill(self):
        fake_row = {
            'title': '테스트 이벤트',
            'link': 'https://example.com/event',
            'expires_at': '2026-12-31 12:34:00',
        }

        with patch('stelline.admin.routes.get_connection') as mock_get_connection, \
             patch('stelline.admin.routes.load_table', return_value=[fake_row]):
            mock_connection = unittest.mock.Mock()
            mock_connection.close.return_value = None
            mock_get_connection.return_value = mock_connection

            with self.client.session_transaction() as session:
                session['logged_in'] = True
                session['admin_csrf'] = 'test-token'

            response = self.client.get('/admin/')

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-row=', html)
        self.assertIn('테스트 이벤트', html)
        self.assertIn('normalizeDateTimeInput', html)
        self.assertIn("field.type === 'datetime-local'", html)


class KaraokeListViewTest(unittest.TestCase):
    """곡이 수백 개라 표가 읽히는지가 중요하다."""

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def _render(self):
        song = {
            'id': 1, 'title': '테스트곡', 'title_alt': None, 'artist': '아이리 칸나',
            'members': '아이리 칸나', 'section': 'group', 'category': 'cover',
            'tj': '12345', 'ky': None, 'release_date': '2024-01-01',
            'youtube_video_id': None, 'note': None, 'sort_order': 0,
            'updated_at': '2026-08-31 09:00:00',
        }
        with patch('stelline.admin.routes.get_connection'),              patch('stelline.admin.routes.load_table',
                   side_effect=lambda connection, table: [song] if table == 'karaoke_songs' else []):
            with self.client.session_transaction() as session:
                session['logged_in'] = True
                session['admin_csrf'] = 'test-token'
            return self.client.get('/admin/').get_data(as_text=True)

    def test_karaoke_table_uses_korean_headers_and_values(self):
        html = self._render()
        self.assertIn('<th>곡명</th>', html)
        self.assertIn('<th>유튜브</th>', html)
        # 구분·종류는 DB 값 대신 한글 이름으로 보여준다.
        self.assertIn('>단체</td>', html)
        self.assertIn('>커버</td>', html)

    def test_karaoke_table_marks_empty_cells_and_spans_the_full_width(self):
        html = self._render()
        self.assertIn('class="is-empty"', html)   # 금영 번호·유튜브가 비었음을 눈에 띄게
        self.assertIn('section.wide', html)       # 넓은 칸 스타일
        self.assertIn('data-table="karaoke_songs" class="wide"', html)

    def test_karaoke_row_still_carries_every_value_for_the_edit_form(self):
        """표에서 뺀 열도 행을 누르면 양식에 채워져야 한다."""
        html = self._render()
        self.assertIn('data-row=', html)
        self.assertIn('sort_order', html)


if __name__ == '__main__':
    unittest.main()
