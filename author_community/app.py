pythonimport os
import hashlib
import sqlite3
import base64
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, g
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ink-and-pages-secret-2024')
DATABASE = os.environ.get('DATABASE_PATH', 'ink_and_pages.db')


# ── DATABASE ────────────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            bio TEXT DEFAULT '',
            genre TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            website TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_type TEXT NOT NULL,
            content TEXT NOT NULL,
            media_url TEXT DEFAULT '',
            event_date TEXT DEFAULT '',
            event_location TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (follower_id, following_id),
            FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS likes (
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, post_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author_name TEXT NOT NULL,
            genre TEXT DEFAULT '',
            description TEXT DEFAULT '',
            cover_url TEXT DEFAULT '',
            buy_link TEXT DEFAULT '',
            release_date TEXT DEFAULT '',
            book_type TEXT DEFAULT 'published',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS confessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'writer',
            like_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            event_date TEXT NOT NULL,
            event_time TEXT DEFAULT '',
            location TEXT DEFAULT '',
            event_type TEXT DEFAULT 'virtual',
            link TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS event_rsvps (
            user_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, event_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS writing_pieces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            genre TEXT DEFAULT '',
            piece_type TEXT DEFAULT 'story',
            excerpt TEXT DEFAULT '',
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS writing_likes (
            user_id INTEGER NOT NULL,
            piece_id INTEGER NOT NULL,
            PRIMARY KEY (user_id, piece_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (piece_id) REFERENCES writing_pieces(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS writing_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            piece_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (piece_id) REFERENCES writing_pieces(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS topic_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        );
    ''')
    db.commit()
    db.close()

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def time_ago(dt_str):
    try:
        dt = datetime.strptime(str(dt_str)[:19], '%Y-%m-%d %H:%M:%S')
        diff = datetime.utcnow() - dt
        s = int(diff.total_seconds())
        if s < 60: return f"{s}s"
        if s < 3600: return f"{s//60}m"
        if s < 86400: return f"{s//3600}h"
        return f"{s//86400}d"
    except Exception:
        return ''

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def current_user():
    if 'user_id' not in session:
        return None
    return get_db().execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()

def unread_count():
    if 'user_id' not in session:
        return 0
    c = get_db().execute(
        'SELECT COUNT(*) as c FROM messages WHERE receiver_id=? AND is_read=0',
        (session['user_id'],)
    ).fetchone()
    return c['c'] if c else 0

# ── AUTH ────────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        display_name = request.form.get('display_name','').strip()
        password = request.form.get('password','')
        genre = request.form.get('genre','').strip()
        bio = request.form.get('bio','').strip()
        if not username or not display_name or not password:
            flash('Fill in all required fields.', 'error')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('register'))
        db = get_db()
        if db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone():
            flash('Username already taken.', 'error')
            return redirect(url_for('register'))
        db.execute('INSERT INTO users (username,display_name,bio,genre,password_hash) VALUES (?,?,?,?,?)',
                   (username, display_name, bio, genre, hash_password(password)))
        db.commit()
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        session['user_id'] = user['id']
        session['username'] = user['username']
        flash(f"Welcome, {display_name}! 🖊️", 'success')
        return redirect(url_for('feed'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        password = request.form.get('password','')
        user = get_db().execute(
            'SELECT * FROM users WHERE username=? AND password_hash=?',
            (username, hash_password(password))
        ).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('feed'))
        flash('Wrong username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── FEED ────────────────────────────────────────────────────────────────────

@app.route('/')
def feed():
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    if user:
        posts = db.execute('''
            SELECT p.*, u.username, u.display_name, u.avatar_url,
                   COUNT(DISTINCT l.user_id) as like_count,
                   COUNT(DISTINCT c.id) as comment_count,
                   EXISTS(SELECT 1 FROM likes WHERE user_id=? AND post_id=p.id) as user_liked
            FROM posts p JOIN users u ON p.user_id=u.id
            LEFT JOIN likes l ON l.post_id=p.id
            LEFT JOIN comments c ON c.post_id=p.id
            WHERE p.user_id=? OR p.user_id IN (SELECT following_id FROM follows WHERE follower_id=?)
            GROUP BY p.id ORDER BY p.created_at DESC LIMIT 60
        ''', (uid, uid, uid)).fetchall()
    else:
        posts = db.execute('''
            SELECT p.*, u.username, u.display_name, u.avatar_url,
                   COUNT(DISTINCT l.user_id) as like_count,
                   COUNT(DISTINCT c.id) as comment_count, 0 as user_liked
            FROM posts p JOIN users u ON p.user_id=u.id
            LEFT JOIN likes l ON l.post_id=p.id
            LEFT JOIN comments c ON c.post_id=p.id
            GROUP BY p.id ORDER BY p.created_at DESC LIMIT 60
        ''').fetchall()
    posts = [dict(p) for p in posts]
    for p in posts:
        p['time_ago'] = time_ago(p['created_at'])
    msgs = unread_count()
    return render_template('feed.html', posts=posts, user=user, unread=msgs)

# ── EXPLORE ─────────────────────────────────────────────────────────────────

@app.route('/explore')
def explore():
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    authors = db.execute('''
        SELECT u.*, COUNT(DISTINCT p.id) as post_count,
               COUNT(DISTINCT f.follower_id) as follower_count
        FROM users u
        LEFT JOIN posts p ON p.user_id=u.id
        LEFT JOIN follows f ON f.following_id=u.id
        GROUP BY u.id ORDER BY follower_count DESC, post_count DESC
    ''').fetchall()
    authors = [dict(a) for a in authors]
    if user:
        following_ids = {r['following_id'] for r in db.execute(
            'SELECT following_id FROM follows WHERE follower_id=?', (uid,)
        ).fetchall()}
        for a in authors:
            a['is_following'] = a['id'] in following_ids
            a['is_me'] = a['id'] == uid
    msgs = unread_count()
    return render_template('explore.html', authors=authors, user=user, unread=msgs)

# ── POSTS ───────────────────────────────────────────────────────────────────

@app.route('/post/create', methods=['GET','POST'])
@login_required
def create_post():
    if request.method == 'POST':
        post_type = request.form.get('post_type','thought')
        content = request.form.get('content','').strip()
        media_url = request.form.get('media_url','').strip()
        event_date = request.form.get('event_date','').strip()
        event_location = request.form.get('event_location','').strip()
        if not content:
            flash('Add some content first.', 'error')
            return redirect(url_for('create_post'))
        db = get_db()
        db.execute('INSERT INTO posts (user_id,post_type,content,media_url,event_date,event_location) VALUES (?,?,?,?,?,?)',
                   (session['user_id'], post_type, content, media_url, event_date, event_location))
        db.commit()
        flash('Posted! ✨', 'success')
        return redirect(url_for('feed'))
    user = current_user()
    post_type = request.args.get('type','thought')
    msgs = unread_count()
    return render_template('create_post.html', user=user, post_type=post_type, unread=msgs)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    post = db.execute('''
        SELECT p.*, u.username, u.display_name, u.avatar_url,
               COUNT(DISTINCT l.user_id) as like_count,
               EXISTS(SELECT 1 FROM likes WHERE user_id=? AND post_id=p.id) as user_liked
        FROM posts p JOIN users u ON p.user_id=u.id
        LEFT JOIN likes l ON l.post_id=p.id
        WHERE p.id=? GROUP BY p.id
    ''', (uid, post_id)).fetchone()
    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('feed'))
    comments = db.execute('''
        SELECT c.*, u.username, u.display_name, u.avatar_url
        FROM comments c JOIN users u ON c.user_id=u.id
        WHERE c.post_id=? ORDER BY c.created_at ASC
    ''', (post_id,)).fetchall()
    post = dict(post)
    post['time_ago'] = time_ago(post['created_at'])
    comments = [dict(c) for c in comments]
    for c in comments:
        c['time_ago'] = time_ago(c['created_at'])
    msgs = unread_count()
    return render_template('view_post.html', post=post, comments=comments, user=user, unread=msgs)

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    db = get_db()
    uid = session['user_id']
    existing = db.execute('SELECT 1 FROM likes WHERE user_id=? AND post_id=?', (uid, post_id)).fetchone()
    if existing:
        db.execute('DELETE FROM likes WHERE user_id=? AND post_id=?', (uid, post_id))
        liked = False
    else:
        db.execute('INSERT INTO likes (user_id,post_id) VALUES (?,?)', (uid, post_id))
        liked = True
    db.commit()
    count = db.execute('SELECT COUNT(*) as c FROM likes WHERE post_id=?', (post_id,)).fetchone()['c']
    return jsonify({'liked': liked, 'count': count})

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment_post(post_id):
    content = request.form.get('content','').strip()
    if content:
        db = get_db()
        db.execute('INSERT INTO comments (user_id,post_id,content) VALUES (?,?,?)',
                   (session['user_id'], post_id, content))
        db.commit()
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    db = get_db()
    post = db.execute('SELECT user_id FROM posts WHERE id=?', (post_id,)).fetchone()
    if post and post['user_id'] == session['user_id']:
        db.execute('DELETE FROM posts WHERE id=?', (post_id,))
        db.commit()
    return redirect(url_for('feed'))

# ── PROFILE ─────────────────────────────────────────────────────────────────

@app.route('/profile/<username>')
def profile(username):
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    author = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not author:
        flash('Author not found.', 'error')
        return redirect(url_for('explore'))
    posts = db.execute('''
        SELECT p.*, u.username, u.display_name, u.avatar_url,
               COUNT(DISTINCT l.user_id) as like_count,
               COUNT(DISTINCT c.id) as comment_count,
               EXISTS(SELECT 1 FROM likes WHERE user_id=? AND post_id=p.id) as user_liked
        FROM posts p JOIN users u ON p.user_id=u.id
        LEFT JOIN likes l ON l.post_id=p.id
        LEFT JOIN comments c ON c.post_id=p.id
        WHERE p.user_id=? GROUP BY p.id ORDER BY p.created_at DESC
    ''', (uid, author['id'])).fetchall()
    books = db.execute('SELECT * FROM books WHERE user_id=? ORDER BY created_at DESC', (author['id'],)).fetchall()
    follower_count = db.execute('SELECT COUNT(*) as c FROM follows WHERE following_id=?', (author['id'],)).fetchone()['c']
    following_count = db.execute('SELECT COUNT(*) as c FROM follows WHERE follower_id=?', (author['id'],)).fetchone()['c']
    is_following = bool(db.execute('SELECT 1 FROM follows WHERE follower_id=? AND following_id=?', (uid, author['id'])).fetchone()) if user else False
    posts = [dict(p) for p in posts]
    for p in posts:
        p['time_ago'] = time_ago(p['created_at'])
    msgs = unread_count()
    return render_template('profile.html', author=dict(author), posts=posts, books=[dict(b) for b in books],
                           follower_count=follower_count, following_count=following_count,
                           is_following=is_following, user=user,
                           is_me=(user and user['id'] == author['id']), unread=msgs)

@app.route('/profile/edit', methods=['GET','POST'])
@login_required
def edit_profile():
    db = get_db()
    user = current_user()
    if request.method == 'POST':
        avatar_url = user['avatar_url'] or ''
        if 'avatar_file' in request.files:
            file = request.files['avatar_file']
            if file and file.filename:
                file_data = file.read()
                if len(file_data) <= 5 * 1024 * 1024:
                    mimetype = file.content_type or 'image/jpeg'
                    b64 = base64.b64encode(file_data).decode('utf-8')
                    avatar_url = f"data:{mimetype};base64,{b64}"
                else:
                    flash('Photo too large. Please use a photo under 5MB.', 'error')
        db.execute('UPDATE users SET display_name=?,bio=?,genre=?,avatar_url=?,website=? WHERE id=?',
                   (request.form.get('display_name','').strip(),
                    request.form.get('bio','').strip(),
                    request.form.get('genre','').strip(),
                    avatar_url,
                    request.form.get('website','').strip(),
                    user['id']))
        db.commit()
        flash('Profile updated! ✨', 'success')
        return redirect(url_for('profile', username=user['username']))
    msgs = unread_count()
    return render_template('edit_profile.html', user=user, unread=msgs)

# ── FOLLOW ──────────────────────────────────────────────────────────────────

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    db = get_db()
    target = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
    if not target or target['id'] == session['user_id']:
        return jsonify({'error': 'invalid'}), 400
    existing = db.execute('SELECT 1 FROM follows WHERE follower_id=? AND following_id=?',
                          (session['user_id'], target['id'])).fetchone()
    if existing:
        db.execute('DELETE FROM follows WHERE follower_id=? AND following_id=?', (session['user_id'], target['id']))
        following = False
    else:
        db.execute('INSERT INTO follows (follower_id,following_id) VALUES (?,?)', (session['user_id'], target['id']))
        following = True
    db.commit()
    count = db.execute('SELECT COUNT(*) as c FROM follows WHERE following_id=?', (target['id'],)).fetchone()['c']
    return jsonify({'following': following, 'follower_count': count})

# ── BOOKS ───────────────────────────────────────────────────────────────────

@app.route('/books')
def books():
    db = get_db()
    user = current_user()
    featured = db.execute('''
        SELECT b.*, u.username, u.display_name, u.avatar_url
        FROM books b JOIN users u ON b.user_id=u.id
        WHERE b.book_type='featured' ORDER BY b.created_at DESC LIMIT 6
    ''').fetchall()
    new_releases = db.execute('''
        SELECT b.*, u.username, u.display_name, u.avatar_url
        FROM books b JOIN users u ON b.user_id=u.id
        WHERE b.book_type='published' ORDER BY b.created_at DESC LIMIT 20
    ''').fetchall()
    upcoming = db.execute('''
        SELECT b.*, u.username, u.display_name, u.avatar_url
        FROM books b JOIN users u ON b.user_id=u.id
        WHERE b.book_type='upcoming' ORDER BY b.release_date ASC LIMIT 12
    ''').fetchall()
    msgs = unread_count()
    return render_template('books.html', user=user, featured=[dict(b) for b in featured],
                           new_releases=[dict(b) for b in new_releases],
                           upcoming=[dict(b) for b in upcoming], unread=msgs)

@app.route('/books/add', methods=['GET','POST'])
@login_required
def add_book():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        author_name = request.form.get('author_name','').strip()
        genre = request.form.get('genre','').strip()
        description = request.form.get('description','').strip()
        cover_url = request.form.get('cover_url','').strip()
        buy_link = request.form.get('buy_link','').strip()
        release_date = request.form.get('release_date','').strip()
        book_type = request.form.get('book_type','published')
        if not title or not author_name:
            flash('Book title and author name are required.', 'error')
            return redirect(url_for('add_book'))
        db = get_db()
        db.execute('''INSERT INTO books (user_id,title,author_name,genre,description,cover_url,buy_link,release_date,book_type)
                      VALUES (?,?,?,?,?,?,?,?,?)''',
                   (session['user_id'], title, author_name, genre, description, cover_url, buy_link, release_date, book_type))
        db.commit()
        flash('Book added! 📚', 'success')
        return redirect(url_for('profile', username=session['username']))
    user = current_user()
    msgs = unread_count()
    return render_template('add_book.html', user=user, unread=msgs)

@app.route('/books/<int:book_id>/delete', methods=['POST'])
@login_required
def delete_book(book_id):
    db = get_db()
    book = db.execute('SELECT user_id FROM books WHERE id=?', (book_id,)).fetchone()
    if book and book['user_id'] == session['user_id']:
        db.execute('DELETE FROM books WHERE id=?', (book_id,))
        db.commit()
    return redirect(url_for('profile', username=session['username']))

# ── CONFESSIONS ─────────────────────────────────────────────────────────────

@app.route('/confessions')
def confessions():
    db = get_db()
    user = current_user()
    category = request.args.get('cat', 'all')
    if category == 'all':
        items = db.execute('SELECT * FROM confessions ORDER BY created_at DESC LIMIT 50').fetchall()
    else:
        items = db.execute('SELECT * FROM confessions WHERE category=? ORDER BY created_at DESC LIMIT 50', (category,)).fetchall()
    items = [dict(i) for i in items]
    for i in items:
        i['time_ago'] = time_ago(i['created_at'])
    msgs = unread_count()
    return render_template('confessions.html', user=user, confessions=items, category=category, unread=msgs)

@app.route('/confessions/post', methods=['POST'])
def post_confession():
    content = request.form.get('content','').strip()
    category = request.form.get('category','writer')
    if not content or len(content) > 500:
        flash('Confession must be 1–500 characters.', 'error')
        return redirect(url_for('confessions'))
    db = get_db()
    db.execute('INSERT INTO confessions (content,category) VALUES (?,?)', (content, category))
    db.commit()
    flash('Your confession has been shared anonymously. 🤫', 'success')
    return redirect(url_for('confessions'))

@app.route('/confessions/<int:conf_id>/like', methods=['POST'])
def like_confession(conf_id):
    db = get_db()
    db.execute('UPDATE confessions SET like_count=like_count+1 WHERE id=?', (conf_id,))
    db.commit()
    c = db.execute('SELECT like_count FROM confessions WHERE id=?', (conf_id,)).fetchone()
    return jsonify({'count': c['like_count'] if c else 0})

# ── EVENTS ──────────────────────────────────────────────────────────────────

@app.route('/events')
def events():
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    upcoming = db.execute('''
        SELECT e.*, u.username, u.display_name, u.avatar_url,
               COUNT(DISTINCT r.user_id) as rsvp_count
        FROM events e JOIN users u ON e.user_id=u.id
        LEFT JOIN event_rsvps r ON r.event_id=e.id
        WHERE e.event_date >= date('now')
        GROUP BY e.id ORDER BY e.event_date ASC LIMIT 30
    ''').fetchall()
    past = db.execute('''
        SELECT e.*, u.username, u.display_name, u.avatar_url,
               COUNT(DISTINCT r.user_id) as rsvp_count
        FROM events e JOIN users u ON e.user_id=u.id
        LEFT JOIN event_rsvps r ON r.event_id=e.id
        WHERE e.event_date < date('now')
        GROUP BY e.id ORDER BY e.event_date DESC LIMIT 10
    ''').fetchall()
    rsvp_ids = set()
    if user:
        rsvp_ids = {r['event_id'] for r in db.execute('SELECT event_id FROM event_rsvps WHERE user_id=?', (uid,)).fetchall()}
    msgs = unread_count()
    return render_template('events.html', user=user, upcoming=[dict(e) for e in upcoming],
                           past=[dict(e) for e in past], rsvp_ids=rsvp_ids, unread=msgs)

@app.route('/events/create', methods=['GET','POST'])
@login_required
def create_event():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        description = request.form.get('description','').strip()
        event_date = request.form.get('event_date','').strip()
        event_time = request.form.get('event_time','').strip()
        location = request.form.get('location','').strip()
        event_type = request.form.get('event_type','virtual')
        link = request.form.get('link','').strip()
        if not title or not event_date:
            flash('Title and date are required.', 'error')
            return redirect(url_for('create_event'))
        db = get_db()
        db.execute('''INSERT INTO events (user_id,title,description,event_date,event_time,location,event_type,link)
                      VALUES (?,?,?,?,?,?,?,?)''',
                   (session['user_id'], title, description, event_date, event_time, location, event_type, link))
        db.commit()
        flash('Event created! 📅', 'success')
        return redirect(url_for('events'))
    user = current_user()
    msgs = unread_count()
    return render_template('create_event.html', user=user, unread=msgs)

@app.route('/events/<int:event_id>/rsvp', methods=['POST'])
@login_required
def rsvp_event(event_id):
    db = get_db()
    uid = session['user_id']
    existing = db.execute('SELECT 1 FROM event_rsvps WHERE user_id=? AND event_id=?', (uid, event_id)).fetchone()
    if existing:
        db.execute('DELETE FROM event_rsvps WHERE user_id=? AND event_id=?', (uid, event_id))
        going = False
    else:
        db.execute('INSERT INTO event_rsvps (user_id,event_id) VALUES (?,?)', (uid, event_id))
        going = True
    db.commit()
    count = db.execute('SELECT COUNT(*) as c FROM event_rsvps WHERE event_id=?', (event_id,)).fetchone()['c']
    return jsonify({'going': going, 'count': count})

@app.route('/events/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    db = get_db()
    ev = db.execute('SELECT user_id FROM events WHERE id=?', (event_id,)).fetchone()
    if ev and ev['user_id'] == session['user_id']:
        db.execute('DELETE FROM events WHERE id=?', (event_id,))
        db.commit()
    return redirect(url_for('events'))

# ── DIRECT MESSAGES ─────────────────────────────────────────────────────────

@app.route('/messages')
@login_required
def messages():
    db = get_db()
    user = current_user()
    uid = user['id']
    convos = db.execute('''
        SELECT u.id, u.username, u.display_name, u.avatar_url,
               MAX(m.created_at) as last_at,
               SUM(CASE WHEN m.receiver_id=? AND m.is_read=0 THEN 1 ELSE 0 END) as unread_msgs,
               (SELECT content FROM messages
                WHERE (sender_id=u.id AND receiver_id=?) OR (sender_id=? AND receiver_id=u.id)
                ORDER BY created_at DESC LIMIT 1) as last_msg
        FROM messages m
        JOIN users u ON (
            CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END = u.id
        )
        WHERE m.sender_id=? OR m.receiver_id=?
        GROUP BY u.id ORDER BY last_at DESC
    ''', (uid, uid, uid, uid, uid, uid)).fetchall()
    msgs = unread_count()
    return render_template('messages.html', user=user, convos=[dict(c) for c in convos], unread=msgs)

@app.route('/messages/<username>', methods=['GET','POST'])
@login_required
def conversation(username):
    db = get_db()
    user = current_user()
    uid = user['id']
    partner = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not partner:
        flash('User not found.', 'error')
        return redirect(url_for('messages'))
    if request.method == 'POST':
        content = request.form.get('content','').strip()
        if content:
            db.execute('INSERT INTO messages (sender_id,receiver_id,content) VALUES (?,?,?)',
                       (uid, partner['id'], content))
            db.commit()
        return redirect(url_for('conversation', username=username))
    db.execute('UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=?', (partner['id'], uid))
    db.commit()
    thread = db.execute('''
        SELECT m.*, u.username, u.display_name, u.avatar_url
        FROM messages m JOIN users u ON m.sender_id=u.id
        WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
        ORDER BY m.created_at ASC LIMIT 100
    ''', (uid, partner['id'], partner['id'], uid)).fetchall()
    thread = [dict(m) for m in thread]
    for m in thread:
        m['time_ago'] = time_ago(m['created_at'])
    msgs = unread_count()
    return render_template('conversation.html', user=user, partner=dict(partner), thread=thread, unread=msgs)

# ── COMMUNITY WRITING ────────────────────────────────────────────────────────

@app.route('/writing')
def writing():
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    piece_type = request.args.get('type','all')
    if piece_type == 'all':
        pieces = db.execute('''
            SELECT wp.*, u.username, u.display_name, u.avatar_url,
                   COUNT(DISTINCT wl.user_id) as like_count,
                   COUNT(DISTINCT wc.id) as comment_count,
                   EXISTS(SELECT 1 FROM writing_likes WHERE user_id=? AND piece_id=wp.id) as user_liked
            FROM writing_pieces wp JOIN users u ON wp.user_id=u.id
            LEFT JOIN writing_likes wl ON wl.piece_id=wp.id
            LEFT JOIN writing_comments wc ON wc.piece_id=wp.id
            GROUP BY wp.id ORDER BY wp.created_at DESC LIMIT 40
        ''', (uid,)).fetchall()
    else:
        pieces = db.execute('''
            SELECT wp.*, u.username, u.display_name, u.avatar_url,
                   COUNT(DISTINCT wl.user_id) as like_count,
                   COUNT(DISTINCT wc.id) as comment_count,
                   EXISTS(SELECT 1 FROM writing_likes WHERE user_id=? AND piece_id=wp.id) as user_liked
            FROM writing_pieces wp JOIN users u ON wp.user_id=u.id
            LEFT JOIN writing_likes wl ON wl.piece_id=wp.id
            LEFT JOIN writing_comments wc ON wc.piece_id=wp.id
            WHERE wp.piece_type=?
            GROUP BY wp.id ORDER BY wp.created_at DESC LIMIT 40
        ''', (uid, piece_type)).fetchall()
    pieces = [dict(p) for p in pieces]
    for p in pieces:
        p['time_ago'] = time_ago(p['created_at'])
    msgs = unread_count()
    return render_template('writing.html', user=user, pieces=pieces, piece_type=piece_type, unread=msgs)

@app.route('/writing/submit', methods=['GET','POST'])
@login_required
def submit_writing():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        genre = request.form.get('genre','').strip()
        piece_type = request.form.get('piece_type','story')
        content = request.form.get('content','').strip()
        excerpt = content[:200] + '...' if len(content) > 200 else content
        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('submit_writing'))
        db = get_db()
        db.execute('''INSERT INTO writing_pieces (user_id,title,genre,piece_type,excerpt,content)
                      VALUES (?,?,?,?,?,?)''',
                   (session['user_id'], title, genre, piece_type, excerpt, content))
        db.commit()
        flash('Your piece has been shared! ✍️', 'success')
        return redirect(url_for('writing'))
    user = current_user()
    msgs = unread_count()
    return render_template('submit_writing.html', user=user, unread=msgs)

@app.route('/writing/<int:piece_id>')
def view_writing(piece_id):
    db = get_db()
    user = current_user()
    uid = user['id'] if user else 0
    piece = db.execute('''
        SELECT wp.*, u.username, u.display_name, u.avatar_url,
               COUNT(DISTINCT wl.user_id) as like_count,
               EXISTS(SELECT 1 FROM writing_likes WHERE user_id=? AND piece_id=wp.id) as user_liked
        FROM writing_pieces wp JOIN users u ON wp.user_id=u.id
        LEFT JOIN writing_likes wl ON wl.piece_id=wp.id
        WHERE wp.id=? GROUP BY wp.id
    ''', (uid, piece_id)).fetchone()
    if not piece:
        flash('Piece not found.', 'error')
        return redirect(url_for('writing'))
    comments = db.execute('''
        SELECT wc.*, u.username, u.display_name, u.avatar_url
        FROM writing_comments wc JOIN users u ON wc.user_id=u.id
        WHERE wc.piece_id=? ORDER BY wc.created_at ASC
    ''', (piece_id,)).fetchall()
    piece = dict(piece)
    piece['time_ago'] = time_ago(piece['created_at'])
    comments = [dict(c) for c in comments]
    for c in comments:
        c['time_ago'] = time_ago(c['created_at'])
    msgs = unread_count()
    return render_template('view_writing.html', user=user, piece=piece, comments=comments, unread=msgs)

@app.route('/writing/<int:piece_id>/like', methods=['POST'])
@login_required
def like_writing(piece_id):
    db = get_db()
    uid = session['user_id']
    existing = db.execute('SELECT 1 FROM writing_likes WHERE user_id=? AND piece_id=?', (uid, piece_id)).fetchone()
    if existing:
        db.execute('DELETE FROM writing_likes WHERE user_id=? AND piece_id=?', (uid, piece_id))
        liked = False
    else:
        db.execute('INSERT INTO writing_likes (user_id,piece_id) VALUES (?,?)', (uid, piece_id))
        liked = True
    db.commit()
    count = db.execute('SELECT COUNT(*) as c FROM writing_likes WHERE piece_id=?', (piece_id,)).fetchone()['c']
    return jsonify({'liked': liked, 'count': count})

@app.route('/writing/<int:piece_id>/comment', methods=['POST'])
@login_required
def comment_writing(piece_id):
    content = request.form.get('content','').strip()
    if content:
        db = get_db()
        db.execute('INSERT INTO writing_comments (user_id,piece_id,content) VALUES (?,?,?)',
                   (session['user_id'], piece_id, content))
        db.commit()
    return redirect(url_for('view_writing', piece_id=piece_id))

@app.route('/writing/<int:piece_id>/delete', methods=['POST'])
@login_required
def delete_writing(piece_id):
    db = get_db()
    piece = db.execute('SELECT user_id FROM writing_pieces WHERE id=?', (piece_id,)).fetchone()
    if piece and piece['user_id'] == session['user_id']:
        db.execute('DELETE FROM writing_pieces WHERE id=?', (piece_id,))
        db.commit()
    return redirect(url_for('writing'))

# ── COFFEE TALK ─────────────────────────────────────────────────────────────

@app.route('/coffee-talk')
def coffee_talk():
    db = get_db()
    user = current_user()
    category = request.args.get('cat','all')
    if category == 'all':
        topics = db.execute('''
            SELECT t.*, u.username, u.display_name, u.avatar_url,
                   COUNT(DISTINCT r.id) as reply_count
            FROM topics t JOIN users u ON t.user_id=u.id
            LEFT JOIN topic_replies r ON r.topic_id=t.id
            GROUP BY t.id ORDER BY t.created_at DESC LIMIT 40
        ''').fetchall()
    else:
        topics = db.execute('''
            SELECT t.*, u.username, u.display_name, u.avatar_url,
                   COUNT(DISTINCT r.id) as reply_count
            FROM topics t JOIN users u ON t.user_id=u.id
            LEFT JOIN topic_replies r ON r.topic_id=t.id
            WHERE t.category=?
            GROUP BY t.id ORDER BY t.created_at DESC LIMIT 40
        ''', (category,)).fetchall()
    topics = [dict(t) for t in topics]
    for t in topics:
        t['time_ago'] = time_ago(t['created_at'])
    msgs = unread_count()
    return render_template('coffee_talk.html', user=user, topics=topics, category=category, unread=msgs)

@app.route('/coffee-talk/create', methods=['GET','POST'])
@login_required
def create_topic():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        content = request.form.get('content','').strip()
        category = request.form.get('category','general')
        if not title or not content:
            flash('Title and content are required.', 'error')
            return redirect(url_for('create_topic'))
        db = get_db()
        db.execute('INSERT INTO topics (user_id,title,content,category) VALUES (?,?,?,?)',
                   (session['user_id'], title, content, category))
        db.commit()
        flash('Discussion started! ☕', 'success')
        return redirect(url_for('coffee_talk'))
    user = current_user()
    msgs = unread_count()
    return render_template('create_topic.html', user=user, unread=msgs)

@app.route('/coffee-talk/<int:topic_id>', methods=['GET','POST'])
def view_topic(topic_id):
    db = get_db()
    user = current_user()
    topic = db.execute('''
        SELECT t.*, u.username, u.display_name, u.avatar_url
        FROM topics t JOIN users u ON t.user_id=u.id WHERE t.id=?
    ''', (topic_id,)).fetchone()
    if not topic:
        flash('Topic not found.', 'error')
        return redirect(url_for('coffee_talk'))
    if request.method == 'POST':
        if not user:
            return redirect(url_for('login'))
        content = request.form.get('content','').strip()
        if content:
            db.execute('INSERT INTO topic_replies (user_id,topic_id,content) VALUES (?,?,?)',
                       (user['id'], topic_id, content))
            db.commit()
        return redirect(url_for('view_topic', topic_id=topic_id))
    replies = db.execute('''
        SELECT r.*, u.username, u.display_name, u.avatar_url
        FROM topic_replies r JOIN users u ON r.user_id=u.id
        WHERE r.topic_id=? ORDER BY r.created_at ASC
    ''', (topic_id,)).fetchall()
    topic = dict(topic)
    topic['time_ago'] = time_ago(topic['created_at'])
    replies = [dict(r) for r in replies]
    for r in replies:
        r['time_ago'] = time_ago(r['created_at'])
    msgs = unread_count()
    return render_template('view_topic.html', user=user, topic=topic, replies=replies, unread=msgs)

@app.route('/coffee-talk/<int:topic_id>/delete', methods=['POST'])
@login_required
def delete_topic(topic_id):
    db = get_db()
    t = db.execute('SELECT user_id FROM topics WHERE id=?', (topic_id,)).fetchone()
    if t and t['user_id'] == session['user_id']:
        db.execute('DELETE FROM topics WHERE id=?', (topic_id,))
        db.commit()
    return redirect(url_for('coffee_talk'))

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
