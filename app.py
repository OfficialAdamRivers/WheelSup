from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory
import sqlite3, os, hashlib, uuid, datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ------------------- DB INIT -------------------
def init_db():
    with sqlite3.connect("wheelsup.db") as con:
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, name TEXT, bio TEXT, avatar TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, image TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, comment TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, sender_id INTEGER, receiver_id INTEGER, message TEXT, created_at TEXT)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS trips (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, location TEXT, description TEXT, trip_date TEXT)''')
init_db()

# ------------------- AUTH -------------------
def hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()

def get_user():
    uid = session.get('user_id')
    if not uid: return None
    con = sqlite3.connect("wheelsup.db"); cur = con.cursor()
    cur.execute("SELECT id, name, avatar FROM users WHERE id=?", (uid,))
    return cur.fetchone()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form['email']
        password = hash_pass(request.form['password'])
        name = request.form['name']
        con = sqlite3.connect("wheelsup.db")
        try:
            con.execute("INSERT INTO users (email, password, name) VALUES (?, ?, ?)", (email, password, name))
            con.commit()
            return redirect("/login")
        except:
            return "Email already registered"
    return render_template_string(REG_FORM)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = hash_pass(request.form['password'])
        con = sqlite3.connect("wheelsup.db")
        cur = con.cursor()
        cur.execute("SELECT id FROM users WHERE email=? AND password=?", (email, password))
        row = cur.fetchone()
        if row:
            session['user_id'] = row[0]
            return redirect("/")
        return "Invalid credentials"
    return render_template_string(LOGIN_FORM)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ------------------- HOME FEED -------------------
@app.route("/", methods=["GET", "POST"])
def index():
    user = get_user()
    if not user: return redirect("/login")
    if request.method == "POST":
        content = request.form['content']
        file = request.files.get('image')
        image_path = ""
        if file:
            filename = secure_filename(file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(image_path)
        con = sqlite3.connect("wheelsup.db")
        con.execute("INSERT INTO posts (user_id, content, image, created_at) VALUES (?, ?, ?, ?)",
                    (user[0], content, image_path, str(datetime.datetime.now())))
        con.commit()
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT posts.id, users.name, posts.content, posts.image, posts.created_at FROM posts JOIN users ON posts.user_id = users.id ORDER BY posts.created_at DESC")
    posts = cur.fetchall()
    return render_template_string(HOME_FEED, user=user, posts=posts)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ------------------- UI HTML -------------------
REG_FORM = '''<!DOCTYPE html><html><body><h2>Register</h2><form method="post">Email: <input name="email"><br>Password: <input type="password" name="password"><br>Name: <input name="name"><br><button type="submit">Register</button></form></body></html>'''

LOGIN_FORM = '''<!DOCTYPE html><html><body><h2>Login</h2><form method="post">Email: <input name="email"><br>Password: <input type="password" name="password"><br><button type="submit">Login</button></form></body></html>'''

HOME_FEED = '''<!DOCTYPE html><html><body><h2>Welcome {{ user[1] }}</h2><a href="/logout">Logout</a>
<form method="post" enctype="multipart/form-data">Share your adventure:<br><textarea name="content"></textarea><br><input type="file" name="image"><br><button type="submit">Post</button></form>
<hr>
{% for post in posts %}<div><h3>{{ post[1] }}</h3><p>{{ post[2] }}</p>{% if post[3] %}<img src="{{ url_for('uploaded_file', filename=post[3].split('/')[-1]) }}" width="200">{% endif %}<p><i>{{ post[4] }}</i></p></div><hr>{% endfor %}
</body></html>'''

# ------------------- RUN -------------------
if __name__ == '__main__':
    app.run(debug=True)
