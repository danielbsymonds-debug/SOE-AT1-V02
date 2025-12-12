from flask import Flask, redirect, render_template, request, flash,session
import sqlite3
import os
import smtplib
from waitress import serve
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random
from flask_cors import CORS
from password_Manager import password_Manager
from AI import QuizAI
import functools
import json
from datetime import datetime
# initialize DBs/tables at startup
import database  # adjust import if you placed database.py elsewhere

# ensure DBs/tables exist
database.init_login_db()
database.init_quiz_db()
database.init_admin_table()
database.init_daily_scores()

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app) 
quiz_ai = QuizAI()

#---------- Routes -----------#

def admin_required(view_func):
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Admin access required")
            return redirect('/')  # or redirect('/login') depending on your flow
        return view_func(*args, **kwargs)
    return wrapper

@app.route('/admin/daily_scores', methods=['GET'])
@admin_required
def admin_daily_scores():
    rows = database.get_all_daily_scores()
    # rows are tuples (id, fname, lname, email, score, date)
    return render_template('admin_daily_scores.html', rows=rows)

@app.route('/admin/quiz_setup', methods=['GET'])
@admin_required
def admin_quiz_setup():
    # render form, loading last saved config if present
    schedules = []
    try:
        if os.path.exists('quiz_schedules.json'):
            with open('quiz_schedules.json', 'r', encoding='utf-8') as f:
                schedules = json.load(f)
    except Exception:
        schedules = []
    return render_template('admin_quiz_setup.html', schedules=schedules)


@app.route('/admin/quiz_setup', methods=['POST'])
@admin_required
def admin_quiz_setup_post():
    # Read form fields
    date_str = request.form.get('date')  # expected YYYY-MM-DD
    genres = request.form.getlist('genres')  # array of selected genres
    num_questions = request.form.get('num_questions', '').strip()

    # Basic validation
    errors = []
    if not date_str:
        errors.append("Date is required.")
    try:
        num_q = int(num_questions)
        if num_q <= 0:
            errors.append("Number of questions must be positive.")
    except Exception:
        errors.append("Number of questions must be an integer.")

    allowed_genres = {'sports', 'general', 'geography', 'history'}
    normalized_genres = []
    for g in genres:
        key = g.strip().lower()
        if key in allowed_genres:
            normalized_genres.append(key)

    if not normalized_genres:
        errors.append("Select at least one genre.")

    if errors:
        for e in errors:
            flash(e)
        return redirect('/admin/quiz_setup')

    # Persist schedule to JSON file
    entry = {
        'date': date_str,
        'genres': normalized_genres,
        'num_questions': num_q,
        'created_by': session.get('user_email')
    }

    schedules = []
    try:
        if os.path.exists('quiz_schedules.json'):
            with open('quiz_schedules.json', 'r', encoding='utf-8') as f:
                schedules = json.load(f)
    except Exception:
        schedules = []

    schedules.append(entry)

    try:
        with open('quiz_schedules.json', 'w', encoding='utf-8') as f:
            json.dump(schedules, f, indent=2)
    except Exception as e:
        flash("Failed to save schedule: " + str(e))
        return redirect('/admin/quiz_setup')

    flash("Quiz schedule saved.")
    return redirect('/admin/quiz_setup')

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/signUp')
def signUp():
    return render_template('signUp.html')

@app.route('/home')
def home():
    fname = request.args.get('fname')
    lname = request.args.get('lname')
    email = request.args.get('email')
    return render_template('home.html', fname=fname, lname=lname, email=email)

