import sqlite3
from datetime import datetime
from flask import g
import json
import re

LOGIN_DB = "LoginData.db"
QUIZ_DB = "QuizData.db"

# -----------------------------
# User & OTP tables
# -----------------------------

# -----------------------------
# QuizQuestions and User_Result tables
# -----------------------------

def get_db(dbString):
    return sqlite3.connect(dbString)
    #if 'db' not in g:
    #    g.db = sqlite3.connect(app.config['dbString'], detect_types=..., check_same_thread=False)
    #    g.db.row_factory = sqlite3.Row
    #return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# -----------------------------
# Quiz results table
# -----------------------------
def init_quiz_db():
    """Initialize QUIZ_RESULTS table."""
    cursor = get_db(QUIZ_DB).cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QUIZ_RESULTS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        subject TEXT,
        score INTEGER,
        total INTEGER
    )
    """)
    get_db(QUIZ_DB).commit()
    get_db(QUIZ_DB).close()

def init_quiz_questions_table():
    """
    Create QuizQuestions table to store individual question rows for quizzes.
    Columns:
      Qid   INTEGER PRIMARY KEY AUTOINCREMENT
      Qno   INTEGER           -- question number in that quiz (1-based)
      Qstr  TEXT              -- question text
      A     TEXT              -- option A text (include 'A)' prefix if desired)
      B     TEXT
      C     TEXT
      D     TEXT
      CAns  TEXT              -- correct answer letter ('A'..'D') or the correct option text
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS QuizQuestions")
    connection.commit() 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QuizQuestions (
        Qid INTEGER,
        Qno INTEGER,
        Qstr TEXT,
        A TEXT,
        B TEXT,
        C TEXT,
        D TEXT,
        CAns TEXT,
        PRIMARY KEY (Qid,Qno)
    )
    """)
    connection.commit()
    connection.close()

# -----------------------------
# QuizHeader table (quiz metadata)
# -----------------------------
def init_quiz_header_table():
    """
    Create QuizHeader table to store quiz-level metadata.
    Columns:
      id        INTEGER PRIMARY KEY AUTOINCREMENT
      per_create TEXT       -- creator identifier (email/name)
      date_time  INTEGER    -- unix timestamp (seconds) for date/time of quiz
      no_ques    INTEGER    -- number of questions in the quiz
      genre      TEXT       -- genre or comma-separated genres
      is_active  INTEGER    -- 0/1 -> boolean (1 = active)
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS QUIZ_HEADER")
    connection.commit() 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QuizHeader (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        per_create TEXT,
        date_time INTEGER,
        no_ques INTEGER,
        genre TEXT,
        is_active INTEGER
    )
    """)
    connection.commit()
    connection.close()

# --- Admin table and daily scores helpers ---

def init_admin_table():
    """Create ADMIN table to store admin account(s)."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ADMIN (
        email VARCHAR(50) PRIMARY KEY,
        password VARCHAR(255) NOT NULL,
        first_name VARCHAR(50),
        last_name VARCHAR(50)
    )
    """)
    connection.commit()
    connection.close()

def add_user(fname, lname, email, password):
    """Insert a new user."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO USERS(first_name,last_name,email,password) VALUES (?,?,?,?)",
                   (fname, lname, email, password))
    connection.commit()
    connection.close()

def create_item_line(headerId, QuestionId, question, answer1,answer2,answer3,answer4, correct_answer):
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO QuizQuestions(Qid, Qno, Qstr, A,B,C,D, CAns) VALUES (?,?,?,?,?,?,?,? )",
                   (headerId, QuestionId, question, answer1,answer2,answer3,answer4, correct_answer))
    connection.commit()
    connection.close()

def create_quiz_head(dateCreated, noQues, genre, createdBy):
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO QUIZ_HEADER(date,num_questions, genres, created_by   ) VALUES (?,?,?,?)",
                   (dateCreated, noQues, genre, createdBy))
    connection.commit()
    connection.close()
    return cursor.lastrowid

