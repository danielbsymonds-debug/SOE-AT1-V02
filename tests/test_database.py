# ensure project root is on sys.path so imports like `password_Manager` and `database`
# (which live in the parent folder) can be resolved when tests run from tests/
import sys, os
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import unittest
import sqlite3
import os
import time
from password_Manager import password_Manager
import database

class TestDatabaseUserLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ...existing code...
        # ensure DB file path
        cls.db_path = os.path.join(os.path.dirname(__file__), '..', 'LoginData.db')
        cls.db_path = os.path.normpath(cls.db_path)
        # If database module provides initialization helpers use them (optional)
        try:
            # call any init functions that create tables (no-op if not present)
            for fn in ('init_quiz_db', 'init_admin_table', 'init_quiz_questions_table', 'init_user_result_table'):
                if hasattr(database, fn):
                    getattr(database, fn)()
        except Exception:
            pass

    def setUp(self):
        # create USERS table if missing and insert a test user
        self.conn = sqlite3.connect(self.db_path)
        self.cur = self.conn.cursor()
        # Create USERS table minimal schema (if not exists)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS USERS(
                first_name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                password TEXT
            )
        """)
        self.conn.commit()

        # unique test email
        ts = int(time.time() * 1000)
        self.test_email = f"testuser_{ts}@example.com"
        self.first_name = "Test"
        self.last_name = "User"
        self.raw_password = "S3cureP@ssw0rd!"
        self.hashed_pw = password_Manager.hash_password(self.raw_password)

        # insert test user
        self.cur.execute(
            "INSERT INTO USERS(first_name,last_name,email,password) VALUES (?,?,?,?)",
            (self.first_name, self.last_name, self.test_email, self.hashed_pw)
        )
        self.conn.commit()

    def tearDown(self):
        # delete the test user and close connection
        try:
            self.cur.execute("DELETE FROM USERS WHERE email=?", (self.test_email,))
            self.conn.commit()
        finally:
            self.cur.close()
            self.conn.close()

    def test_get_user_by_email_returns_inserted_user(self):
        # Use database.get_user_by_email to verify retrieval
        user = None
        try:
            user = database.get_user_by_email(self.test_email)
        except AttributeError:
            # If database.get_user_by_email is not present, fail with clear message
            self.fail("database.get_user_by_email function not found in database.py")

        # Accept either a row tuple or a list with one tuple
        if user is None:
            self.fail("get_user_by_email returned None for existing user")

        # normalize if function returns list/rows
        if isinstance(user, (list, tuple)) and len(user) > 0 and not isinstance(user[0], (str, bytes)):
            # likely a row tuple already
            row = user
        else:
            row = user

        # The expected shape (based on app.py usage) is (first_name, last_name, email, ...)
        # Validate email present somewhere in the returned structure
        email_found = False
        try:
            # If row is a tuple-like record
            if isinstance(row, (list, tuple)):
                if self.test_email in row:
                    email_found = True
            # If row is an object or other mapping, try attribute / key access
            if not email_found:
                if hasattr(row, 'email') and getattr(row, 'email') == self.test_email:
                    email_found = True
                elif isinstance(row, dict) and row.get('email') == self.test_email:
                    email_found = True
        except Exception:
            pass

        self.assertTrue(email_found, "Returned user record does not contain the expected email")

class TestQuizHeadAndItems(unittest.TestCase):
    def setUp(self):
        # use database.get_db to open the same Quiz DB the module uses
        self.conn = database.get_db(database.QUIZ_DB)
        self.cur = self.conn.cursor()
        # ensure QUIZ_HEADER exists (legacy schema used by create_quiz_head)
        self.cur.execute("""
            CREATE TABLE IF NOT EXISTS QUIZ_HEADER (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                num_questions INTEGER,
                genres TEXT,
                created_by TEXT,
                is_active INTEGER DEFAULT 0
            )
        """)
        # ensure QuizQuestions table exists (uses the same DB)
        database.init_quiz_questions_table()
        self.conn.commit()
        self.created_header_ids = []

    def tearDown(self):
        # remove any created questions and headers
        for hid in self.created_header_ids:
            try:
                self.cur.execute("DELETE FROM QuizQuestions WHERE Qid=?", (hid,))
            except Exception:
                pass
            try:
                self.cur.execute("DELETE FROM QUIZ_HEADER WHERE id=?", (hid,))
            except Exception:
                pass
        self.conn.commit()
        self.cur.close()
        self.conn.close()

    def test_create_quiz_head_and_items(self):
        # create header
        hid = database.create_quiz_head('2025-01-01', 2, 'general knowledge', 'tester@example.com')
        self.assertIsNotNone(hid, "create_quiz_head should return an id")
        self.created_header_ids.append(hid)

        # add two questions
        database.create_item_line(hid, 1, 'What is 2+2?', '3', '4', '5', '6', '2')
        database.create_item_line(hid, 2, 'Capital of France?', 'Berlin', 'Madrid', 'Paris', 'Rome', '3')

        # verify rows inserted for that Qid
        rows = self.cur.execute(
            "SELECT Qno, Qstr, A, B, C, D, CAns FROM QuizQuestions WHERE Qid=? ORDER BY Qno ASC",
            (hid,)
        ).fetchall()

        self.assertEqual(len(rows), 2, "Expected two QuizQuestions rows for the created header")
        # first question checks
        q1 = rows[0]
        self.assertEqual(q1[0], 1)          # Qno
        self.assertEqual(q1[1], 'What is 2+2?')
        self.assertEqual(q1[2], '3')        # A
        self.assertEqual(q1[3], '4')        # B
        self.assertEqual(str(q1[6]), '2')   # CAns stored as '2'
        # second question checks
        q2 = rows[1]
        self.assertEqual(q2[0], 2)
        self.assertEqual(q2[1], 'Capital of France?')
        self.assertEqual(str(q2[6]), '3')

if __name__ == '__main__':
    unittest.main()