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
            'tj': '12345', 'ky': None, 'title_alt': None,
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
        self.assertIn('<th>참여 멤버</th>', html)
        # 구분·종류는 DB 값 대신 한글 이름으로 보여준다.
        self.assertIn('>단체</td>', html)
        self.assertIn('>커버</td>', html)

    def test_karaoke_table_marks_empty_cells_and_scrolls_in_place(self):
        html = self._render()
        self.assertIn('class="is-empty"', html)   # 금영 번호가 비었음을 눈에 띄게
        self.assertIn('data-table="karaoke_songs"', html)
        # 곡이 수백 개라 표는 제자리에서 스크롤되고 머리글이 붙박이여야 한다.
        self.assertIn('table-scroll', html)
        self.assertIn('data-table-filter', html)

    def test_tables_are_split_into_tabs(self):
        """표 열한 개를 한 화면에 펼치면 찾는 데만 시간이 걸린다. 묶음별로 나눠 보여준다."""
        html = self._render()
        self.assertIn('data-group="karaoke"', html)          # 탭 버튼
        self.assertIn('data-group-panel="karaoke"', html)     # 탭이 여는 칸
        self.assertIn('data-group-panel="reports"', html)
        self.assertIn('stelline.admin.group', html)           # 고른 탭을 기억한다

    def test_form_labels_are_written_in_korean(self):
        """열 이름을 그대로 보여 주면 무엇을 넣는 칸인지 알기 어렵다."""
        html = self._render()
        self.assertIn('<label>영상 ID', html)
        self.assertIn('<label>검색어', html)
        self.assertIn('<label>만료 시각(비우면 계속 표시)', html)

    def test_karaoke_row_still_carries_every_value_for_the_edit_form(self):
        """표에서 뺀 열도 행을 누르면 양식에 채워져야 한다."""
        html = self._render()
        self.assertIn('data-row=', html)
        self.assertIn('title_alt', html)

    def test_every_row_offers_a_copy_button(self):
        """행을 누르면 수정이라, 값을 그대로 가져다 새 항목을 만들 길을 따로 둔다."""
        html = self._render()
        self.assertIn('data-copy-row', html)
        self.assertIn('새 항목으로 추가', html)
        # 버튼을 눌렀을 때 행 클릭(수정)이 덮어쓰지 않도록 연결돼 있어야 한다.
        self.assertIn("row.querySelector('[data-copy-row]')", html)
        self.assertIn('copyButton.addEventListener', html)


if __name__ == '__main__':
    unittest.main()
