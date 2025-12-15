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
from types import SimpleNamespace
# initialize DBs/tables at startup
import database  # adjust import if you placed database.py elsewhere

# ensure DBs/tables exist
database.init_quiz_db()
database.init_admin_table()
database.init_quiz_questions_table()
database.init_user_result_table()

app = Flask(__name__)
app.config['DEBUG'] = True
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

# new: simple login_required decorator to protect routes that need an authenticated user
def login_required(view_func):
	@functools.wraps(view_func)
	def wrapper(*args, **kwargs):
		if not session.get('user_email'):
			flash("Please log in to access that page.")
			return redirect('/')  # send to login
		return view_func(*args, **kwargs)
	return wrapper

@app.route('/admin', methods=['GET'])
@admin_required
def admin_dashboard():
    """Simple admin dashboard linking to admin pages."""
    return render_template('/admin_Dashboard')

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
def admin_quiz_setup_post():
    # Read form fields
    genres = request.form.getlist('genres')  # array of selected genres
    num_questions = request.form.get('num_questions', '').strip()
    quizJson = request.form.get('QuizJson', '').strip()
    # Basic validation
    errors = []
    
    try:
        num_q = int(num_questions)
        if num_q <= 0:
            errors.append("Number of questions must be positive.")
    except Exception:
        errors.append("Number of questions must be an integer.")

    allowed_genres = {'sports', 'general knowledge', 'geography', 'history'}
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


#need to link this with item creation
    HeaderId = database.create_quiz_head(request.form.get('date'), num_questions, request.form.getlist('genres')[0] , "")

    try:
        questions = quiz_ai.generate_questions(generated=quizJson)
    except Exception as e:
        last_exception = e
        questions = None

    for q in questions: 
        database.create_item_line(HeaderId, q["question no"], q["question"] , q["answer1"], q["answer2"], q["answer3"], q["answer4"], q["correct answer number"])   

    if not questions:
        msg = f"Failed to generate valid questions from AI."
        if last_exception:
            msg += f" Error: {last_exception}"
        flash(msg)
        return redirect('/admin/quiz_setup')

    flash("Quiz scheduled and generated successfully.")
    return redirect('/admin/quiz_setup')

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/signUp')
def signUp():
    return render_template('signUp.html')

@app.route('/home')
@login_required
def home():
	fname = request.args.get('fname') or session.get('fname')
	lname = request.args.get('lname') or session.get('lname')
	email = request.args.get('email') or session.get('user_email')
	return render_template('home.html', fname=fname, lname=lname, email=email)

@app.route('/login_validation', methods=['POST'])
def login_validation():
    email = request.form.get('email')
    password = request.form.get('password')
    action = request.form.get('action', 'login')  # 'login' or 'admin_login'

    if email is None or password is None:
        flash("Email and password are required")
        return redirect('/')

    # delegate authentication to database helper (which handles hashing/migration)
    try:
        hashed_pw = password_Manager.hash_password(password)
        authenticated, user_row, msg = database.authenticate_user(email, hashed_pw)
    except Exception as e:
        password_Manager.log_event(f"Error during auth for {email}: {e}")
        flash("Invalid credentials")
        return redirect('/')

    if not authenticated:
        password_Manager.log_event(f"Failed login attempt for {email} ({msg})")
        flash("Invalid credentials")
        return redirect('/')

    # authenticated
    password_Manager.log_event(f"{email} logged in successfully")
    session['user_email'] = email

    # Determine admin status:
    admin_email = os.environ.get('ADMIN_EMAIL', '').strip()
    is_admin = (email == admin_email)

    if not is_admin:
        try:
            admins = database.get_admins()
            if any(row[0] == email for row in admins):
                is_admin = True
        except Exception:
            pass

    session['is_admin'] = is_admin

    if action == 'admin_login':
        if session.get('is_admin'):
            return redirect('/admin')
        else:
            flash("Admin access required for that action")
            return redirect('/')

    # Regular login redirect (user_row expected shape: first_name,last_name,email,...)
    return redirect(f'/home?fname={user_row[0]}&lname={user_row[1]}&email={user_row[2]}')

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
        # return the entered values so the form can be pre-filled and show the message
        flash(msg)
        return render_template('signUp.html', fname=fname, lname=lname, email=email, msg=msg)

    hashed_pw = password_Manager.hash_password(password)

    # Use database helpers instead of direct SQL here
    try:
        # check exists (database layer will talk to sqlite)
        if database.user_exists(email):
            msg = "User already exists"
            flash(msg)
            return render_template('signUp.html', fname=fname, lname=lname, email=email, msg=msg)

        success, err = database.insert_user(fname, lname, email, hashed_pw)
        if not success:
            # insert_user returns nice error strings for common cases
            flash(err or "Failed to create user")
            return render_template('signUp.html', fname=fname, lname=lname, email=email, msg=err)
    except Exception as e:
        # unexpected error
        flash(f"Error creating user: {e}")
        return render_template('signUp.html', fname=fname, lname=lname, email=email, msg=str(e))

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

    # use database helper to check existence and store OTP
    if database.user_exists(email):
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        sender_email = "daniel.b.symonds@gmail.com"
        login = sender_email
        password = "hxui wjwz adsz vycn"  # Your application-specific password
        receiver_email = email
        subject = "Your OTP Code"
        otp = generate_otp()

        # store OTP via database helper
        try:
            database.set_user_otp(email, otp)
        except Exception as e:
            flash("Failed to create OTP. Try again.")
            return redirect('/forgot_page')

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
        flash("OTP has been sent!")
        return redirect('/forgot_page')
    else:
        flash("Invalid email!")
        return redirect('/forgot_page')

