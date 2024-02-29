import os
import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, is_valid_password

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    trades = db.execute(
        "SELECT symbol, sum(shares) as sum_shares FROM trades WHERE user_id = ? GROUP BY symbol",
        session["user_id"],
    )
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    # Get the current price of the stocks and total values
    total = 0
    for trade in trades:
        quote = lookup(trade["symbol"])
        trade["price"] = quote["price"]
        trade["value"] = trade["sum_shares"] * trade["price"]
        total = total + trade["value"]

    return render_template("index.html", trades=trades, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # Ensure fields are completed
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        if not symbol:
            return apology("must provide symbol", 400)
        elif not shares or not shares.isdigit() or int(shares)<=0:
            return apology("invalid shares", 400)

        # Ensure symbol exist
        stock_info = lookup(symbol)
        if stock_info == None:
            return apology("Invalid symbol", 400)

        # Ensure there are funds
        price_stock = stock_info["price"]
        cost_of_stock = int(shares) * price_stock
        user_id = session["user_id"]
        user_cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]
        if cost_of_stock > user_cash:
            return apology("No cash available", 400)

        # update users table
        updated_cash = user_cash - cost_of_stock
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)

        # Update transactions table
        date = datetime.datetime.now()
        db.execute(
            "INSERT INTO trades (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)",
            user_id,
            symbol,
            shares,
            price_stock,
            date,
        )

        flash("Bought!")
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    trades = db.execute("SELECT * FROM trades WHERE user_id = ?", user_id)

    return render_template("history.html", trades=trades)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Registered!")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Ensure there is a symbol
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Turning information into variables
        symbol = request.form.get("symbol")
        stock_info = lookup(symbol)

        # Accesing the information of the stock
        if stock_info == None:
            return apology("Invalid symbol", 400)
        else:
            return render_template(
                "quoted.html", symbol=symbol, stock_value=stock_info["price"]
            )

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Ensure fields are completed
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        elif not password:
            return apology("must provide password", 400)
        elif not password_confirmation:
            return apology("must confirm the password", 400)

        # Validate password safety
        elif is_valid_password(password) == False:
            return apology("Choose a strong password", 400)

        # Ensure both passwords are the same
        elif password_confirmation != password:
            return apology("both paswords should be the same", 400)

        # Query database for username
        validation_username = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(validation_username) != 0:
            return apology("The username alredy exist", 400)

        # Prepare form
        hash_password = generate_password_hash(request.form.get("password"))

        # Remember user
        db.execute(
            "INSERT INTO users (username, hash) VALUES(?, ?)", username, hash_password
        )
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Registered!")
        return redirect("/")

        # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    symbols = db.execute(
        "SELECT DISTINCT symbol FROM trades WHERE user_id = ? AND shares > 0", user_id
    )
    print(symbols)
    if request.method == "POST":
        # Validate fields are complete
        f_symbol = request.form.get("symbol")
        f_shares = int(request.form.get("shares"))

        if not f_symbol:
            return apology("must provide symbol", 400)
        elif not f_shares:
            return apology("must provide a quantity", 400)

        # Validate user has enough shares
        num_shares = db.execute(
            "SELECT sum(shares) as shares FROM trades WHERE user_id = ? AND symbol = ?",
            user_id,
            f_symbol,
        )
        num_shares2 = num_shares[0]["shares"]

        if f_shares > num_shares2:
            return apology("invalid number of shares", 400)

        # Updating cash table and trades table
        price = lookup(f_symbol)["price"]
        date = datetime.datetime.now()
        user_cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]
        updated_cash = user_cash + (price * f_shares)

        db.execute(
            "INSERT INTO trades (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)",
            user_id,
            f_symbol,
            -f_shares,
            price,
            date,
        )

        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)
        flash("Sold!")
        return redirect("/")

    else:
        return render_template(
            "sell.html", symbols=[item["symbol"] for item in symbols]
        )
