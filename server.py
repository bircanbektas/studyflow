from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os, json, time, re, secrets

app = Flask(__name__, static_folder="static")

DATABASE_URL = os.environ.get("DATABASE_URL")
USERNAME_RE = re.compile(r"^[a-z0-9çğıöşü_.-]{2,20}$")
MIN_PASSWORD = 4

if DATABASE_URL:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    def get_conn():
        return psycopg2.connect(DATABASE_URL)

    def run(sql, params=(), fetch=None):
        conn = get_conn()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            result = None
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            conn.commit()
            cur.close()
            return result
        finally:
            conn.close()

    def init_db():
        run("""
            CREATE TABLE IF NOT EXISTS user_data (
                username TEXT PRIMARY KEY,
                sessions JSONB DEFAULT '{}',
                subjects JSONB DEFAULT '{}',
                active JSONB DEFAULT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        run("ALTER TABLE user_data ADD COLUMN IF NOT EXISTS password_hash TEXT")
        run("ALTER TABLE user_data ADD COLUMN IF NOT EXISTS settings JSONB DEFAULT '{}'")
        run("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

    init_db()

    def db_check():
        run("SELECT 1")

    def db_get_all():
        rows = run("SELECT username, sessions, subjects, active, settings FROM user_data", fetch="all")
        return {
            row["username"]: {
                "sessions": row["sessions"] or {},
                "subjects": row["subjects"] or {},
                "active": row["active"],
                "settings": row["settings"] or {},
            }
            for row in rows
        }

    def db_get_password_hash(username):
        row = run("SELECT password_hash FROM user_data WHERE username = %s", (username,), fetch="one")
        return (row is not None, row["password_hash"] if row else None)

    def db_set_password_hash(username, password_hash):
        run("""
            INSERT INTO user_data (username, password_hash, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (username) DO UPDATE SET password_hash = %s, updated_at = NOW()
        """, (username, password_hash, password_hash))

    def db_upsert(username, field, value):
        assert field in ("sessions", "subjects", "active", "settings")
        run(f"""
            INSERT INTO user_data (username, {field}, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (username) DO UPDATE SET {field} = %s, updated_at = NOW()
        """, (username, json.dumps(value), json.dumps(value)))

    def db_clear_active(username):
        run("UPDATE user_data SET active = NULL WHERE username = %s", (username,))

    def db_add_token(token, username):
        run("INSERT INTO auth_tokens (token, username) VALUES (%s, %s)", (token, username))

    def db_token_user(token):
        row = run("SELECT username FROM auth_tokens WHERE token = %s", (token,), fetch="one")
        return row["username"] if row else None

    def db_delete_token(token):
        run("DELETE FROM auth_tokens WHERE token = %s", (token,))

else:
    import threading
    DATA_FILE = "data.json"
    file_lock = threading.RLock()  # aynı anda gelen istekler dosyayı bozmasın

    def locked(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            with file_lock:
                return f(*args, **kwargs)
        return wrapper

    def load():
        if not os.path.exists(DATA_FILE):
            return {"users": {}, "tokens": {}}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "users" not in data:  # eski format: {username: {...}}
            data = {"users": data, "tokens": {}}
        return data

    def save(data):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @locked
    def db_check():
        load()

    @locked
    def db_get_all():
        return {
            name: {
                "sessions": u.get("sessions") or {},
                "subjects": u.get("subjects") or {},
                "active": u.get("active"),
                "settings": u.get("settings") or {},
            }
            for name, u in load()["users"].items()
        }

    @locked
    def db_get_password_hash(username):
        users = load()["users"]
        return (username in users, users.get(username, {}).get("password_hash"))

    @locked
    def db_set_password_hash(username, password_hash):
        data = load()
        data["users"].setdefault(username, {})["password_hash"] = password_hash
        save(data)

    @locked
    def db_upsert(username, field, value):
        data = load()
        data["users"].setdefault(username, {})[field] = value
        save(data)

    @locked
    def db_clear_active(username):
        data = load()
        if username in data["users"]:
            data["users"][username]["active"] = None
            save(data)

    @locked
    def db_add_token(token, username):
        data = load()
        data["tokens"][token] = username
        save(data)

    @locked
    def db_token_user(token):
        return load()["tokens"].get(token)

    @locked
    def db_delete_token(token):
        data = load()
        data["tokens"].pop(token, None)
        save(data)


def current_token():
    header = request.headers.get("Authorization", "")
    return header[7:] if header.startswith("Bearer ") else None

def require_auth(f):
    """Token'ı doğrular; URL'de kullanıcı adı varsa token sahibiyle eşleşmeli."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = current_token()
        user = db_token_user(token) if token else None
        if not user:
            return jsonify({"error": "Oturum geçersiz, tekrar giriş yap."}), 401
        if "username" in kwargs and kwargs["username"] != user:
            return jsonify({"error": "Bu kullanıcı için yetkin yok."}), 403
        return f(*args, **kwargs)
    return wrapper


@app.route("/health")
def health():
    try:
        db_check()
        return "ok", 200
    except Exception as e:
        return f"db error: {e}", 500

@app.route("/api/login", methods=["POST"])
def login():
    body = request.json or {}
    username = str(body.get("username", "")).strip().lower()
    password = str(body.get("password", ""))
    if not USERNAME_RE.match(username):
        return jsonify({"error": "İsim 2-20 karakter olmalı; harf, rakam, _ . - kullanabilirsin."}), 400
    if len(password) < MIN_PASSWORD:
        return jsonify({"error": f"Şifre en az {MIN_PASSWORD} karakter olmalı."}), 400

    exists, password_hash = db_get_password_hash(username)
    created = False
    if password_hash is None:
        # Yeni kullanıcı ya da şifresi olmayan eski kullanıcı: ilk girilen şifre kaydedilir
        db_set_password_hash(username, generate_password_hash(password))
        created = True
    elif not check_password_hash(password_hash, password):
        return jsonify({"error": "Şifre yanlış."}), 401

    token = secrets.token_urlsafe(32)
    db_add_token(token, username)
    return jsonify({"token": token, "username": username, "created": created, "existed": exists})

@app.route("/api/logout", methods=["POST"])
@require_auth
def logout():
    db_delete_token(current_token())
    return jsonify({"ok": True})

@app.route("/api/users", methods=["GET"])
@require_auth
def get_users():
    return jsonify(db_get_all())

@app.route("/api/users/<username>/sessions", methods=["POST"])
@require_auth
def set_sessions(username):
    db_upsert(username, "sessions", request.json)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/subjects", methods=["POST"])
@require_auth
def set_subjects(username):
    db_upsert(username, "subjects", request.json)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/settings", methods=["POST"])
@require_auth
def set_settings(username):
    db_upsert(username, "settings", request.json)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/active", methods=["POST"])
@require_auth
def set_active(username):
    data = request.json
    data["alive"] = time.time() * 1000
    db_upsert(username, "active", data)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/active", methods=["DELETE"])
@require_auth
def clear_active(username):
    db_clear_active(username)
    return jsonify({"ok": True})

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/sw.js")
def service_worker():
    # Kök adresten sunulmalı ki tüm siteyi kapsasın
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

if __name__ == "__main__":
    # Render/Railway'in atadığı portu alıyoruz, yereldeysen 8080'i kullanıyoruz.
    port = int(os.environ.get("PORT", 8080))

    print(f"\n🌊 StudyFlow başlatılıyor... Port: {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
