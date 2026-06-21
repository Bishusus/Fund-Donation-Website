import os

from cs50 import SQL
from flask import Flask,flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from email_validator import validate_email, EmailNotValidError
from helpers import apology, login_required, usd
from datetime import datetime
app = Flask(__name__)

app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

db = SQL("sqlite:///fund.db")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/donate", methods=["GET","POST"])
def donate():
    if request.method == "POST":
        fund_name=request.form.get("fund","").strip()
        if fund_name:
            query="%"+fund_name+"%"
            funds=db.execute("SELECT * FROM funds WHERE name LIKE ?",query)
        else:
            funds=[]
        return render_template("donate.html",funds=funds)
    else:
        funds=db.execute("SELECT * FROM funds LIMIT 5")
        return render_template("donate.html",funds=funds)

@app.route("/search", methods=["GET","POST"])
def search():
    name=request.args.get("fund","").strip()
    if name:
        query = f"%{name}%"
        funds=db.execute("SELECT * FROM funds WHERE name LIKE ? LIMIT 10 ",query)
        return jsonify(funds)
    return jsonify([])

@app.route("/validity", methods=["GET","POST"])
@login_required
def valid():
    if request.method == "POST":
        id=session["user_id"]
        fund_id=request.form.get("fund_id")
        fund_name=request.form.get("fund_name")
        email=request.form.get("email")
        password=request.form.get("password")
        password_confirm=request.form.get("confirm")
        credit_card=request.form.get("credits")
        amount=request.form.get("amount")
        if not email or not password or not password_confirm or not credit_card or not amount:
            return apology("Please enter the details as specified")
        if password != password_confirm:
            return apology("The passwords do not match")
        try:
            valid = validate_email(email)
            email=valid.normalized
        except EmailNotValidError:
            return apology("Invalid email")
        fix=db.execute("SELECT * FROM users WHERE id=?",id)
        if len(fix)!=1:
            return apology("Account with the email not found")
        if fix[0]["email"]!=email:
            return apology("Email of the logged in user and the entered email do not match")
        if not check_password_hash(fix[0]["hash"],password):
            return apology("Invalid password")
        credit_card = ''.join(filter(str.isdigit, credit_card))
        def confirm_credit(credit_card):
            flag=False
            sum=0
            for i in range(len(credit_card) - 1,-1,-1):
                digit=int(credit_card[i])
                if flag:
                    digit=digit*2
                    if digit>9:
                        digit-=9
                sum += digit
                flag= not flag
            return sum % 10 == 0
        message=confirm_credit(credit_card)
        if not message:
            return apology("Invalid credit card")
        try:
            amount=float(amount)
        except ValueError:
            return apology("Inavlid amount")
        if amount<1:
            return apology("Amount cannot be negative")
        db.execute("INSERT INTO donations(user_id,fund_id,fund_name,email,amount) VALUES (?,?,?,?,?)",id,fund_id,fund_name,email,amount)
        flash("Thank you for you donation")
        return redirect("/")
    else:
        return render_template("donate.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email=request.form.get("email")
        password=request.form.get("password")
        confirmpass=request.form.get("confirmation")
        if not email or not password or not confirmpass:
            return apology("Please fill out all the boxes as requested")
        try:
            valid=validate_email(email)
            email=valid.normalized
        except EmailNotValidError:
            return apology("Email is not valid")
        if password != confirmpass:
            return apology("Passwords do not match")
        duplicate=db.execute("SELECT email FROM users WHERE email=?",email)
        if len(duplicate):
            return apology("Email already exists.")
        hash=generate_password_hash(password)
        db.execute("INSERT INTO users(hash,email) VALUES (?,?)",hash,email)
        session["user_id"] = db.execute(
            "SELECT id FROM users WHERE email = ? ",email)[0]["id"]
        flash("Registration successful!")
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        session.clear()
        email=request.form.get("email")
        password=request.form.get("password")
        if not email or not password:
            return apology("Please fill out the boxes as requested")
        try:
            valid=validate_email(email)
            email=valid.normalized
        except EmailNotValidError:
            return apology("Email is not valid")
        sure=db.execute("SELECT * FROM users WHERE email=?",email)
        if len(sure) != 1 or not check_password_hash(sure[0]["hash"], password):
            return apology("Invalid username or password")
        session["user_id"]=sure[0]["id"]
        flash("Log In successful!")
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/reset", methods=["GET","POST"])
def reset():
    if request.method == "POST":
        email=request.form.get("email")
        if not email:
            return apology("Please enter a valid email")
        valid=db.execute("SELECT * FROM users WHERE email=?",email)
        if len(valid)!=1:
            flash("If such email is registered in the system, you will receive a link")
            return redirect("/reset")
        session["reset_email"] = email
        return redirect("/forgot")
    else:
        return render_template("reset.html")

@app.route("/forgot", methods=["GET","POST"])
def forgot():
    email=session.get("reset_email")
    if request.method == "POST":
        password=request.form.get("password")
        currentpass=request.form.get("confirmpassword")
        if not password or not currentpass:
            return apology("Please fill out both the boxes")
        if password != currentpass:
            return apology("Passwords do not match")
        hash_new=generate_password_hash(password)
        db.execute("UPDATE users SET hash = ? WHERE email = ?", hash_new, email)
        flash("Password changed successfully")
        return redirect("/")
    else:
        return render_template("forgot.html")

@app.route("/history", methods=["GET","POST"])
def history():
    id=session.get("user_id")
    if not id:
        flash("Please log in to view your donation history.")
        return redirect("/login")
    history = db.execute("SELECT * FROM donations WHERE user_id=?",id)
    for improve in history:
        improve["amount"]=usd(improve["amount"])
        dt = datetime.strptime(improve["donated_at"], "%Y-%m-%d %H:%M:%S")
        improve["donated_at"] = dt.strftime("%b %d, %Y")
    return render_template("history.html",history=history)


@app.route("/logout", methods=["GET","POST"])
def logout():
    session.clear()
    flash("You have been logged out")
    return redirect("/")
