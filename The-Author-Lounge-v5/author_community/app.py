import os
import hashlib
import sqlite3
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
    return render_template('feed.html', posts=posts, user=user)

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
    return render_template('explore.html', authors=authors, user=user)

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
    return render_template('create_post.html', user=user, post_type=post_type)

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
    return render_template('view_post.html', post=post, comments=comments, user=user)

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
    follower_count = db.execute('SELECT COUNT(*) as c FROM follows WHERE following_id=?', (author['id'],)).fetchone()['c']
    following_count = db.execute('SELECT COUNT(*) as c FROM follows WHERE follower_id=?', (author['id'],)).fetchone()['c']
    is_following = bool(db.execute('SELECT 1 FROM follows WHERE follower_id=? AND following_id=?', (uid, author['id'])).fetchone()) if user else False
    posts = [dict(p) for p in posts]
    for p in posts:
        p['time_ago'] = time_ago(p['created_at'])
    return render_template('profile.html', author=dict(author), posts=posts,
                           follower_count=follower_count, following_count=following_count,
                           is_following=is_following, user=user,
                           is_me=(user and user['id'] == author['id']))

@app.route('/profile/edit', methods=['GET','POST'])
@login_required
def edit_profile():
    db = get_db()
    user = current_user()
    if request.method == 'POST':
        db.execute('UPDATE users SET display_name=?,bio=?,genre=?,avatar_url=?,website=? WHERE id=?',
                   (request.form.get('display_name','').strip(),
                    request.form.get('bio','').strip(),
                    request.form.get('genre','').strip(),
                    request.form.get('avatar_url','').strip(),
                    request.form.get('website','').strip(),
                    user['id']))
        db.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile', username=user['username']))
    return render_template('edit_profile.html', user=user)

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

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
