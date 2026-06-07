# 🖊️ Ink & Pages — Author Community Platform

A social platform built just for authors. Share thoughts, snaps, reels, and book signing events. Follow fellow authors. Build your community.

---

## Features

- **💭 Thoughts** — Share what's on your author mind
- **📸 Snaps** — Post photos from your writing life
- **🎬 Reels** — Share video links (YouTube, etc.)
- **📅 Events** — Announce book signings and appearances
- **Follow system** — Follow your favorite authors
- **Likes & Comments** — Engage with the community
- **Author profiles** — Bio, genre, stats, post history
- **Mobile-first design** — Works great on phones

---

## Deploy for Free on Railway (Recommended)

Railway gives you a live public URL at no cost.

### Steps:

1. **Create a free account** at [railway.app](https://railway.app)

2. **Upload your project:**
   - Click **New Project** → **Deploy from GitHub**
   - OR click **Deploy from local** and drag your project folder

3. **Set an environment variable:**
   - In your Railway project → Settings → Variables
   - Add: `SECRET_KEY` = (any long random phrase, e.g. `my-golden-pen-secret-2024`)

4. **That's it!** Railway auto-detects Python and installs everything. Your site goes live in ~2 minutes.

---

## Run Locally (on your own computer)

If you want to test it on your own machine first:

1. **Install Python** from [python.org](https://python.org) (version 3.9+)

2. **Open Terminal / Command Prompt** in the `author_community` folder

3. Run these commands:
   ```
   pip install flask gunicorn
   python app.py
   ```

4. Open your browser and go to: **http://localhost:5000**

---

## File Structure

```
author_community/
├── app.py              ← All the server code
├── wsgi.py             ← Production entry point
├── requirements.txt    ← Python packages needed
├── Procfile            ← Tells Railway how to start the app
├── static/
│   ├── style.css       ← All the styling
│   └── app.js          ← Interactive features (likes, follows)
└── templates/
    ├── base.html        ← Shared layout (header, nav)
    ├── login.html       ← Sign in page
    ├── register.html    ← Join page
    ├── feed.html        ← Home feed
    ├── create_post.html ← New post form
    ├── view_post.html   ← Single post + comments
    ├── profile.html     ← Author profile
    ├── explore.html     ← Discover authors
    └── edit_profile.html← Edit your profile
```

---

## Customization

- **App name / branding**: Search for "Ink & Pages" in the HTML templates and replace with your name
- **Colors**: Edit `static/style.css` — change `--gold`, `--dark`, etc. at the top
- **Genre list**: Edit the `<select>` options in `register.html` and `edit_profile.html`

---

Built with Flask + SQLite. No paid services required.
