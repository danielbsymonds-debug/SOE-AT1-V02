import sqlite3
from datetime import datetime
import json

LOGIN_DB = "LoginData.db"
QUIZ_DB = "QuizData.db"

# -----------------------------
# User & OTP tables
# -----------------------------




def add_user(fname, lname, email, password):
    """Insert a new user."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO USERS(first_name,last_name,email,password) VALUES (?,?,?,?)",
                   (fname, lname, email, password))
    connection.commit()
    connection.close()


def get_users():
    """Return all users."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT * FROM USERS").fetchall()
    connection.close()
    return rows


def save_otp(email, otp):
    """Save or update OTP for a user."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("DELETE FROM USEROTP WHERE email=?", (email,))
    cursor.execute("INSERT INTO USEROTP(email, otp) VALUES (?, ?)", (email, otp))
    connection.commit()
    connection.close()


def check_otp(email, otp):
    """Check if OTP matches for a given email."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    ans = cursor.execute("SELECT * FROM USEROTP WHERE email=?", (email,)).fetchall()
    connection.close()
    return len(ans) > 0 and ans[0][1] == otp

# -----------------------------
# Quiz results table
# -----------------------------
def init_quiz_db():
    """Initialize QUIZ_RESULTS table."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QUIZ_RESULTS (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        subject TEXT,
        score INTEGER,
        total INTEGER
    )
    """)
    connection.commit()
    connection.close()


def save_quiz_result(email, subject, score, total):
    """Save a quiz result."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO QUIZ_RESULTS(email, subject, score, total) VALUES (?, ?, ?, ?)",
                   (email, subject, score, total))
    connection.commit()
    connection.close()


def get_user_results(email):
    """Get all quiz results for a user."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT * FROM QUIZ_RESULTS WHERE email=?", (email,)).fetchall()
    connection.close()
    return rows


def get_all_results():
    """Get all quiz results."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT * FROM QUIZ_RESULTS").fetchall()
    connection.close()
    return rows

# --- Admin table and daily scores helpers ---

def init_admin_table():
    """Create ADMIN table to store admin account(s)."""
    connection = sqlite3.connect(LOGIN_DB)
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


def add_admin(email, password, first_name=None, last_name=None):
    """Insert a new admin (use hashed password)."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT OR REPLACE INTO ADMIN(email, password, first_name, last_name) VALUES (?, ?, ?, ?)",
                   (email, password, first_name, last_name))
    connection.commit()
    connection.close()


def get_admins():
    """Return all admins."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT email, first_name, last_name FROM ADMIN").fetchall()
    connection.close()
    return rows


def init_daily_scores():
    """Create DAILY_SCORES table to store daily quiz scores (per user)."""
    connection = sqlite3.connect(QUIZ_DB)
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
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO DAILY_SCORES(fname, lname, email, score, date) VALUES (?, ?, ?, ?, ?)",
                   (fname, lname, email, score, date))
    connection.commit()
    connection.close()


def get_all_daily_scores():
    """Return all daily scores, ordered newest first."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT id, fname, lname, email, score, date FROM DAILY_SCORES ORDER BY date DESC").fetchall()
    connection.close()
    return rows


def get_user_by_email(email):
    """Return user (first_name, last_name, email) from USERS table (or None)."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()
    row = cursor.execute("SELECT first_name, last_name, email FROM USERS WHERE email=?", (email,)).fetchone()
    connection.close()
    return row

def init_admin_table():
    """Create ADMIN table to store admin account(s)."""
    connection = sqlite3.connect(LOGIN_DB)
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

def init_quizzes_table():
    """Create QUIZZES table to store scheduled/admin-generated quizzes."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QUIZZES (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        genres TEXT,
        num_questions INTEGER,
        created_by TEXT,
        questions TEXT
    )
    """)
    connection.commit()
    connection.close()

def save_quiz(date, genres, num_questions, created_by, questions):
    """Save a generated quiz (questions should be serializable)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO QUIZZES(date, genres, num_questions, created_by, questions) VALUES (?, ?, ?, ?, ?)",
        (date, json.dumps(genres), num_questions, created_by, json.dumps(questions))
    )
    connection.commit()
    connection.close()

