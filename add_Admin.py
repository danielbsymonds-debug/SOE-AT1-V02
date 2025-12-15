# add_admin.py — run once to add the admin account
from password_Manager import password_Manager
import database

email = "daniel.b.symonds@gmail.com"
plain_pw = "STARWARS"
first_name = "daniel"
last_name = "symonds"

hashed = password_Manager.hash_password(plain_pw)
database.add_user(email=email, password=hashed, fname=first_name, lname=last_name)
print("Admin created/updated:", email)
print("Note: change the password after first login for security.")