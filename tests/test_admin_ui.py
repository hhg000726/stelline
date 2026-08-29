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

        with patch('stelline.admin.views.get_connection') as mock_get_connection, \
             patch('stelline.admin.views.load_table', return_value=[fake_row]):
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
        self.assertIn("input.type === 'datetime-local'", html)


if __name__ == '__main__':
    unittest.main()