@app.route('/check_otp', methods=['POST'])
def check_otp():
    otp = request.form.get('otp')
    #logged_mail = session.get('logged_mail') 
    if logged_mail:
        stored = database.get_user_otp(logged_mail)
        if stored and str(otp) == str(stored):
            # valid OTP: delete and redirect to home
            database.delete_user_otp(logged_mail)
            user = database.get_user_by_email(logged_mail)
            if user:
                return redirect(f'/home?fname={user[0]}&lname={user[1]}&email={user[2]}')
            else:
                flash("User not found after OTP verification")
                return redirect('/forgot_page')
        else:
            flash("Invalid OTP!")
            return redirect('/forgot_page')
    else:
        flash("No email in progress for OTP verification")
        return redirect('/forgot_page')

@app.route('/quiz', methods=['GET', 'POST'])
@login_required
def quiz():

    # GET: load the active quiz from DB (quiz_header.is_active = 1)
    active = database.get_active_quiz()
    if not active:
        flash("No active quiz is available right now.")
        return redirect('/home')

    quiz_id = active['id']
    questions = database.get_quiz_questions(quiz_id)

    # store for grading
    session['questions'] = questions
    session['quiz_id'] = quiz_id
    session['subject'] = f"Daily Quiz"

    # If user is logged in, check if they already have entries for this quiz.
    user_email = session.get('user_email')
    if user_email:
        try:
            saved = database.get_user_answers_for_quiz(user_email, quiz_id)
        except Exception:
            saved = []

        if saved:
            # saved is list of tuples (Qno, Ans, correct_answer)
            # build a mapping Qno -> saved data
            saved_map = {int(r[0]): {'Ans': str(r[1]), 'correct_flag': int(r[2]) if r[2] is not None else 0} for r in saved}

            # construct per_question_results similar to submit_quiz review mode
            per_question_results = []
            score = 0
            total = len(questions)
            for q in questions:
                qno = int(q.get('question_no', 0))
                answers = [
                    q.get('answer1', ''),
                    q.get('answer2', ''),
                    q.get('answer3', ''),
                    q.get('answer4', '')
                ]
                # original correct answer number from QuizQuestions (may be '1'..'4' or other)
                raw_correct = q.get('correct_answer_number') or q.get('CAns') or ''
                try:
                    correct_str = str(int(raw_correct))
                except Exception:
                    correct_str = str(raw_correct)

                saved_row = saved_map.get(qno, {})
                selected = saved_row.get('Ans', '')
                # Determine correctness by comparing selected to correct_str (if stored as indexes)
                is_correct = False
                try:
                    if selected != "" and correct_str != "":
                        is_correct = str(selected) == str(correct_str)
                except Exception:
                    is_correct = False

                if is_correct:
                    score += 1

                per_question_results.append({
                    'question_no': qno,
                    'question': q.get('question'),
                    'answers': answers,
                    'selected': selected,
                    'correct': correct_str,
                    'is_correct': is_correct
                })

            # Render review view (locked)
            return render_template('quiz.html', subject=session['subject'],
                                   questions=per_question_results, review=True, score=score, total=total)

    # No saved answers found -> normal quiz display
    return render_template('quiz.html', subject=session['subject'], questions=questions)

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    # load questions that were presented
    questions = session.get('questions', [])
    subject = session.get('subject', 'General Knowledge')
    quiz_id = session.get('quiz_id', None)
    user_email = session.get('user_email', 'anonymous')

    # collect user answers in same order as questions
    user_answers = []
    for i in range(len(questions)):
        ans = request.form.get(f"q{i+1}", "")  # radio value like "1","2","3","4" or ""
        user_answers.append(ans)

    # grade locally by comparing to question's correct answer
    score = 0
    total = len(questions)
    per_question_results = []  # list of dicts with selected, correct, choices
    for idx, q in enumerate(questions):
        # accept either 'correct_answer_number' key (from earlier helpers) or 'CAns'
        correct = q.get('correct_answer_number') or q.get('CAns') or q.get('cans') or q.get('CAns')
        try:
            correct = str(int(correct))  # normalize to string '1'..'4'
        except Exception:
            correct = str(correct) if correct is not None else ""

        selected = str(user_answers[idx]) if idx < len(user_answers) else ""
        is_correct = (selected == correct) and selected != ""
        if is_correct:
            score += 1

        per_question_results.append({
            'question_no': q.get('question_no', idx+1),
            'question': q.get('question'),
            'answers': [
                q.get('answer1', ''),
                q.get('answer2', ''),
                q.get('answer3', ''),
                q.get('answer4', '')
            ],
            'selected': selected,
            'correct': correct,
            'is_correct': is_correct
        })

    # Persist results: user answers and quiz score
    try:
        # save per-question answers as JSON string
        import json as _json
        answers_json = _json.dumps([{'selected': r['selected'], 'correct': r['correct']} for r in per_question_results])
        database.save_user_answers(user_email, quiz_id, answers_json)
    except Exception as e:
        # non-fatal, log/flash
        flash(f"Failed to save user answers: {e}")

    try:
        # save summary score into quiz_results table (keeps existing helper name)
        database.save_quiz_result(quiz_id, user_email, subject, score, total)
    except Exception as e:
        flash(f"Failed to save quiz result: {e}")

    # Re-render the quiz page in review mode with highlights and inputs disabled
    flash(f'Quiz submitted — Score: {score}/{total}')
    return render_template('quiz.html', subject=subject, questions=per_question_results, review=True, score=score, total=total)

#@app.teardown_appcontext
#def teardown():
#    database.close_db(e=None)

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
        print("Failed to send email: {e}")   

if __name__ == '__main__':
    app.run()