@app.route('/login_validation' ,methods=['POST'])
def login_validation():
    email = request.form.get('email')
    password = request.form.get('password')
    if email is None or password is None:
        flash("Email and password are required")
        return redirect('/')

    hashed_pw = password_Manager.hash_password(password)

    connection = sqlite3.connect('LoginData.db')
    cursor = connection.cursor()

    # Fetch user by email only
    user_row = cursor.execute("SELECT * FROM USERS WHERE email=?", (email,)).fetchone()

    if user_row is None:
        connection.close()
        password_Manager.log_event(f"Failed login attempt for {email} (no such user)")
        flash("Invalid credentials")
        return redirect('/')

    # Assume schema: (first_name, last_name, email, password, ...)
    stored_password = user_row[3] if len(user_row) > 3 else None

    # Check hashed match OR plain-text match (to support older records)
    if stored_password == hashed_pw:
        # good: stored password is hashed and matches
        authenticated = True
    elif stored_password == password:
        # stored password was plaintext; migrate it to hashed
        try:
            cursor.execute("UPDATE USERS SET password = ? WHERE email = ?", (hashed_pw, email))
            connection.commit()
            authenticated = True
            password_Manager.log_event(f"Migrated password to hashed for {email}")
        except Exception as e:
            authenticated = False
            password_Manager.log_event(f"Failed to migrate password for {email}: {e}")
    else:
        authenticated = False

    connection.close()

    if authenticated:
        password_Manager.log_event(f"{email} logged in successfully")
        # set session user info
        session['user_email'] = email
        # admin check via environment variable
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        session['is_admin'] = (email == admin_email)
        return redirect(f'/home?fname={user_row[0]}&lname={user_row[1]}&email={user_row[2]}')
    else:
        password_Manager.log_event(f"Failed login attempt for {email} (bad password)")
        flash("Invalid credentials")
        return redirect('/')
    
@app.route('/add_user', methods=['POST'])
def add_user():
    fname = request.form.get('fname')
    lname = request.form.get('lname')
    email = request.form.get('email')
    password = request.form.get('password')

    # Check the password strength
    is_valid, msg = password_Manager.is_strong_password(password)
    if not is_valid:
        return render_template('signUp.html', msg=msg)

    hashed_pw = password_Manager.hash_password(password)

    connection = sqlite3.connect('LoginData.db')
    cursor = connection.cursor()

    # Check by email only
    existing = cursor.execute("SELECT * from USERS where email=?",(email,)).fetchall()
    if len(existing) > 0:
        connection.close()
        return render_template('signUp.html', msg="User already exists")
    else:
        # Insert hashed password only
        cursor.execute(
            "INSERT INTO USERS(first_name,last_name,email,password) VALUES (?,?,?,?)",
            (fname, lname, email, hashed_pw)
        )
        connection.commit()
        connection.close()
        password_Manager.log_event(f"New user registered: {email}")
        return render_template('login.html')
    
@app.route('/forgot_page')
def forgot_page():
    return render_template('forgot-password.html')

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    global logged_mail
    logged_mail = ""
    email = request.form.get('email')
    logged_mail = email
    connection = sqlite3.connect('LoginData.db')
    cursor = connection.cursor()

    cmd1 = cursor.execute("SELECT * FROM USERS WHERE email=?", (email,)).fetchall()
    if len(cmd1) > 0:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        
        sender_email = "daniel.b.symonds@gmail.com"
        login = sender_email 
        
        password = "hxui wjwz adsz vycn"  # Your application-specific password
        receiver_email = email
        subject = "Your OTP Code"
        otp = generate_otp()
        cursor.execute("DELETE FROM USEROTP WHERE email = ?", (email,))
        connection.commit()
        cursor.execute("INSERT INTO USEROTP(email, otp) VALUES (?, ?)", (email, otp))
        connection.commit()
        connection.close()

        body = f"""
        <html>
        <head>
        <style>
            .box {{
            width: 600px;
            background-color: #83c9c5;
            padding: 20px;
            box-shadow: 10px 15px 10px black;
            border-radius: 10px;
            height: 100px;
            align-items: center;
            justify-content: center;
        }}
        .box p {{
            font-size: 1rem;
        }}
        .box strong {{
            font-size: 1.2rem;
            margin-left: 3px;
            margin-right: 3px;
            background: orange;
            color: black;
            padding: 5px;
            border-radius: 5px;
            letter-spacing: 0.5px;
            cursor: pointer;
            transition: 1.2s linear ease;
        }}
        .box strong:hover{{
            transform: scale(1.2);
        }}
        </style>
        </head>
        <body>
            <div class="box">
                <p>Your OTP code is <strong>{otp}</strong>.</p>
            </div>
        </body>
        </html>
        """
        send_email(sender_email, receiver_email, subject, body, smtp_server, smtp_port, login, password)
        flash("otp has been sent!")
        return render_template('forgot-password.html',sent="OTP has been sent!")
    else:
        msg = "Invalid email!"
        return render_template('forgot-password.html', sent=msg)

