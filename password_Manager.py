import re #import regular expression module
import hashlib # import hashlib module
from datetime import datetime

class password_Manager:
# Function to hash password

    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()


# Password cheker Function

    def is_strong_password(password):
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"

        if not re.search(r"[0-9]", password):
            return False, "Password must contain at least one number"

        if not re.search(r"[!@#$%^&*(),-_:.?\"{}|<>]", password):
            return False, "Password must contain at least one special character"

        return True, "Password is strong"

                        
    # Function to log user activity
    def log_event(event):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("audit_log.txt", "a") as log_file:
            log_file.write(f"{timestamp} - {event}\n")


                        
        # Registration Function

    def Register_user(is_strong_password, hash_password, log_event):
        username = input("Enter a username: ")
        password = input("Enter a password: ")

        is_valid, message = is_strong_password(password)
        if not is_valid:
            print("Password is not strong enough:")
            print(message)
            return

        
        #Hash the password
        hashed_password = hash_password(password)

        with open("users.txt", "a") as file:
            file.write(f"{username}:{hashed_password}\n")
        print("Registration successful!")
        log_event(f"{username} registered successfully")


        # Login Function

    def login_user(post_Login_Menu, log_event, hash_password):
        username = input("Enter your Username: ")
        password = input("Enter your Password: ")
        
        with open("users.txt", "r") as file:
            users = file.readlines()

        for user in users:
            stored_username, stored_password = user.strip().split(":")
        if username == stored_username and hash_password(password) == stored_password:
            print("Login successful!")
            log_event(f"{username} logged in successfully")
            post_Login_Menu(username)
            
            return
            
        print("Invalid Username or Password")
        log_event(f"Failed login attempt for {username}")

        # funnction to  display Post Login Menu

    def post_Login_Menu(username, view_logs, log_event):
        while True:
            print("\nPost Login Menu")
            print("1. View My Logs")
            print("2. Logout")
            choice = input("What would you like to do? ")

            if choice == "1":
                view_logs(username)
            elif choice == "2":
                log_event(f"User '{username}' logged out")
                print("Logging out Successfully")
                break
            else:
                print("Invalid choice, please try again")

        # Function to view logs

    def view_logs(username):
        print(f"\nLogs for user '{username}'")
        with open("audit_log.txt", "r") as log_file:
            logs = log_file.readlines()

        user_logs = [log.strip() for log in logs if username in log]

        if user_logs:
            for log in user_logs:
                print(log)

        else:
            print("No logs found were found for this user")

    def main(Register_user, login_user, log_event):
        while True:
            print("welcome to User Registration")
            print("1. Register")
            print("2. Login")
            print("3. Exit")
            choice = input("What would you like to do? ")

            if choice == "1":
                Register_user()

            elif choice == "2":
                login_user()

            elif choice == "3":
                log_event("System exited")
                print("Exiting the system")
                break
            else:
                print("Invalid choice, please try again")

password_Manager()
