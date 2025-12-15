import sqlite3
import os
import password_Manager
import json
from datetime import datetime

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


# -----------------------------
# Quiz results table
# -----------------------------
def init_quiz_db():
    """Initialize QUIZ_RESULTS table."""
    cursor = get_db(QUIZ_DB).cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QUIZ_RESULTS (
        Qid ,
        email TEXT,
        subject TEXT,
        score INTEGER,
        total INTEGER,
        primary key (Qid,email)
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
""" def init_quiz_header_table():
    
    Create QuizHeader table to store quiz-level metadata.
    Columns:
      id        INTEGER PRIMARY KEY AUTOINCREMENT
      per_create TEXT       -- creator identifier (email/name)
      date_time  INTEGER    -- unix timestamp (seconds) for date/time of quiz
      no_ques    INTEGER    -- number of questions in the quiz
      genre      TEXT       -- genre or comma-separated genres
      is_active  INTEGER    -- 0/1 -> boolean (1 = active)
    
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()

    cursor.execute(
    CREATE TABLE IF NOT EXISTS QuizHeader (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        per_create TEXT,
        date_time INTEGER,
        no_ques INTEGER,
        genre TEXT,
        is_active INTEGER
    )
    )
    connection.commit()
    connection.close() """

# --- Admin table helpers ---

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
    """
    Insert a new QUIZ_HEADER row and mark it active.
    Before inserting, clear any existing active QUIZ_HEADER rows (is_active = 1 -> 0).
    """
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    try:
        # Try to deactivate any currently active QUIZ_HEADER entries (if column/table exists)
        try:
            cursor.execute("UPDATE QUIZ_HEADER SET is_active = 0 WHERE is_active = 1")
        except Exception:
            # QUIZ_HEADER or is_active may not exist in older schemas — ignore safely
            pass

        # Insert new header (legacy schema used elsewhere in this codebase)
        cursor.execute(
            "INSERT INTO QUIZ_HEADER(date,num_questions, genres, created_by, is_active) VALUES (?,?,?,?,?)",
            (dateCreated, noQues, genre, createdBy, 1)
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()



def save_quiz_result(Qid, email, subject, score, total):
    """Save a quiz result."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    cursor.execute("INSERT INTO QUIZ_RESULTS(Qid, email, subject, score, total) VALUES (?,?, ?, ?, ?)",
                   (Qid, email, subject, score, total))
    connection.commit()
    connection.close()


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



def get_quiz_questions():
    """Return all QuizQuestions rows (list of tuples)."""
    connection = get_db(QUIZ_DB)
    cursor = connection.cursor()
    rows = cursor.execute("SELECT Qid, Qno, Qstr, A, B, C, D, CAns FROM QuizQuestions ORDER BY Qno ASC").fetchall()
    connection.close()
    return rows


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


def _get_db_path():
    return os.path.join(os.path.dirname(__file__), 'LoginData.db')

def ensure_users_table():
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS USERS(
                first_name TEXT,
                last_name TEXT,
                email TEXT UNIQUE,
                password TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

def ensure_userotp_table():
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS USEROTP(
                email TEXT UNIQUE,
                otp TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

def ensure_user_result_table():
    db = _get_db_path()
    conn = sqlite3.connect(QUIZ_DB)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS User_result(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                quiz_id INTEGER,
                answers TEXT, -- JSON string of user's answers
                timestamp TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()

def ensure_quiz_results_table():
    db = _get_db_path()
    conn = sqlite3.connect(QUIZ_DB)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results(
                Qid INTEGER,
                email TEXT,
                subject TEXT,
                score INTEGER,
                total INTEGER,
                timestamp TEXT,
                    primary key (Qid,email)
            )
        """)
        conn.commit()
    finally:
        conn.close()

# keep existing user helpers (user_exists, insert_user) if present
def user_exists(email):
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM USERS WHERE email = ?", (email,))
        return cur.fetchone() is not None
    finally:
        conn.close()

def insert_user(first_name, last_name, email, hashed_password):
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO USERS(first_name,last_name,email,password) VALUES (?,?,?,?)",
                (first_name, last_name, email, hashed_password)
            )
            conn.commit()
            return True, None
        except sqlite3.IntegrityError:
            return False, "User already exists"
        except Exception as e:
            return False, str(e)
    finally:
        conn.close()

# Authentication helper (migrates plaintext password to hashed if needed)
def authenticate_user(email, password):
    
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM USERS WHERE email = ?", (email,))
        user_row = cur.fetchone()
        if not user_row:
            return False, None, "no such user"

        stored_password = user_row[3] if len(user_row) > 3 else None

        if stored_password == password:
            return True, user_row, None
        else:
            return False, None, "bad password"
    finally:
        conn.close()