def get_quiz_by_date(date):
    """Return the latest quiz for a given date (or None)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    row = cursor.execute("SELECT id, date, genres, num_questions, created_by, questions FROM QUIZZES WHERE date=? ORDER BY id DESC LIMIT 1", (date,)).fetchone()
    connection.close()
    return row

def get_latest_quiz():
    """Return the latest quiz saved (or None)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    row = cursor.execute("SELECT id, date, genres, num_questions, created_by, questions FROM QUIZZES ORDER BY id DESC LIMIT 1").fetchone()
    connection.close()
    return row

# -- QUIZZES table helpers (add to database.py) --


def init_quizzes_table():
    """Create QUIZZES table to store scheduled/admin-generated quizzes."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QUIZ_HEADER (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        genres TEXT,
        num_questions INTEGER,
        created_by TEXT,
        is_active BOOLEAN
    )
    """)
    connection.commit()
    connection.close()

def save_quiz(date, genres, num_questions, created_by, questions):
    """Save a generated quiz (questions should be serializable)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO QUIZZES(date, genres, num_questions, created_by, is_active) VALUES (?, ?, ?, ?, ?)",
        (date, json.dumps(genres), num_questions, created_by, json.dumps(questions))
    )
    connection.commit()
    connection.close()

def get_quiz_by_date(date):
    """Return the latest quiz for a given date (or None)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    row = cursor.execute(
        "SELECT id, date, genres, num_questions, created_by, is_active FROM QUIZZES WHERE date=? ORDER BY id DESC LIMIT 1",
        (date,)
    ).fetchone()
    connection.close()
    return row

def get_latest_quiz():
    """Return the latest quiz saved (or None)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    row = cursor.execute(
        "SELECT id, date, genres, num_questions, created_by, is_active FROM QUIZZES ORDER BY id DESC LIMIT 1"
    ).fetchone()
    connection.close()
    return row

# -----------------------------
# QuizQuestions and User_Result tables
# -----------------------------
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
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QuizQuestions (
        Qid INTEGER PRIMARY KEY AUTOINCREMENT,
        Qno INTEGER,
        Qstr TEXT,
        A TEXT,
        B TEXT,
        C TEXT,
        D TEXT,
        CAns TEXT
    )
    """)
    connection.commit()
    connection.close()

def save_quiz_question(qno, qstr, a, b, c, d, cans):
    """
    Insert a question row into QuizQuestions.
    Returns the inserted Qid.
    """
    connection = sqlite3.connect(QUIZ_DB)
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
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT Qid, Qno, Qstr, A, B, C, D, CAns FROM QuizQuestions ORDER BY Qno ASC").fetchall()
    connection.close()
    return rows

def get_question_by_qid(qid):
    connection = sqlite3.connect(QUIZ_DB)
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
    connection = sqlite3.connect(QUIZ_DB)
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
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO User_Result (user, Qid, Qno, Ans, correct_answer) VALUES (?, ?, ?, ?, ?)",
        (user, qid, qno, ans, 1 if correct else 0)
    )
    connection.commit()
    connection.close()

def get_user_results(user):
    """Return all User_Result rows for a given user (list of tuples)."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT id, user, Qid, Qno, Ans, correct_answer FROM User_Result WHERE user=? ORDER BY id DESC", (user,)).fetchall()
    connection.close()
    return rows

def get_results_for_question(qid):
    """Return all User_Result rows for a particular question id."""
    connection = sqlite3.connect(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT id, user, Qid, Qno, Ans, correct_answer FROM User_Result WHERE Qid=?", (qid,)).fetchall()
    connection.close()
    return rows