# WheelSup - Full Flask App
# Part 1: Imports, Configuration, Database Setup, and Helper Functions

from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory
import sqlite3, os, hashlib, datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    with sqlite3.connect("wheelsup.db") as con:
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            name TEXT,
            bio TEXT,
            location TEXT,
            vehicle TEXT,
            skills TEXT,
            avatar TEXT,
            cover TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            content TEXT,
            image TEXT,
            created_at TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS likes (
            user_id INTEGER,
            post_id INTEGER,
            PRIMARY KEY(user_id, post_id)
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER,
            followee_id INTEGER,
            PRIMARY KEY(follower_id, followee_id)
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            trip_date TEXT,
            location TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            sender_id INTEGER,
            receiver_id INTEGER,
            message TEXT,
            created_at TEXT
        )''')
init_db()

def hash_pass(p): return hashlib.sha256(p.encode()).hexdigest()

def get_user():
    uid = session.get('user_id')
    if not uid: return None
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (uid,))
    return cur.fetchone()

# WheelSup - Full Flask App
# Part 2: Authentication Routes (Login, Register, Logout) + Persistent Sessions

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
    return render_template_string(REG_TEMPLATE)

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
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# WheelSup - Full Flask App
# Part 3: Main Feed, Post Creation, Likes, and Comments

@app.route("/", methods=["GET", "POST"])
def index():
    user = get_user()
    if not user:
        return redirect("/login")

    if request.method == "POST":
        content = request.form["content"]
        file = request.files.get("image")
        image_path = ""
        if file:
            filename = secure_filename(file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(image_path)
        con = sqlite3.connect("wheelsup.db")
        con.execute("INSERT INTO posts (user_id, content, image, created_at) VALUES (?, ?, ?, ?)",
                    (user[0], content, image_path, str(datetime.datetime.now())))
        con.commit()

    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("""SELECT posts.id, users.name, posts.content, posts.image, posts.created_at, users.id
                   FROM posts JOIN users ON posts.user_id = users.id
                   ORDER BY posts.created_at DESC""")
    posts = cur.fetchall()

    likes = {row[0]: row[1] for row in con.execute("SELECT post_id, COUNT(*) FROM likes GROUP BY post_id")}
    comments = {}
    for row in con.execute("""SELECT post_id, users.name, content, created_at
                              FROM comments JOIN users ON comments.user_id = users.id
                              ORDER BY created_at"""):
        comments.setdefault(row[0], []).append(row[1:])
    return render_template_string(FEED_TEMPLATE, user=user, posts=posts, likes=likes, comments=comments)

@app.route("/like/<int:post_id>")
def like(post_id):
    user = get_user()
    if user:
        con = sqlite3.connect("wheelsup.db")
        try:
            con.execute("INSERT INTO likes (user_id, post_id) VALUES (?, ?)", (user[0], post_id))
        except:
            con.execute("DELETE FROM likes WHERE user_id=? AND post_id=?", (user[0], post_id))
        con.commit()
    return redirect("/")

@app.route("/comment/<int:post_id>", methods=["POST"])
def comment(post_id):
    user = get_user()
    if user:
        content = request.form["comment"]
        con = sqlite3.connect("wheelsup.db")
        con.execute("INSERT INTO comments (post_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
                    (post_id, user[0], content, str(datetime.datetime.now())))
        con.commit()
    return redirect("/")

# WheelSup - Full Flask App
# Part 4: Explore, Profile, Trip Planner, Follow System

@app.route("/explore")
def explore():
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT id, name FROM users ORDER BY id DESC LIMIT 10")
    users = cur.fetchall()
    cur.execute("""SELECT posts.id, users.name, posts.content, posts.image, posts.created_at
                   FROM posts JOIN users ON posts.user_id = users.id
                   ORDER BY RANDOM() LIMIT 10""")
    posts = cur.fetchall()
    return render_template_string(EXPLORE_TEMPLATE, users=users, posts=posts)

@app.route("/profile/<int:user_id>")
def profile(user_id):
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT name, bio, avatar, cover FROM users WHERE id=?", (user_id,))
    user_data = cur.fetchone()
    cur.execute("SELECT content, image, created_at FROM posts WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    posts = cur.fetchall()
    return render_template_string(PROFILE_TEMPLATE, name=user_data[0], bio=user_data[1], avatar=user_data[2], cover=user_data[3], posts=posts)

@app.route("/profile/edit", methods=["GET", "POST"])
def edit_profile():
    user = get_user()
    if not user:
        return redirect("/login")

    if request.method == "POST":
        bio = request.form.get("bio")
        location = request.form.get("location")
        vehicle = request.form.get("vehicle")
        skills = request.form.get("skills")
        avatar = request.files.get("avatar")
        cover = request.files.get("cover")
        avatar_path, cover_path = "", ""

        if avatar:
            avatar_filename = secure_filename(avatar.filename)
            avatar_path = os.path.join(app.config["UPLOAD_FOLDER"], avatar_filename)
            avatar.save(avatar_path)

        if cover:
            cover_filename = secure_filename(cover.filename)
            cover_path = os.path.join(app.config["UPLOAD_FOLDER"], cover_filename)
            cover.save(cover_path)

        con = sqlite3.connect("wheelsup.db")
        con.execute("""UPDATE users SET bio=?, location=?, vehicle=?, skills=?,
                        avatar=COALESCE(NULLIF(?, ''), avatar),
                        cover=COALESCE(NULLIF(?, ''), cover)
                     WHERE id=?""",
                     (bio, location, vehicle, skills, avatar_path, cover_path, user[0]))
        con.commit()
        return redirect(f"/profile/{user[0]}")

    return render_template_string(EDIT_PROFILE_TEMPLATE, user=user)

@app.route("/trip", methods=["GET", "POST"])
def trip():
    user = get_user()
    if not user:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]
        date = request.form["date"]
        con = sqlite3.connect("wheelsup.db")
        con.execute("INSERT INTO trips (user_id, title, description, trip_date, location) VALUES (?, ?, ?, ?, ?)",
                    (user[0], title, description, date, location))
        con.commit()
        return redirect("/trip")

    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT title, description, trip_date, location FROM trips ORDER BY trip_date ASC")
    trips = cur.fetchall()
    return render_template_string(TRIP_TEMPLATE, trips=trips)

@app.route("/follow/<int:followee_id>")
def follow(followee_id):
    user = get_user()
    if user:
        con = sqlite3.connect("wheelsup.db")
        try:
            con.execute("INSERT INTO follows (follower_id, followee_id) VALUES (?, ?)", (user[0], followee_id))
        except:
            con.execute("DELETE FROM follows WHERE follower_id=? AND followee_id=?", (user[0], followee_id))
        con.commit()
    return redirect("/explore")

# WheelSup - Full Flask App
# Part 5: Direct Messages, Inbox, Notifications, File Serving

@app.route("/dm/<int:user_id>", methods=["GET", "POST"])
def dm(user_id):
    user = get_user()
    if not user:
        return redirect("/login")

    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    if request.method == "POST":
        msg = request.form["message"]
        cur.execute("""INSERT INTO messages (sender_id, receiver_id, message, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (user[0], user_id, msg, str(datetime.datetime.now())))
        con.commit()

    cur.execute("""SELECT sender_id, message, created_at
                   FROM messages
                   WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
                   ORDER BY created_at""",
                (user[0], user_id, user_id, user[0]))
    messages = cur.fetchall()
    return render_template_string(CHAT_TEMPLATE, messages=messages, me=user[0], you=user_id)

@app.route("/inbox")
def inbox():
    user = get_user()
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("""SELECT DISTINCT receiver_id FROM messages WHERE sender_id=?
                   UNION SELECT DISTINCT sender_id FROM messages WHERE receiver_id=?""",
                (user[0], user[0]))
    users = cur.fetchall()
    return render_template_string(INBOX_TEMPLATE, users=users)

@app.route("/notifications")
def notifications():
    user = get_user()
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()

    cur.execute("""SELECT posts.id, users.name, 'liked your post', posts.created_at
                   FROM likes
                   JOIN posts ON likes.post_id = posts.id
                   JOIN users ON likes.user_id = users.id
                   WHERE posts.user_id=?""", (user[0],))
    likes = cur.fetchall()

    cur.execute("""SELECT posts.id, users.name, 'commented on your post', comments.created_at
                   FROM comments
                   JOIN posts ON comments.post_id = posts.id
                   JOIN users ON comments.user_id = users.id
                   WHERE posts.user_id=?""", (user[0],))
    comments = cur.fetchall()

    cur.execute("""SELECT NULL, users.name, 'followed you', NULL
                   FROM follows
                   JOIN users ON follows.follower_id = users.id
                   WHERE followee_id=?""", (user[0],))
    follows = cur.fetchall()

    all_notes = likes + comments + follows
    return render_template_string(NOTIFICATION_TEMPLATE, notes=all_notes)

@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# WheelSup - Full Flask App
# Part 6: Templates and App Runner

TAILWIND_HEAD = '<script src="https://cdn.tailwindcss.com"></script>'

HEADER_HTML = '''
<div class="w-full bg-green-800 text-white p-4 text-center shadow-md">
  <h1 class="text-2xl font-bold tracking-wide">WheelSup</h1>
  <p class="text-sm font-light">Social Media for Travelers</p>
