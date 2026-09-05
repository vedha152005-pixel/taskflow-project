from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import os
from psycopg2.extras import RealDictCursor


app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "taskflow_secret_key"
)


# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"]
    )


# =========================
# INITIALIZE DATABASE
# =========================
def init_db():

    connection = get_db_connection()
    cursor = connection.cursor()

    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """)

    # TASKS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            category VARCHAR(100),
            priority VARCHAR(50),
            due_date DATE,
            status VARCHAR(20) DEFAULT 'Pending',
            CONSTRAINT fk_user
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()

    cursor.close()
    connection.close()


# =========================
# HOME PAGE
# =========================
@app.route("/")
def home():

    return render_template("index.html")


# =========================
# TEST DATABASE
# =========================
@app.route("/test-db")
def test_db():

    connection = get_db_connection()

    connection.close()

    return "Database Connected Successfully!"


# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        connection = get_db_connection()
        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        # Check whether email already exists
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            connection.close()

            flash(
                "This email is already registered. Please log in.",
                "error"
            )

            return redirect(url_for("login"))

        # Create new account
        cursor.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (%s, %s, %s)
            """,
            (name, email, password)
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Account created successfully! Please log in to continue.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        connection = None
        cursor = None

        try:

            connection = get_db_connection()

            cursor = connection.cursor(
                cursor_factory=RealDictCursor
            )

            query = """
                SELECT *
                FROM users
                WHERE email = %s
                AND password = %s
            """

            cursor.execute(
                query,
                (email, password)
            )

            user = cursor.fetchone()

            if user:

                session["user_id"] = user["id"]

                return redirect(
                    url_for("dashboard")
                )

            else:

                return render_template(
                    "login.html",
                    error="Invalid email or password."
                )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("login.html")


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    status = request.args.get("status")
    search = request.args.get("search")

    connection = get_db_connection()

    cursor = connection.cursor(
        cursor_factory=RealDictCursor
    )

    query = """
        SELECT *
        FROM tasks
        WHERE user_id = %s
    """

    values = [user_id]

    # Status Filter
    if status in ["Pending", "Completed"]:

        query += " AND status = %s"

        values.append(status)

    # Search Filter
    if search and search.strip():

        search_value = "%" + search.strip() + "%"

        query += """
            AND (
                title ILIKE %s
                OR description ILIKE %s
                OR category ILIKE %s
            )
        """

        values.append(search_value)
        values.append(search_value)
        values.append(search_value)

    cursor.execute(
        query,
        tuple(values)
    )

    tasks = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "dashboard.html",
        tasks=tasks,
        selected_status=status,
        search=search
    )


# =========================
# ADD TASK
# =========================
@app.route("/add-task", methods=["GET", "POST"])
def add_task():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        user_id = session["user_id"]

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        priority = request.form["priority"]
        due_date = request.form["due_date"]

        connection = get_db_connection()

        cursor = connection.cursor()

        query = """
            INSERT INTO tasks
            (
                user_id,
                title,
                description,
                category,
                priority,
                due_date
            )
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                user_id,
                title,
                description,
                category,
                priority,
                due_date
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(
            url_for("dashboard")
        )

    return render_template("add_task.html")


# =========================
# COMPLETE TASK
# =========================
@app.route("/complete-task/<int:task_id>")
def complete_task(task_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = get_db_connection()

    cursor = connection.cursor()

    query = """
        UPDATE tasks
        SET status = 'Completed'
        WHERE id = %s
        AND user_id = %s
    """

    cursor.execute(
        query,
        (task_id, user_id)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(
        url_for("dashboard")
    )


# =========================
# EDIT TASK
# =========================
@app.route(
    "/edit-task/<int:task_id>",
    methods=["GET", "POST"]
)
def edit_task(task_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = get_db_connection()

    cursor = connection.cursor(
        cursor_factory=RealDictCursor
    )

    # UPDATE TASK
    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        priority = request.form["priority"]
        due_date = request.form["due_date"]

        query = """
            UPDATE tasks
            SET
                title = %s,
                description = %s,
                category = %s,
                priority = %s,
                due_date = %s
            WHERE id = %s
            AND user_id = %s
        """

        cursor.execute(
            query,
            (
                title,
                description,
                category,
                priority,
                due_date,
                task_id,
                user_id
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(
            url_for("dashboard")
        )

    # GET TASK DETAILS
    query = """
        SELECT *
        FROM tasks
        WHERE id = %s
        AND user_id = %s
    """

    cursor.execute(
        query,
        (task_id, user_id)
    )

    task = cursor.fetchone()

    cursor.close()
    connection.close()

    return render_template(
        "edit_task.html",
        task=task
    )


# =========================
# DELETE TASK
# =========================
@app.route("/delete-task/<int:task_id>")
def delete_task(task_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = get_db_connection()

    cursor = connection.cursor()

    query = """
        DELETE FROM tasks
        WHERE id = %s
        AND user_id = %s
    """

    cursor.execute(
        query,
        (task_id, user_id)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(
        url_for("dashboard")
    )


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# =========================
# RUN APPLICATION
# =========================
if __name__ == "__main__":

    try:
        init_db()
        print("Database initialized successfully!")

    except Exception as e:
        print("Database initialization error:", e)

    app.run(
        debug=True
    )
