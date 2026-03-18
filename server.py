from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os, json, time

app = Flask(__name__, static_folder="static")
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    def get_conn():
        return psycopg2.connect(DATABASE_URL)

    def init_db():
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                username TEXT PRIMARY KEY,
                sessions JSONB DEFAULT '{}',
                subjects JSONB DEFAULT '{}',
                active JSONB DEFAULT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        conn.close()

    init_db()

    def db_get_all():
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM user_data")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = {}
        for row in rows:
            result[row["username"]] = {
                "sessions": row["sessions"] or {},
                "subjects": row["subjects"] or {},
                "active": row["active"],
            }
        return result

    def db_upsert(username, field, value):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO user_data (username, {field}, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (username) DO UPDATE SET {field} = %s, updated_at = NOW()
        """, (username, json.dumps(value), json.dumps(value)))
        conn.commit()
        cur.close()
        conn.close()

    def db_clear_active(username):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE user_data SET active = NULL WHERE username = %s", (username,))
        conn.commit()
        cur.close()
        conn.close()

else:
    DATA_FILE = "data.json"

    def load():
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(data):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def db_get_all():
        return load()

    def db_upsert(username, field, value):
        data = load()
        if username not in data:
            data[username] = {}
        data[username][field] = value
        save(data)

    def db_clear_active(username):
        data = load()
        if username in data:
            data[username]["active"] = None
            save(data)


@app.route("/api/users", methods=["GET"])
def get_users():
    return jsonify(db_get_all())

@app.route("/api/users/<username>/sessions", methods=["POST"])
def set_sessions(username):
    db_upsert(username, "sessions", request.json)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/subjects", methods=["POST"])
def set_subjects(username):
    db_upsert(username, "subjects", request.json)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/active", methods=["POST"])
def set_active(username):
    data = request.json
    data["alive"] = time.time() * 1000
    db_upsert(username, "active", data)
    return jsonify({"ok": True})

@app.route("/api/users/<username>/active", methods=["DELETE"])
def clear_active(username):
    db_clear_active(username)
    return jsonify({"ok": True})

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    # Railway'in atadığı portu alıyoruz, eğer yereldeysen 8080'i kullanıyoruz.
    port = int(os.environ.get("PORT", 8080))
    
    print(f"\n🌊 StudyFlow başlatılıyor... Port: {port}")
    # port=8080 yerine port=port değişkenini yazdık
    app.run(host="0.0.0.0", port=port, debug=False)