def get_users():
    """Return all users."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT * FROM USERS").fetchall()
    connection.close()
    return rows


def save_otp(email, otp):
    """Save or update OTP for a user."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM USEROTP WHERE email=?", (email,))
    cursor.execute("INSERT INTO USEROTP(email, otp) VALUES (?, ?)", (email, otp))
    connection.commit()
    connection.close()


def check_otp(email, otp):
    """Check if OTP matches for a given email."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    ans = cursor.execute("SELECT * FROM USEROTP WHERE email=?", (email,)).fetchall()
    connection.close()
    return len(ans) > 0 and ans[0][1] == otp


def save_quiz_result(email, subject, score, total):
    """Save a quiz result."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO QUIZ_RESULTS(email, subject, score, total) VALUES (?, ?, ?, ?)",
                   (email, subject, score, total))
    connection.commit()
    connection.close()


def get_user_results(email):
    """Get all quiz results for a user."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT * FROM QUIZ_RESULTS WHERE email=?", (email,)).fetchall()
    connection.close()
    return rows


def get_all_results():
    """Get all quiz results."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT * FROM QUIZ_RESULTS").fetchall()
    connection.close()
    return rows




def add_admin(email, password, first_name=None, last_name=None):
    """Insert a new admin (use hashed password)."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT OR REPLACE INTO ADMIN(email, password, first_name, last_name) VALUES (?, ?, ?, ?)",
                   (email, password, first_name, last_name))
    connection.commit()
    connection.close()


def get_admins():
    """Return all admins."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT email, first_name, last_name FROM ADMIN").fetchall()
    connection.close()
    return rows


def init_daily_scores():
    """Create DAILY_SCORES table to store daily quiz scores (per user)."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS DAILY_SCORES (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fname TEXT,
        lname TEXT,
        email TEXT,
        score INTEGER,
        date TEXT
    )
    """)
    connection.commit()
    connection.close()


def save_daily_score(fname, lname, email, score, date=None):
    """Save a daily quiz score entry."""
    if date is None:
        date = datetime.utcnow().isoformat()
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO DAILY_SCORES(fname, lname, email, score, date) VALUES (?, ?, ?, ?, ?)",
                   (fname, lname, email, score, date))
    connection.commit()
    connection.close()


def get_all_daily_scores():
    """Return all daily scores, ordered newest first."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT id, fname, lname, email, score, date FROM DAILY_SCORES ORDER BY date DESC").fetchall()
    connection.close()
    return rows


def get_user_by_email(email):
    """Return user (first_name, last_name, email) from USERS table (or None)."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    row = cursor.execute("SELECT first_name, last_name, email FROM USERS WHERE email=?", (email,)).fetchone()
    connection.close()
    return row

def init_admin_table():
    """Create ADMIN table to store admin account(s)."""
    connection = get_db(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ADMIN (
        email VARCHAR(50) PRIMARY KEY,
        password VARCHAR(255) NOT NULL,
        first_name VARCHAR(50),
        last_name VARCHAR(50)
    )
    """)

    # --- auto-create default admin if not present ---
    try:
        from password_Manager import password_Manager
        default_email = "daniel.b.symonds@gmail.com"
        default_plain = "STARWARS"
        default_hashed = password_Manager.hash_password(default_plain)
        cursor.execute(
            "INSERT OR IGNORE INTO ADMIN(email, password, first_name, last_name) VALUES (?, ?, ?, ?)",
            (default_email, default_hashed, "daniel", "symonds")
        )
    except Exception:
        # avoid breaking init if something goes wrong with password_Manager import
        pass
    # -------------------------------------------------
    connection.commit()
    connection.close()



def save_quiz_question(qno, qstr, a, b, c, d, cans):
    """
    Insert a question row into QuizQuestions.
    Returns the inserted Qid.
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO QuizQuestions (Qno, Qstr, A, B, C, D, CAns) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (qno, qstr, a, b, c, d, cans)
    )
    qid = cursor.lastrowid
    connection.commit()
    connection.close()
    return qid

