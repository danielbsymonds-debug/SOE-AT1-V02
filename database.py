import sqlite3

LOGIN_DB = "LoginData.db"
QUIZ_DB = "QuizData.db"

# -----------------------------
# User & OTP tables
# -----------------------------
def init_login_db():
    """Initialize USERS and USEROTP tables."""
    connection = sqlite3.connect(LOGIN_DB)
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS USERS(
        first_name VARCHAR(50),
        last_name VARCHAR(50),
        email VARCHAR(50) PRIMARY KEY,
        password VARCHAR(50) NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS USEROTP(
        email VARCHAR(50) PRIMARY KEY REFERENCES USERS(email),
        otp VARCHAR(6)
    )
    """)

    connection.commit()
    connection.close()


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