from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from pyzbar.pyzbar import decode
from PIL import Image
import io, base64
import google.generativeai as genai

# ====== CONFIG ======
app = Flask(__name__)
app.secret_key = "supersecretkey"  # change this in production

# Configure Gemini API
genai.configure(api_key="YOUR_GEMINI_API_KEY")  # replace with your actual key


# ====== DB INIT ======
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            college TEXT,
            accsoft_id TEXT
        )
    """
    )
    conn.commit()
    conn.close()


# ====== HELPERS ======
def verify_with_barcode(image_bytes, entered_code):
    """Try reading barcode first."""
    img = Image.open(io.BytesIO(image_bytes))
    decoded = decode(img)
    if decoded:
        scanned = decoded[0].data.decode("utf-8")
        return scanned == entered_code
    return None


def verify_with_gemini(image_bytes, entered_code):
    """Fallback OCR using Gemini API."""
    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        [
            {"mime_type": "image/png", "data": b64_img},
            "Extract the digits visible on the ID card (especially below barcode).",
        ]
    )
    text = response.text.strip()
    return entered_code in text


# ====== ROUTES ======
@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "")
        college = request.form.get("college", "").strip()
        accsoft_id = request.form.get("accsoft_id", "").strip()
        file = request.files.get("id_image")

        if not (full_name and email and password and role and college and accsoft_id and file):
            flash("All fields are required.")
            return redirect(url_for("signup"))

        image_bytes = file.read()

        # Step 1: barcode
        barcode_result = verify_with_barcode(image_bytes, accsoft_id)

        if barcode_result is True:
            verified = True
        elif barcode_result is False:
            verified = False
        else:
            verified = verify_with_gemini(image_bytes, accsoft_id)

        if not verified:
            flash("❌ ID Verification failed. Cannot sign up.")
            return redirect(url_for("signup"))

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        try:
            c.execute(
                """
                INSERT INTO users (full_name, email, password, role, college, accsoft_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (full_name, email, generate_password_hash(password), role, college, accsoft_id),
            )
            conn.commit()

            # ✅ Auto login after signup
            session["user"] = email
            flash("✅ Signup successful! You are now logged in.")
            return redirect(url_for("home"))

        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return redirect(url_for("signup"))
        finally:
            conn.close()

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        print("DEBUG - user from DB:", user)  # Debug print

        if user and check_password_hash(user[3], password):
            session["user"] = email
            print("DEBUG - Login successful, redirecting to home")  # Debug print
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials. Try again.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/home")
def home():
    if "user" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute(
        "SELECT full_name, role, college FROM users WHERE email=?",
        (session["user"],),
    )
    user = c.fetchone()
    conn.close()

    return render_template("home.html", user=user)


@app.route("/profile")
def profile():
    if "user" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    return render_template("profile.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("landing"))


# ====== RUN ======
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
