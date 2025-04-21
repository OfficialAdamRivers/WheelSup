# WheelSup - Ultra Build v3.0
# Part 1: Imports, Configuration, Database Initialization, and Utility Helpers

from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory, abort
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
        cur.execute('''CREATE TABLE IF NOT EXISTS trip_comments (
            id INTEGER PRIMARY KEY,
            trip_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TEXT
        )''')
        cur.execute('''CREATE TABLE IF NOT EXISTS trip_rsvps (
            user_id INTEGER,
            trip_id INTEGER,
            PRIMARY KEY(user_id, trip_id)
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

# WheelSup - Ultra Build v3.0
# Part 2: Auth Routes, Session Management, Context Injection

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = hash_pass(request.form["password"])
        name = request.form["name"]
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
        email = request.form["email"]
        password = hash_pass(request.form["password"])
        con = sqlite3.connect("wheelsup.db")
        cur = con.cursor()
        cur.execute("SELECT id FROM users WHERE email=? AND password=?", (email, password))
        row = cur.fetchone()
        if row:
            session["user_id"] = row[0]
            return redirect("/")
        return "Invalid credentials"
    return render_template_string(LOGIN_TEMPLATE)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.context_processor
def inject_counters():
    user = get_user()
    if not user:
        return dict(notif_count=0, message_count=0)
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM likes WHERE post_id IN (SELECT id FROM posts WHERE user_id=?)", (user[0],))
    like_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM comments WHERE post_id IN (SELECT id FROM posts WHERE user_id=?)", (user[0],))
    comment_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM follows WHERE followee_id=?", (user[0],))
    follow_count = cur.fetchone()[0]
    notif_total = like_count + comment_count + follow_count

    cur.execute("SELECT COUNT(*) FROM messages WHERE receiver_id=?", (user[0],))
    message_total = cur.fetchone()[0]

    return dict(notif_count=notif_total, message_count=message_total)

# WheelSup - Ultra Build v3.0
# Part 3: Feed, Post Creation, Likes, Comments, View Single Post

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

@app.route("/post/<int:post_id>")
def view_post(post_id):
    user = get_user()
    if not user:
        return redirect("/login")
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT posts.id, users.name, posts.content, posts.image, posts.created_at, users.id FROM posts JOIN users ON posts.user_id = users.id WHERE posts.id=?", (post_id,))
    post = cur.fetchone()
    if not post:
        return abort(404)
    likes = {post[0]: cur.execute("SELECT COUNT(*) FROM likes WHERE post_id=?", (post_id,)).fetchone()[0]}
    cur.execute("SELECT users.name, content, created_at FROM comments JOIN users ON comments.user_id = users.id WHERE post_id=? ORDER BY created_at", (post_id,))
    comments = {post_id: cur.fetchall()}
    return render_template_string(FEED_TEMPLATE, user=user, posts=[post], likes=likes, comments=comments)

# WheelSup - Ultra Build v3.0
# Part 4: Profile View, Edit, Explore, Follow System

@app.route("/profile/<int:user_id>")
def profile(user_id):
    con = sqlite3.connect("wheelsup.db")
    cur = con.cursor()
    cur.execute("SELECT name, bio, avatar, cover, location, vehicle, skills FROM users WHERE id=?", (user_id,))
    user_data = cur.fetchone()
    if not user_data:
        return "User not found"
    cur.execute("SELECT content, image, created_at FROM posts WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    posts = cur.fetchall()
    return render_template_string(PROFILE_TEMPLATE,
                                  name=user_data[0],
                                  bio=user_data[1],
                                  avatar=user_data[2],
                                  cover=user_data[3],
                                  location=user_data[4],
                                  vehicle=user_data[5],
                                  skills=user_data[6],
                                  posts=posts)

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

@app.route("/profile")
def profile_redirect():
    user = get_user()
    if user:
        return redirect(f"/profile/{user[0]}")
    return redirect("/login")

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

# WheelSup - Ultra Build v3.0
# Part 5: Trip Planner, Comments, RSVPs, Leaflet Map Integration

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
    cur.execute("""SELECT trips.id, users.name, title, description, trip_date, location
                   FROM trips JOIN users ON trips.user_id = users.id
                   ORDER BY trip_date ASC""")
    trips = cur.fetchall()
    cur.execute("""SELECT trip_id, users.name, content, created_at
                   FROM trip_comments JOIN users ON trip_comments.user_id = users.id
                   ORDER BY created_at""")
    trip_comments = {}
    for row in cur.fetchall():
        trip_comments.setdefault(row[0], []).append(row[1:])
    cur.execute("SELECT trip_id, COUNT(*) FROM trip_rsvps GROUP BY trip_id")
    rsvp_counts = {row[0]: row[1] for row in cur.fetchall()}
    return render_template_string(TRIP_TEMPLATE, trips=trips, comments=trip_comments, rsvps=rsvp_counts)

@app.route("/trip/comment/<int:trip_id>", methods=["POST"])
def comment_trip(trip_id):
    user = get_user()
    if not user: return redirect("/login")
    content = request.form["comment"]
    con = sqlite3.connect("wheelsup.db")
    con.execute("INSERT INTO trip_comments (trip_id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
                (trip_id, user[0], content, str(datetime.datetime.now())))
    con.commit()
    return redirect("/trip")

@app.route("/trip/rsvp/<int:trip_id>")
def rsvp_trip(trip_id):
    user = get_user()
    if not user: return redirect("/login")
    con = sqlite3.connect("wheelsup.db")
    try:
        con.execute("INSERT INTO trip_rsvps (user_id, trip_id) VALUES (?, ?)", (user[0], trip_id))
    except:
        con.execute("DELETE FROM trip_rsvps WHERE user_id=? AND trip_id=?", (user[0], trip_id))
    con.commit()
    return redirect("/trip")

# WheelSup - Ultra Build v3.0
# Part 6: Direct Messages, Inbox, Notifications, File Routing

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

# WheelSup - Ultra Build v3.0
# Part 7: App Runner + Template Headers + Startup

TAILWIND_HEAD = '''<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { font-family: 'Segoe UI', sans-serif; }
  input, textarea, button { transition: all 0.2s ease-in-out; }
  input:focus, textarea:focus {
    outline: none;
    border-color: #38a169;
    box-shadow: 0 0 0 2px rgba(72, 187, 120, 0.4);
  }
</style>
'''

HEADER_HTML = '''
<div class="bg-green-900 text-white px-6 py-4 shadow-md">
  <div class="max-w-7xl mx-auto flex justify-between items-center">
    <div>
      <h1 class="text-2xl font-bold tracking-widest">WheelSup</h1>
      <p class="text-sm opacity-80">Social Media for Travelers</p>
    </div>
    <a href="/profile" class="text-white hover:underline">My Profile</a>
  </div>
</div>
'''

NAVBAR_TEMPLATE = '''
<aside class="w-20 bg-green-800 text-white flex flex-col items-center py-6 space-y-6 shadow-lg">
  <a href="/" title="Home">🏠</a>
  <a href="/explore" title="Explore">🧭</a>
  <div class="relative" title="Notifications">
    <a href="/notifications">🔔</a>
    {% if notif_count > 0 %}
    <span class="absolute -top-1 -right-2 bg-red-600 text-xs text-white rounded-full px-1">{{ notif_count }}</span>
    {% endif %}
  </div>
  <div class="relative" title="Inbox">
    <a href="/inbox">💬</a>
    {% if message_count > 0 %}
    <span class="absolute -top-1 -right-2 bg-red-600 text-xs text-white rounded-full px-1">{{ message_count }}</span>
    {% endif %}
  </div>
  <a href="/trip" title="Trips">🗺️</a>
  <a href="/logout" title="Logout">🚪</a>
</aside>
'''
# WheelSup - Ultra Build v3.0
# Part 8: HTML Templates (Login, Register, Feed, Trip, Explore, Chat, Inbox, Notifications, Profile, Edit)

LOGIN_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="flex items-center justify-center h-screen bg-gray-100">
<div class="bg-white p-6 rounded shadow w-full max-w-sm">
  <h2 class="text-xl font-bold mb-4">Login</h2>
  <form method="post" class="flex flex-col space-y-3">
    <input name="email" placeholder="Email" class="border p-2 rounded">
    <input type="password" name="password" placeholder="Password" class="border p-2 rounded">
    <button class="bg-green-600 text-white py-2 rounded">Login</button>
  </form>
  <p class="text-sm mt-3">No account? <a class="text-blue-500" href="/register">Register here</a></p>
</div></body></html>'''

REG_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="flex items-center justify-center h-screen bg-gray-100">
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

# WheelSup - Ultra Build v3.0
# Part 9: Templates (Feed, Trip, Explore, Chat, Inbox, Notifications, Profile, Edit)

FEED_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-50"><div class="flex min-h-screen">
''' + NAVBAR_TEMPLATE + '''
<main class="flex-1 p-6 max-w-3xl mx-auto">
  <form method="post" enctype="multipart/form-data" class="bg-white p-4 rounded shadow mb-6 space-y-3">
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
</main></div></body></html>
'''

TRIP_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100"><div class="flex">
''' + NAVBAR_TEMPLATE + '''
<main class="flex-1 p-6 max-w-4xl mx-auto">
  <h2 class="text-2xl font-bold mb-4">Trip Board</h2>
  <form method="post" class="bg-white p-4 rounded shadow mb-6 space-y-3">
    <input name="title" placeholder="Trip Title" class="w-full border rounded p-2">
    <input name="location" placeholder="Location" class="w-full border rounded p-2">
    <input name="date" type="date" class="w-full border rounded p-2">
    <textarea name="description" placeholder="Description" class="w-full border rounded p-2"></textarea>
    <button class="bg-green-600 text-white px-4 py-2 rounded">Post Trip</button>
  </form>
  <div id="map" class="w-full h-64 rounded shadow mb-6"></div>
  <script src="https://unpkg.com/leaflet@1.9.3/dist/leaflet.js"></script>
  <script>
    var map = L.map('map').setView([43.0731, -89.4012], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '© OpenStreetMap'
    }).addTo(map);
  </script>
  <div class="space-y-6">
    {% for t in trips %}
    <div class="bg-white p-4 rounded shadow">
      <h3 class="font-bold text-lg">{{ t[2] }} - {{ t[4] }}</h3>
      <p class="text-gray-700">{{ t[3] }}</p>
      <p class="text-sm text-gray-500">Location: {{ t[5] }} | Posted by {{ t[1] }}</p>
      <form method="post" action="/trip/comment/{{ t[0] }}" class="mt-2 flex space-x-2">
        <input name="comment" placeholder="Add comment..." class="flex-1 border rounded p-1">
        <button class="bg-blue-600 text-white px-2 rounded">Post</button>
      </form>
      <a href="/trip/rsvp/{{ t[0] }}" class="inline-block mt-2 text-green-700 font-semibold hover:underline">
        RSVP ({{ rsvps.get(t[0], 0) }})
      </a>
      <div class="mt-3 text-sm text-gray-700">
        {% for c in comments.get(t[0], []) %}
        <p><strong>{{ c[0] }}</strong>: {{ c[1] }} <i class="text-xs text-gray-400">{{ c[2] }}</i></p>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </div>
</main></div></body></html>
'''

EXPLORE_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100 p-6">
<h2 class="text-2xl font-bold mb-4">Explore</h2>
<div class="flex flex-wrap gap-4">
  {% for user in users %}
  <div class="bg-white p-4 rounded shadow w-56">
    <p class="font-semibold"><a href="/profile/{{ user[0] }}">{{ user[1] }}</a></p>
    <a href="/follow/{{ user[0] }}" class="text-blue-600 text-sm">Follow</a>
  </div>
  {% endfor %}
</div>
<h3 class="text-xl font-semibold mt-6 mb-2">Featured Posts</h3>
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
</body></html>
'''
# WheelSup - Ultra Build v3.0
# Part 10: Remaining Templates (Chat, Inbox, Notifications, Profile, Edit Profile)

CHAT_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100 p-6 max-w-xl mx-auto">
<h2 class="text-2xl font-bold mb-4">Chat</h2>
<div class="space-y-2">
{% for m in messages %}
  <div class="{{ 'text-right' if m[0] == me else 'text-left' }}">
    <p class="inline-block bg-white p-2 rounded shadow">{{ m[1] }}</p>
    <span class="block text-xs text-gray-400">{{ m[2] }}</span>
  </div>
{% endfor %}
</div>
<form method="post" class="mt-4 flex">
  <input name="message" class="flex-1 border p-2 rounded" placeholder="Type message">
  <button class="ml-2 bg-blue-600 text-white px-4 py-2 rounded">Send</button>
</form>
</body></html>
'''

INBOX_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100 p-6 max-w-xl mx-auto">
<h2 class="text-2xl font-bold mb-4">Inbox</h2>
<div class="space-y-3">
{% for u in users %}
  <a href="/dm/{{ u[0] }}" class="block bg-white p-3 rounded shadow">Chat with User {{ u[0] }}</a>
{% endfor %}
</div>
</body></html>
'''

NOTIFICATION_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100 p-6 max-w-xl mx-auto">
<h2 class="text-2xl font-bold mb-4">Notifications</h2>
<div class="space-y-2">
{% for n in notes %}
  <a href="/post/{{ n[0] or '' }}" class="block bg-white p-3 rounded shadow">
    <strong>{{ n[1] }}</strong> {{ n[2] }} <span class="text-xs text-gray-400">{{ n[3] or '' }}</span>
  </a>
{% endfor %}
</div>
</body></html>
'''

PROFILE_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100 p-6 max-w-3xl mx-auto">
<h2 class="text-2xl font-bold mb-4">{{ name }}'s Profile</h2>
{% if avatar %}<img src="{{ url_for('uploaded_file', filename=avatar.split('/')[-1]) }}" class="rounded-full w-32 h-32 mb-4">{% endif %}
{% if cover %}<img src="{{ url_for('uploaded_file', filename=cover.split('/')[-1]) }}" class="rounded w-full h-40 object-cover mb-4">{% endif %}
<p class="text-md text-gray-700 mb-2"><strong>Bio:</strong> {{ bio }}</p>
<p class="text-md text-gray-700 mb-2"><strong>Location:</strong> {{ location }}</p>
<p class="text-md text-gray-700 mb-2"><strong>Vehicle:</strong> {{ vehicle }}</p>
<p class="text-md text-gray-700 mb-4"><strong>Skills:</strong> {{ skills }}</p>
<div class="space-y-4">
{% for post in posts %}
  <div class="bg-white p-4 rounded shadow">
    <p>{{ post[0] }}</p>
    {% if post[1] %}<img src="{{ url_for('uploaded_file', filename=post[1].split('/')[-1]) }}" class="mt-2 rounded">{% endif %}
    <p class="text-xs text-gray-500 mt-1">{{ post[2] }}</p>
  </div>
{% endfor %}
</div>
</body></html>
'''

EDIT_PROFILE_TEMPLATE = TAILWIND_HEAD + HEADER_HTML + '''
<html><body class="bg-gray-100 p-6 max-w-xl mx-auto">
<h2 class="text-2xl font-bold mb-4">Edit Profile</h2>
<form method="post" enctype="multipart/form-data" class="bg-white p-4 rounded shadow space-y-3">
  <input name="bio" placeholder="Bio" class="w-full border p-2 rounded">
  <input name="location" placeholder="Location" class="w-full border p-2 rounded">
  <input name="vehicle" placeholder="Vehicle Type" class="w-full border p-2 rounded">
  <input name="skills" placeholder="Skills or Services" class="w-full border p-2 rounded">
  <label class="block text-sm font-semibold">Avatar:</label>
  <input type="file" name="avatar" class="w-full">
  <label class="block text-sm font-semibold">Cover Photo:</label>
  <input type="file" name="cover" class="w-full">
  <button class="bg-green-700 text-white px-4 py-2 rounded">Save</button>
</form>
</body></html>
'''

# Final runner
if __name__ == "__main__":
    app.run(debug=True)
