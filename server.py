from flask import Flask, redirect
import os

# StudyFlow artık GitHub Pages + Firebase'de. Bu sunucu sadece eski Render adresine
# gelenleri yeni siteye yönlendirir; Render servisi kapatılınca bu dosya da silinebilir.
NEW_URL = "https://bircanbektas.github.io/studyflow/"

app = Flask(__name__, static_folder=None)

@app.route("/health")
def health():
    return "ok", 200

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def moved(path):
    return redirect(NEW_URL, code=301)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