</div>
'''

LOGIN_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="flex items-center justify-center h-screen bg-gray-100">
<div class="bg-white p-6 rounded shadow w-full max-w-sm">
  <h2 class="text-xl font-bold mb-4">Login</h2>
  <form method="post" class="flex flex-col space-y-3">
    <input name="email" placeholder="Email" class="border p-2 rounded">
    <input type="password" name="password" placeholder="Password" class="border p-2 rounded">
    <button class="bg-green-600 text-white py-2 rounded">Login</button>
  </form>
  <p class="text-sm mt-3">No account? <a class="text-blue-500" href="/register">Register here</a></p>
</div></body></html>'''

REG_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="flex items-center justify-center h-screen bg-gray-100">
<div class="bg-white p-6 rounded shadow w-full max-w-sm">
  <h2 class="text-xl font-bold mb-4">Register</h2>
  <form method="post" class="flex flex-col space-y-3">
    <input name="email" placeholder="Email" class="border p-2 rounded">
    <input type="password" name="password" placeholder="Password" class="border p-2 rounded">
    <input name="name" placeholder="Display Name" class="border p-2 rounded">
    <button class="bg-green-600 text-white py-2 rounded">Register</button>
  </form>
  <p class="text-sm mt-3">Already have an account? <a class="text-blue-500" href="/login">Login</a></p>
