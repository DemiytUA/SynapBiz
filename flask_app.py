from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mail import Mail, Message
import sqlite3
import random
import os
import hashlib

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Генерує випадковий ключ


# ------------------------------------------------------------email_init

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'chernykteam@gmail.com'  # Заміни на свою пошту
app.config['MAIL_PASSWORD'] = 'utcq lsni epkx otkj'  # Заміни на свій пароль
app.config['MAIL_DEFAULT_SENDER'] = 'chernykteam@gmail.com'
mail = Mail(app)

# -----------------------messages_templates
def message_code(confirmation_code):
    return f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333333;">
            <h2 style="text-align: center; font-size: 24px; color: #4CAF50;">Email Address Confirmation</h2>
            <p style="font-size: 16px;">Your verification code is: <strong style="font-size: 18px; color: #333333;">{confirmation_code}</strong></p>
            <p style="font-size: 16px;">Please use this code to confirm your email address.</p>
        </body>
    </html>
    """

def message_update(file_name_without_extension):
    return f"""
<html>
    <body style="font-family: Arial, sans-serif; color: #333333;">
        <h2 style="text-align: center; font-size: 24px; color: #4CAF50;">Our App has received an update!</h2>
        <p style="font-size: 16px;">We are happy to announce that our app <strong style="font-size: 18px; color: #333333;">{file_name_without_extension}</strong> has received an update!</p>
        <p style="font-size: 16px;">We are waiting for you to try out the new features.</p>
        <p style="font-size: 16px;">Feel free to download the latest version.</p>
    </body>
</html>
"""
# -----------------------messages_templates

# ------------------------------------------------------------email_init


# ------------------------------------------------------------db

DB_NAME = "subscribers.db"


def init_db():
    """Створює таблиці, якщо їх ще немає, і додає стовпець confirmed"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # Створюємо таблицю subscribers, якщо її немає
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                confirmed INTEGER DEFAULT 0
            )
        """)

        # Створюємо таблицю confirmations, якщо її немає
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS confirmations (
                email TEXT PRIMARY KEY,
                code TEXT
            )
        """)

        # Створюємо таблицю для збереження інформації про файл
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_updates (
                id INTEGER PRIMARY KEY,
                file_name TEXT
            )
        """)
        conn.commit()

# Викликаємо функцію для ініціалізації бази даних
init_db()

# ------------------------------------------------------------db


# ------------------------------------------------------------work_with_file_updates

def get_file_hash(file_path):
    """Обчислюємо хеш файлу"""
    hash_sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def check_for_file_update():
    """Перевіряємо, чи змінилася назва файлу в папці і надсилаємо повідомлення, якщо змінилася"""
    folder_path = "static/app"  # Шлях до папки, де зберігаються файли
    files = os.listdir(folder_path)

    for file in files:
        file_path = os.path.join(folder_path, file)

        if os.path.isfile(file_path):
            # Отримуємо назву файлу без розширення
            file_name_without_extension = os.path.splitext(file)[0]

            # Перевірка на зміни назви файлу в базі даних
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_name FROM file_updates WHERE id = 1")
                row = cursor.fetchone()

                # Якщо назва файлу змінилася
                if row is None or row[0] != file_name_without_extension:
                    # Оновлюємо назву файлу в базі даних
                    cursor.execute("INSERT OR REPLACE INTO file_updates (id, file_name) VALUES (1, ?)", (file_name_without_extension,))
                    conn.commit()

                    # Відправка повідомлення всім підписникам
                    cursor.execute("SELECT email FROM subscribers WHERE confirmed = 1")
                    subscribers = cursor.fetchall()

                    # Вивести в консоль для перевірки
                    print(f"Назва файлу {file} змінилася! Оновлюємо підписників...")

                    # Використовуємо контекст додатку для відправки повідомлень
                    with app.app_context():
                        for email in subscribers:
                            try:
                                msg = Message("New updates are here!", recipients=[email[0]])
                                # Відправляємо повідомлення без розширення файлу
                                msg.html = message_update(file_name_without_extension)
                                mail.send(msg)

                                print(f"Повідомлення надіслано: {email[0]}")
                            except Exception as e:
                                print(f"Не вдалося надіслати листа на {email[0]}: {e}")

# ------------------------------------------------------------db


# ------------------------------------------------------------web


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email = request.form["email"]

        # Перевіряємо, чи email вже є в базі
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT confirmed FROM subscribers WHERE email = ?", (email,))
            user = cursor.fetchone()

        if user and user[0] == 1:
            flash("Your email has already been confirmed!", "success")
            return redirect(url_for("index"))

        # Генеруємо код підтвердження
        confirmation_code = str(random.randint(100000, 999999))

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO confirmations (email, code) VALUES (?, ?)",
                           (email, confirmation_code))
            cursor.execute("INSERT OR IGNORE INTO subscribers (email) VALUES (?)", (email,))
            conn.commit()

        try:
            msg = Message("Email address confirmation", recipients=[email])
            msg.html = message_code(confirmation_code)
            mail.send(msg)
            flash("Лист підтвердження надіслано! Перевірте пошту.", "success")
            return redirect(url_for("verify", email=email))
        except Exception as e:
            flash(f"Error: {e}", "danger")

    return render_template("index.html")


@app.route("/verify/<email>", methods=["GET", "POST"])
def verify(email):
    if request.method == "POST":
        user_code = request.form["code"]

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code FROM confirmations WHERE email = ?", (email,))
            record = cursor.fetchone()

        if record and record[0] == user_code:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE subscribers SET confirmed = 1 WHERE email = ?", (email,))
                cursor.execute("DELETE FROM confirmations WHERE email = ?", (email,))
                conn.commit()

            flash("Subscription confirmed!", "success")
            return redirect(url_for("index"))
        else:
            flash("Incorrect code!", "danger")

    return render_template("verify.html", email=email)

@app.route("/demo")
def demo():
    return render_template("demo.html")


if __name__ == "__main__":
    app.secret_key = os.urandom(24)  # Для flash-повідомлень
    check_for_file_update()  # Перевірка файлу при запуску сервера
    app.run(debug=True)

# ------------------------------------------------------------web
