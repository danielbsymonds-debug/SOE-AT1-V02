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
database.init_quiz_db()
database.init_admin_table()
database.init_daily_scores()
database.init_quizzes_table() 

app = Flask(__name__)
app.jinja_env.globals.update(enumerate=enumerate)
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

@app.route('/admin', methods=['GET'])
@admin_required
def admin_dashboard():
    """Simple admin dashboard linking to admin pages."""
    return render_template('/admin_Dashboard')

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
    return render_template('admin_Quiz_Setup.html', schedules=schedules)


@app.route('/admin/quiz_setup', methods=['POST'])
@admin_required
def    admin_quiz_setup_post():
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

      # Build a subject/prompt for the AI from the chosen genres
    subject_prompt = ", ".join(normalized_genres).title()

    # Ask the AI to generate the questions: temporarily set the QuizAI instance fields
    old_subject = getattr(quiz_ai, 'subject', None)
    old_difficulty = getattr(quiz_ai, 'difficulty', None)
    quiz_ai.subject = subject_prompt
    quiz_ai.difficulty = "advanced"

    try:
        questions = quiz_ai.generate_questions(num_questions=num_q)
    except Exception as e:
        # restore before exiting
        quiz_ai.subject = old_subject
        quiz_ai.difficulty = old_difficulty
        flash(f"Failed to generate questions from AI: {e}")
        return redirect('/admin/quiz_setup')

    # restore original ai settings
    quiz_ai.subject = old_subject
    quiz_ai.difficulty = old_difficulty

    # Persist generated quiz to DB
    try:
        database.save_quiz(date_str, normalized_genres, num_q, session.get('user_email'), questions)
    except Exception as e:
        flash(f"Failed to save generated quiz: {e}")
        return redirect('/admin/quiz_setup')

    flash("Quiz scheduled and generated successfully.")
    return redirect('/admin/quiz_setup')

@app.route('/quiz/active', methods=['GET'])
def quiz_active():
    """Load today's quiz (or the latest) and present it to the user."""
    today = datetime.utcnow().date().isoformat()
    quiz_row = database.get_quiz_by_date(today)
    if not quiz_row:
        quiz_row = database.get_latest_quiz()
        if not quiz_row:
            flash("No active quiz is available right now.")
            return redirect('/home')

    # quiz_row: (id, date, genres, num_questions, created_by, questions)
    quiz_id, quiz_date, genres_json, num_q, created_by, questions_json = quiz_row
    try:
        questions = json.loads(questions_json)
    except Exception:
        # fallback if questions stored as a Python list string
        questions = quiz_row[5]

    # Store generated questions in session so submit_quiz can grade them
    session['questions'] = questions
    session['subject'] = f"Daily Quiz ({quiz_date})"
    print(questions)

    return render_template('quiz.html', subject=session['subject'], questions=questions)

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

@app.route('/login_validation', methods=['POST'])
def login_validation():
    email = request.form.get('email')
    password = request.form.get('password')
    action = request.form.get('action', 'login')  # 'login' or 'admin_login'

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
        authenticated = True
    elif stored_password == password:
        # migrate plaintext to hashed
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

        # Determine admin status:
        # 1) env var match
        admin_email = os.environ.get('ADMIN_EMAIL', '').strip()
        is_admin = (email == admin_email)

        # 2) OR present in ADMIN table
        if not is_admin:
            try:
                admins = database.get_admins()  # returns list of (email, first_name, last_name)
                if any(row[0] == email for row in admins):
                    is_admin = True
            except Exception:
                # if DB lookup fails, keep previous is_admin value (False)
                pass

        session['is_admin'] = is_admin

        # If admin button clicked, require that the user is actually an admin
        if action == 'admin_login':
            if session.get('is_admin'):
                return redirect('/admin')  # go to the admin dashboard route
            else:
                flash("Admin access required for that action")
                return redirect('/')

        # Regular login redirect
        return redirect(f'/home?fname={user_row[0]}&lname={user_row[1]}&email={user_row[2]}')
    else:
        password_Manager.log_event(f"Failed login attempt for {email} (bad password)")
        flash("Invalid credentials")
        return redirect('/')
    
@app.route('/admin/results', methods=['GET'])
@admin_required
def admin_results():
    """
    Load quiz results from the DB and group by user email.
    Pass a mapping `users` (email -> list of result dicts) to the template.
    """
    results = []
    try:
        results = database.get_all_results()  # returns rows like (id, email, subject, score, total)
    except Exception:
        results = []

    users = {}
    for r in results:
        # adapt to your QUIZ_RESULTS schema (id, email, subject, score, total)
        try:
            _id = r[0]
            email = r[1]
            subject = r[2] if len(r) > 2 else ''
            score = r[3] if len(r) > 3 else ''
            total = r[4] if len(r) > 4 else ''
        except Exception:
            continue

        # get first/last name from USERS table if available
        user = database.get_user_by_email(email)
        if user:
            fname, lname, _ = user[0], user[1], user[2]
        else:
            fname, lname = '', ''

        entry = {
            'id': _id,
            'email': email,
            'subject': subject,
            'score': score,
            'total': total,
            'fname': fname,
            'lname': lname,
            'timestamp': ''
        }
        users.setdefault(email, []).append(entry)

    return render_template('admin_results.html', users=users)

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
        # Temporarily set the AI's subject/difficulty for generation
        old_subject = getattr(quiz_ai, 'subject', None)
        old_difficulty = getattr(quiz_ai, 'difficulty', None)
        quiz_ai.subject = subject
        quiz_ai.difficulty = "advanced"

        try:
            questions = quiz_ai.generate_questions(num_questions=3)
        finally:
            # restore original settings
            quiz_ai.subject = old_subject
            quiz_ai.difficulty = old_difficulty

        # Store questions in session so we can grade later
        session['questions'] = questions
        session['subject'] = subject
        print(questions)
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
    