def get_quiz_questions():
    """Return all QuizQuestions rows (list of tuples)."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT Qid, Qno, Qstr, A, B, C, D, CAns FROM QuizQuestions ORDER BY Qno ASC").fetchall()
    connection.close()
    return rows

def get_question_by_qid(qid):
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    row = cursor.execute("SELECT Qid, Qno, Qstr, A, B, C, D, CAns FROM QuizQuestions WHERE Qid=?", (qid,)).fetchone()
    connection.close()
    return row


def init_user_result_table():
    """
    Create User_Result table to record individual user answers.
    Columns:
      id              INTEGER PRIMARY KEY AUTOINCREMENT
      user            TEXT   -- user identifier (email or username)
      Qid             INTEGER -- foreign key into QuizQuestions.Qid (optional)
      Qno             INTEGER -- question number (copied for convenience)
      Ans             TEXT   -- the answer the user submitted (letter or text)
      correct_answer  INTEGER -- 0 or 1 for False/True
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS User_Result (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        Qid INTEGER,
        Qno INTEGER,
        Ans TEXT,
        correct_answer INTEGER
    )
    """)
    connection.commit()
    connection.close()

def save_user_result(user, qid, qno, ans, correct):
    """
    Save a user's answer.
    `correct` should be truthy/falsey (True -> 1, False -> 0)
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO User_Result (user, Qid, Qno, Ans, correct_answer) VALUES (?, ?, ?, ?, ?)",
        (user, qid, qno, ans, 1 if correct else 0)
    )
    connection.commit()
    connection.close()

def get_user_results(user):
    """Return all User_Result rows for a given user (list of tuples)."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT id, user, Qid, Qno, Ans, correct_answer FROM User_Result WHERE user=? ORDER BY id DESC", (user,)).fetchall()
    connection.close()
    return rows

def get_results_for_question(qid):
    """Return all User_Result rows for a particular question id."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT id, user, Qid, Qno, Ans, correct_answer FROM User_Result WHERE Qid=?", (qid,)).fetchall()
    connection.close()
    return rows


def save_quiz_header(per_create, date_time, no_ques, genre, is_active=0):
    """
    Insert a quiz header row. `date_time` should be an integer timestamp (UTC seconds).
    Returns the inserted id.
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO QuizHeader (per_create, date_time, no_ques, genre, is_active) VALUES (?, ?, ?, ?, ?)",
        (per_create, int(date_time), int(no_ques), genre, 1 if is_active else 0)
    )
    qid = cursor.lastrowid
    connection.commit()
    connection.close()
    return qid

def get_quiz_headers(active_only=False):
    """
    Return list of quiz header rows.
    If active_only is True, returns only rows where is_active=1.
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    if active_only:
        rows = cursor.execute("SELECT id, per_create, date_time, no_ques, genre, is_active FROM QuizHeader WHERE is_active=1 ORDER BY date_time DESC").fetchall()
    else:
        rows = cursor.execute("SELECT id, per_create, date_time, no_ques, genre, is_active FROM QuizHeader ORDER BY date_time DESC").fetchall()
    connection.close()
    return rows

def get_quiz_header_by_id(hid):
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    row = cursor.execute("SELECT id, per_create, date_time, no_ques, genre, is_active FROM QuizHeader WHERE id=?", (hid,)).fetchone()
    connection.close()
    return row

def set_quiz_active(hid, active=True):
    """
    Set or unset a quiz header as active (active=True -> is_active=1).
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("UPDATE QuizHeader SET is_active=? WHERE id=?", (1 if active else 0, hid))
    connection.commit()
    connection.close()

    # -----------------------------
# Save quiz header + questions (linked)
# -----------------------------
def _ensure_quizquestions_has_quizid():
    """
    Ensure the QuizQuestions table has a 'quiz_id' column.
    If the column does not exist, add it (ALTER TABLE).
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    # Get table columns
    cols = [row[1] for row in cursor.execute("PRAGMA table_info('QuizQuestions')").fetchall()]
    if 'quiz_id' not in cols:
        try:
            cursor.execute("ALTER TABLE QuizQuestions ADD COLUMN quiz_id INTEGER")
            connection.commit()
        except Exception:
            # If ALTER fails, ignore - we still try insert without quiz_id
            pass
    connection.close()