@app.route('/check_otp', methods=['POST'])
def check_otp():
    otp = request.form.get('otp')
    connection = sqlite3.connect('LoginData.db')
    cursor = connection.cursor()
    #logged_mail = session.get('logged_mail') 
    if logged_mail:
        ans = cursor.execute("SELECT * FROM USEROTP WHERE email=?", (logged_mail,)).fetchall()
        if len(ans) > 0 and otp == ans[0][1]:
            cursor.execute("DELETE FROM USEROTP WHERE email = ?", (logged_mail,))
            user = cursor.execute("SELECT * from USERS where email=?",(logged_mail,)).fetchall()
            connection.commit()
            connection.close()
            return redirect(f'/home?fname={user[0][0]}&lname={user[0][1]}&email={user[0][2]}')
        else:
            connection.close()
            return render_template('forgot-password.html', msg="Invalid OTP!")
        
@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if request.method == 'POST':
        subject = request.form.get('subject', 'General Knowledge')
        questions = quiz_ai.generate_questions(subject=subject, difficulty="advanced", num_questions=3)

        # Store questions in session so we can grade later
        session['questions'] = questions
        session['subject'] = subject
        return render_template('quiz.html', subject=subject, questions=questions)

    return render_template('quiz_select.html')  # page with subject input form

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    questions = session.get('questions', [])
    subject = session.get('subject', 'General Knowledge')
    user_answers = []

    for i in range(len(questions)):
        user_answers.append(request.form.get(f"q{i+1}", ""))

    score, total = quiz_ai.grade(questions, user_answers)

    # Save to QUIZ_RESULTS (existing helper)
    user_email = session.get('user_email', 'anonymous')
    try:
        database.save_quiz_result(user_email, subject, score, total)
    except Exception as e:
        # non-fatal: log or flash
        flash(f"Failed to save quiz result to DB: {e}")

    # Save a DAILY_SCORES entry (include fname/lname if available)
    user = database.get_user_by_email(user_email)
    if user:
        fname, lname, email = user[0], user[1], user[2]
    else:
        # fallback: try to get from session or mark anonymous
        fname = session.get('fname', '')
        lname = session.get('lname', '')
        email = user_email

    try:
        database.save_daily_score(fname, lname, email, score)
    except Exception as e:
        flash(f"Failed to save daily score: {e}")

    flash(f'Quiz submitted — Score: {score}/{total}')
    return redirect('/home')


#--------- Utility ---------#
def generate_otp():
    """Generate a 6-digit OTP."""
    otp = random.randint(100000, 999999)
    return otp

def send_email(sender_email, receiver_email, subject, body, smtp_server, smtp_port, login, password):
    """Send an email with the specified parameters."""
    # Create the email message object
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Attach the HTML email body
    msg.attach(MIMEText(body, 'html'))

    try:
        # Establish connection to the server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade to secure connection
        server.login(login, password)
        
        # Send the email
        server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Email sent successfully")
        server.quit()
        
    except Exception as e:
        print(f"Failed to send email: {e}")   

if __name__ == '__main__':
    app.run(debug=True)
    