</div></body></html>'''

# Note: For brevity, other templates like FEED_TEMPLATE, PROFILE_TEMPLATE, CHAT_TEMPLATE, etc. 
# will be included in the following continuation.

# WheelSup - Full Flask App
# Part 7: Feed, Profile, Explore, Trip, Chat, Inbox, Notifications Templates

FEED_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-50">
<div class="flex min-h-screen">
  <aside class="w-20 bg-green-900 text-white flex flex-col items-center py-6 space-y-6">
    <a href="/">🏠</a><a href="/explore">🧭</a><a href="/notifications">🔔</a>
    <a href="/inbox">💬</a><a href="/trip">🗺️</a><a href="/logout">🚪</a>
  </aside>
  <main class="flex-1 p-4 max-w-2xl mx-auto">
    <form method="post" enctype="multipart/form-data" class="bg-white p-4 rounded shadow mb-4 space-y-3">
      <textarea name="content" placeholder="What's on your mind?" class="w-full border rounded p-2"></textarea>
      <input type="file" name="image" class="w-full">
      <button class="bg-green-700 text-white px-4 py-2 rounded">Post</button>
    </form>
    {% for post in posts %}
    <div class="bg-white p-4 rounded shadow mb-4">
      <h3 class="font-bold"><a href="/profile/{{ post[5] }}">{{ post[1] }}</a></h3>
      <p class="mt-1">{{ post[2] }}</p>
      {% if post[3] %}<img src="{{ url_for('uploaded_file', filename=post[3].split('/')[-1]) }}" class="mt-2 rounded">{% endif %}
      <p class="text-xs text-gray-500 mt-2">{{ post[4] }}</p>
      <div class="flex items-center space-x-4 mt-2">
        <a href="/like/{{ post[0] }}" class="text-blue-600">❤️ {{ likes.get(post[0], 0) }}</a>
      </div>
      <form method="post" action="/comment/{{ post[0] }}" class="mt-2 flex space-x-2">
        <input name="comment" placeholder="Add comment..." class="flex-1 border rounded p-1">
        <button class="bg-blue-600 text-white px-2 rounded">Post</button>
      </form>
      <div class="mt-2 text-sm text-gray-700">
        {% for c in comments.get(post[0], []) %}
        <p><strong>{{ c[0] }}</strong>: {{ c[1] }} <i class="text-xs text-gray-400">{{ c[2] }}</i></p>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </main>
</div></body></html>'''