def save_quiz_with_header(per_create, date_time, no_ques, genre, is_active, questions):
    """
    Save a quiz: insert a header row into QuizHeader and insert each question into QuizQuestions.
    - per_create: creator identifier (email/name)
    - date_time: integer timestamp (or string; will be converted to int if possible)
    - no_ques: number of questions (int)
    - genre: string (single or comma-separated)
    - is_active: truthy/falsey -> stored as 1/0
    - questions: list of dicts, each dict expected to contain:
        { "question": "...", "options": ["A) ...","B) ...","C) ...","D) ..."], "answer": "A", ... }
    Returns: header_id (the inserted QuizHeader.id)
    """
    # Ensure tables exist
    init_quiz_header_table()
    init_quiz_questions_table()
    # Ensure QuizQuestions has quiz_id column for linking
    _ensure_quizquestions_has_quizid()

    # Normalize date_time to int if possible
    try:
        date_time_int = int(date_time)
    except Exception:
        # try to parse ISO date string to timestamp (best-effort)
        try:
            from datetime import datetime
            # accept YYYY-MM-DD or full ISO; set time to 00:00 UTC if only date provided
            if isinstance(date_time, str) and len(date_time) == 10:
                dt = datetime.fromisoformat(date_time)
            else:
                dt = datetime.fromisoformat(date_time)
            date_time_int = int(dt.timestamp())
        except Exception:
            date_time_int = int(__import__('time').time())

    # Insert header row using existing helper if present
    header_id = None
    try:
        header_id = save_quiz_header(per_create, date_time_int, no_ques, genre, is_active)
    except Exception:
        # Fallback: insert directly if helper not found
        connection = get_db(QUIZ_DB)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO QuizHeader (per_create, date_time, no_ques, genre, is_active) VALUES (?, ?, ?, ?, ?)",
            (per_create, int(date_time_int), int(no_ques), genre, 1 if is_active else 0)
        )
        header_id = cursor.lastrowid
        connection.commit()
        connection.close()

    # Insert questions
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    for idx, q in enumerate(questions, start=1):
        # extract fields with safe defaults
        qstr = (q.get('question') or q.get('prompt') or "").strip()
        opts = q.get('options') or []
        # Normalize options to strings for A,B,C,D
        A = opts[0] if len(opts) > 0 else ""
        B = opts[1] if len(opts) > 1 else ""
        C = opts[2] if len(opts) > 2 else ""
        D = opts[3] if len(opts) > 3 else ""
        # Normalize answer to single letter A-D
        ans = (q.get('answer') or "A").strip().upper()
        if not re.match(r'^[A-D]$', ans):
            # try to recover from an index or text match
            if isinstance(ans, str) and ans.isdigit():
                # convert "1" -> A etc (1->A,2->B...)
                try:
                    n = int(ans)
                    if 1 <= n <= 4:
                        ans = chr(ord('A') + n - 1)
                    else:
                        ans = "A"
                except Exception:
                    ans = "A"
            else:
                ans = "A"

        # Insert with quiz_id if column exists
        cols = [row[1] for row in cursor.execute("PRAGMA table_info('QuizQuestions')").fetchall()]
        if 'quiz_id' in cols:
            cursor.execute(
                "INSERT INTO QuizQuestions (Qno, Qstr, A, B, C, D, CAns, quiz_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (idx, qstr, A, B, C, D, ans, header_id)
            )
        else:
            cursor.execute(
                "INSERT INTO QuizQuestions (Qno, Qstr, A, B, C, D, CAns) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (idx, qstr, A, B, C, D, ans)
            )

    connection.commit()
    connection.close()
    return header_id

def get_questions_by_quiz_id(quiz_id):
    """
    Return list of questions rows (Qid, Qno, Qstr, A, B, C, D, CAns, quiz_id) for a given quiz header id.
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    # If quiz_id column exists, fetch by it; otherwise return empty list
    cols = [row[1] for row in cursor.execute("PRAGMA table_info('QuizQuestions')").fetchall()]
    if 'quiz_id' in cols:
        rows = cursor.execute("SELECT Qid, Qno, Qstr, A, B, C, D, CAns, quiz_id FROM QuizQuestions WHERE quiz_id=? ORDER BY Qno ASC", (quiz_id,)).fetchall()
    else:
        rows = []
    connection.close()
    return rows