# OTP helpers
def set_user_otp(email, otp):
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM USEROTP WHERE email = ?", (email,))
        cur.execute("INSERT INTO USEROTP(email, otp) VALUES (?, ?)", (email, str(otp)))
        conn.commit()
    finally:
        conn.close()

def get_user_otp(email):
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT otp FROM USEROTP WHERE email = ?", (email,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def delete_user_otp(email):
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM USEROTP WHERE email = ?", (email,))
        conn.commit()
    finally:
        conn.close()

# ensure tables exist on import
ensure_users_table()
ensure_userotp_table()
ensure_user_result_table()
ensure_quiz_results_table()

def get_active_quiz():
    """
    Return the active quiz header as a dict or None.
    Expected quiz_header columns: id, date, genres, num_questions, created_by, is_active (boolean/int)
    """
    db_path = os.path.join(os.path.dirname(__file__), QUIZ_DB)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, date, genres, num_questions, created_by FROM QUIZ_HEADER WHERE is_active = 1 LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'date': row[1],
            'genres': row[2],
            'num_questions': row[3],
            'created_by': row[4]
        }
    finally:
        conn.close()

def get_quiz_questions(quiz_id):
    """
    Return a list of question dicts for the given quiz header id (Qid).
    Each dict contains keys: question_no, question, answer1..answer4, correct_answer_number
    """
    db_path = os.path.join(os.path.dirname(__file__), QUIZ_DB)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT Qno, Qstr, A, B, C, D, CAns
            FROM QuizQuestions
            WHERE Qid = ?
            ORDER BY Qno
        """, (quiz_id,))
        rows = cur.fetchall()
        questions = []
        for r in rows:
            questions.append({
                'question_no': r[0],
                'question': r[1],
                'answer1': r[2],
                'answer2': r[3],
                'answer3': r[4],
                'answer4': r[5],
                'correct_answer_number': r[6]
            })
        return questions
    finally:
        conn.close()

def save_user_answers(email, quiz_id, answers_json):
    """
    Persist a user's per-question answers into the User_Result table.

    answers_json should be a JSON string like:
      [ {"selected":"1","correct":"2"}, {"selected":"3","correct":"3"}, ... ]

    This will insert one row per question into User_Result using columns:
      user, Qid, Qno, Ans, correct_answer
    """
    # ensure target table exists (matches init_user_result_table schema)
    connection = get_db(QUIZ_DB)
    try:
        cur = connection.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS User_Result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                Qid INTEGER,
                Qno INTEGER,
                Ans TEXT,
                correct_answer INTEGER
            )
        """)
        # parse JSON
        try:
            items = json.loads(answers_json)
            if not isinstance(items, list):
                items = list(items)
        except Exception as e:
            # malformed JSON -> nothing to save
            connection.close()
            raise ValueError(f"Invalid answers_json: {e}")

        # insert each answer as a separate row
        for idx, item in enumerate(items, start=1):
            # accept dicts that may contain different keys
            if isinstance(item, dict):
                selected = item.get('selected', '') or item.get('Ans', '') or ''
                correct = item.get('correct', '') or item.get('correct_answer', '') or ''
            else:
                # if item is just a primitive, treat as selected value
                selected = item
                correct = ''

            # normalize to strings for comparison
            sel_str = str(selected).strip()
            corr_str = str(correct).strip()

            correct_flag = 1 if (sel_str != "" and corr_str != "" and sel_str == corr_str) else 0

            cur.execute(
                "INSERT INTO User_Result(user, Qid, Qno, Ans, correct_answer) VALUES (?, ?, ?, ?, ?)",
                (email, quiz_id, idx, sel_str, correct_flag)
            )

        connection.commit()
        return True
    finally:
        connection.close()

def get_user_answers_for_quiz(user_email, quiz_id):
    """
    Return list of rows (Qno, Ans, correct_answer) for the given user and quiz id,
    ordered by Qno ascending. Returns empty list if none.
    """
    connection = get_db(QUIZ_DB)
    try:
        cur = connection.cursor()
        rows = cur.execute(
            "SELECT Qno, Ans, correct_answer FROM User_Result WHERE user=? AND Qid=? ORDER BY Qno ASC",
            (user_email, quiz_id)
        ).fetchall()
        return rows
    finally:
        connection.close()

def has_user_completed_quiz(user_email, quiz_id):
    """Return True if the user has at least one User_Result row for the quiz."""
    rows = get_user_answers_for_quiz(user_email, quiz_id)
    return len(rows) > 0