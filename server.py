from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json, os, time

app = Flask(__name__, static_folder="static")
CORS(app)

DATA_FILE = "data.json"

def load():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Kullanıcı verilerini getir
@app.route("/api/users", methods=["GET"])
def get_users():
    return jsonify(load())

# Kullanıcı session'larını kaydet
@app.route("/api/users/<name>/sessions", methods=["POST"])
def set_sessions(name):
    data = load()
    if name not in data:
        data[name] = {}
    data[name]["sessions"] = request.json
    save(data)
    return jsonify({"ok": True})

# Kullanıcı derslerini kaydet
@app.route("/api/users/<name>/subjects", methods=["POST"])
def set_subjects(name):
    data = load()
    if name not in data:
        data[name] = {}
    data[name]["subjects"] = request.json
    save(data)
    return jsonify({"ok": True})

# Aktif oturum (canlı zamanlayıcı)
@app.route("/api/users/<name>/active", methods=["POST"])
def set_active(name):
    data = load()
    if name not in data:
        data[name] = {}
    data[name]["active"] = request.json
    data[name]["active"]["alive"] = time.time() * 1000
    save(data)
    return jsonify({"ok": True})

@app.route("/api/users/<name>/active", methods=["DELETE"])
def clear_active(name):
    data = load()
    if name in data and "active" in data[name]:
        del data[name]["active"]
        save(data)
    return jsonify({"ok": True})

# Ana sayfa
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    print("\n🌊 StudyFlow başlatılıyor...")
    print("👉 Tarayıcında aç: http://localhost:5000")
    print("👥 Arkadaşın aynı ağdaysa: http://<senin-ip-adresin>:5000")
    print("Durdurmak için: CTRL+C\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