PROFILE_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-4">
<h2 class="text-2xl font-bold mb-4">{{ name }}'s Profile</h2>
{% if avatar %}<img src="{{ url_for('uploaded_file', filename=avatar.split('/')[-1]) }}" class="rounded-full w-32 h-32 mb-4">{% endif %}
{% if cover %}<img src="{{ url_for('uploaded_file', filename=cover.split('/')[-1]) }}" class="rounded w-full h-40 object-cover mb-4">{% endif %}
<p class="text-md text-gray-700 mb-4">{{ bio }}</p>
<div class="space-y-4">
{% for post in posts %}
  <div class="bg-white p-4 rounded shadow">
    <p>{{ post[0] }}</p>
    {% if post[1] %}<img src="{{ url_for('uploaded_file', filename=post[1].split('/')[-1]) }}" class="mt-2 rounded">{% endif %}
    <p class="text-xs text-gray-500 mt-1">{{ post[2] }}</p>
  </div>
{% endfor %}
</div>
</body></html>'''

# Continue to next for EXPLORE_TEMPLATE, TRIP_TEMPLATE, CHAT_TEMPLATE, INBOX_TEMPLATE, NOTIFICATION_TEMPLATE

# WheelSup - Full Flask App
# Part 8: Explore, Trip, Chat, Inbox, Notifications Templates

EXPLORE_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-4">
<h2 class="text-2xl font-bold mb-4">Explore</h2>
<h3 class="text-xl mb-2">Recent Travelers</h3>
<div class="flex flex-wrap gap-3 mb-6">
{% for user in users %}
  <a href="/profile/{{ user[0] }}" class="bg-white p-3 rounded shadow w-48 block hover:bg-green-50">
    <p class="font-semibold">{{ user[1] }}</p>
    <a href="/follow/{{ user[0] }}" class="text-blue-500 text-sm">Follow</a>
  </a>
{% endfor %}
</div>
<h3 class="text-xl mb-2">Featured Posts</h3>
<div class="space-y-4">
{% for post in posts %}
  <div class="bg-white p-4 rounded shadow">
    <h4 class="font-bold">{{ post[1] }}</h4>
    <p>{{ post[2] }}</p>
    {% if post[3] %}<img src="{{ url_for('uploaded_file', filename=post[3].split('/')[-1]) }}" class="mt-2 rounded">{% endif %}
    <p class="text-xs text-gray-500">{{ post[4] }}</p>
  </div>
{% endfor %}
</div>
</body></html>'''

TRIP_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-4">
<h2 class="text-2xl font-bold mb-4">Trip Board</h2>
<form method="post" class="bg-white p-4 rounded shadow mb-4 space-y-2">
  <input name="title" placeholder="Trip Title" class="w-full border rounded p-2">
  <input name="location" placeholder="Location" class="w-full border rounded p-2">
  <input name="date" type="date" class="w-full border rounded p-2">
  <textarea name="description" placeholder="Description" class="w-full border rounded p-2"></textarea>
  <button class="bg-green-600 text-white px-4 py-2 rounded">Post Trip</button>
</form>
<div class="space-y-4">
{% for t in trips %}
  <div class="bg-white p-4 rounded shadow">
    <h3 class="font-bold">{{ t[0] }} - {{ t[2] }}</h3>
    <p>{{ t[1] }}</p>
    <p class="text-sm text-gray-600">{{ t[3] }}</p>
  </div>
{% endfor %}
</div>
</body></html>'''

CHAT_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-4">
<h2 class="text-2xl font-bold mb-4">Chat</h2>
<div class="space-y-2">
{% for m in messages %}
  <div class="{{ 'text-right' if m[0]==me else 'text-left' }}">
    <p class="inline-block bg-white p-2 rounded shadow">{{ m[1] }}</p>
    <span class="block text-xs text-gray-400">{{ m[2] }}</span>
  </div>
{% endfor %}
</div>
<form method="post" class="mt-4 flex">
  <input name="message" class="flex-1 border p-2 rounded" placeholder="Type message">
  <button class="ml-2 bg-blue-600 text-white px-4 py-2 rounded">Send</button>
</form>
</body></html>'''

INBOX_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-4">
<h2 class="text-2xl font-bold mb-4">Inbox</h2>
<div class="space-y-3">
{% for u in users %}
  <a href="/dm/{{ u[0] }}" class="block bg-white p-3 rounded shadow">Chat with User {{ u[0] }}</a>
{% endfor %}
</div>
</body></html>'''

NOTIFICATION_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-4">
<h2 class="text-2xl font-bold mb-4">Notifications</h2>
<div class="space-y-2">
{% for n in notes %}
  <a href="/post/{{ n[0] or '' }}" class="block bg-white p-3 rounded shadow">
    <strong>{{ n[1] }}</strong> {{ n[2] }} <span class="text-xs text-gray-400">{{ n[3] or '' }}</span>
  </a>
{% endfor %}
</div>
</body></html>'''

EDIT_PROFILE_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''<html><body class="bg-gray-100 p-6 max-w-xl mx-auto">
<h2 class="text-2xl font-bold mb-4">Edit Profile</h2>
<form method="post" enctype="multipart/form-data" class="bg-white p-4 rounded shadow space-y-3">
  <input name="bio" placeholder="Bio" class="w-full border p-2 rounded">
  <input name="location" placeholder="Location" class="w-full border p-2 rounded">
  <input name="vehicle" placeholder="Vehicle Type" class="w-full border p-2 rounded">
  <input name="skills" placeholder="Skills or Services" class="w-full border p-2 rounded">
  <label>Avatar:</label><input type="file" name="avatar" class="w-full">
  <label>Cover Photo:</label><input type="file" name="cover" class="w-full">
  <button class="bg-green-700 text-white px-4 py-2 rounded">Save</button>
</form>
</body></html>'''

# App runner
if __name__ == "__main__":
    app.run(debug=True)
