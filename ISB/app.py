from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
import pandas as pd
import json

import database as db
from parallel_processor import start_processing, get_progress

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Initialize DB
db.init_db()


# ─────────────────────────────────────────────────────────────
# UI ROUTES
# ─────────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/results")
def results_page():
    return render_template("results.html")


@app.route("/search")
def search_page():
    return render_template("search.html")


# ─────────────────────────────────────────────────────────────
# FILE UPLOAD
# ─────────────────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    save_name = str(uuid.uuid4()) + "_" + file.filename
    path = os.path.join(app.config["UPLOAD_FOLDER"], save_name)
    file.save(path)

    return jsonify({
        "file_name": file.filename,
        "save_name": save_name,
        "file_size": os.path.getsize(path)
    })


# ─────────────────────────────────────────────────────────────
# START PROCESSING
# ─────────────────────────────────────────────────────────────
@app.route("/process", methods=["POST"])
def process_file():
    data = request.json

    # Resolve use_multiprocessing from string or bool
    use_mp = data.get("use_multiprocessing", False)
    if isinstance(use_mp, str):
        use_mp = use_mp.lower() == "true"

    batch_id = start_processing(
        file_path=os.path.join(app.config["UPLOAD_FOLDER"], data["save_name"]),
        file_name=data["file_name"],
        file_size=data["file_size"],
        num_workers=data.get("num_workers"),
        use_multiprocessing=use_mp
    )

    return jsonify({"batch_id": batch_id})


# ─────────────────────────────────────────────────────────────
# STATUS POLLING
# ─────────────────────────────────────────────────────────────
@app.route("/status/<batch_id>")
def status(batch_id):
    return jsonify(get_progress(batch_id))


# ─────────────────────────────────────────────────────────────
# STATISTICS API  (new — used by results page)
# ─────────────────────────────────────────────────────────────
@app.route("/api/stats")
def get_stats():
    batch_id = request.args.get("batch_id")
    stats = db.get_statistics(batch_id=batch_id)

    # Also gather pattern frequencies and top words
    try:
        all_data = db.get_all_chunks_for_export(batch_id=batch_id)
        patterns = {}
        pos_words = {}
        neg_words = {}
        total_words = 0

        for row in all_data:
            total_words += row.get("word_count", 0) or 0

            pm = row.get("pattern_matches", "")
            if isinstance(pm, str) and pm:
                for p in pm.split(", "):
                    p = p.strip()
                    if p:
                        patterns[p] = patterns.get(p, 0) + 1
            elif isinstance(pm, list):
                for p in pm:
                    patterns[p] = patterns.get(p, 0) + 1

            pw = row.get("positive_words", "")
            if isinstance(pw, str) and pw:
                for w in pw.split(", "):
                    w = w.strip()
                    if w:
                        pos_words[w] = pos_words.get(w, 0) + 1
            elif isinstance(pw, list):
                for w in pw:
                    pos_words[w] = pos_words.get(w, 0) + 1

            nw = row.get("negative_words", "")
            if isinstance(nw, str) and nw:
                for w in nw.split(", "):
                    w = w.strip()
                    if w:
                        neg_words[w] = neg_words.get(w, 0) + 1
            elif isinstance(nw, list):
                for w in nw:
                    neg_words[w] = neg_words.get(w, 0) + 1

        stats["patterns"] = patterns
        stats["top_positive_words"] = sorted(pos_words.items(), key=lambda x: -x[1])[:10]
        stats["top_negative_words"] = sorted(neg_words.items(), key=lambda x: -x[1])[:10]
        stats["total_words"] = total_words
        stats["total_lines"] = stats.get("total_chunks", 0)

    except Exception as e:
        app.logger.warning("Stats enrichment error: %s", e)

    return jsonify(stats)


# ─────────────────────────────────────────────────────────────
# RESULTS API
# ─────────────────────────────────────────────────────────────
@app.route("/api/results")
def get_results():
    batch_id = request.args.get("batch_id")
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))

    result = db.search_chunks(
        batch_id=batch_id,
        page=page,
        page_size=page_size
    )

    return jsonify(result)


# ─────────────────────────────────────────────────────────────
# SEARCH API
# ─────────────────────────────────────────────────────────────
@app.route("/api/search")
def search():
    keyword = request.args.get("keyword")
    batch_id = request.args.get("batch_id")

    result = db.search_chunks(
        keyword=keyword,
        batch_id=batch_id,
        page=int(request.args.get("page", 1)),
        page_size=int(request.args.get("page_size", 50))
    )

    return jsonify(result)


# ─────────────────────────────────────────────────────────────
# EXPORT CSV / EXCEL
# ─────────────────────────────────────────────────────────────
@app.route("/api/export")
def export_data():
    batch_id = request.args.get("batch_id")
    keyword  = request.args.get("keyword")
    file_type = request.args.get("type", "csv")

    if keyword:
        # Export search results
        result = db.search_chunks(keyword=keyword, batch_id=batch_id, page=1, page_size=999999)
        rows = result.get("results", [])
        # Flatten list fields
        for r in rows:
            for field in ("positive_words", "negative_words", "tags", "pattern_matches"):
                val = r.get(field, [])
                r[field] = ", ".join(val) if isinstance(val, list) else str(val)
        data = rows
    else:
        data = db.get_all_chunks_for_export(batch_id)

    df = pd.DataFrame(data)

    if file_type == "excel":
        path = "export.xlsx"
        df.to_excel(path, index=False)
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        path = "export.csv"
        df.to_csv(path, index=False)
        mimetype = "text/csv"

    return send_file(path, as_attachment=True, mimetype=mimetype)


# ─────────────────────────────────────────────────────────────
# EMAIL SEND
# ─────────────────────────────────────────────────────────────
@app.route("/api/email", methods=["POST"])
def send_email():
    data = request.json
    email = data.get("email")
    batch_id = data.get("batch_id")

    if not email:
        return jsonify({"error": "No email provided"}), 400

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Build a summary for the email body
        stats = db.get_statistics(batch_id=batch_id)
        body = f"""Your Lexon Analytics results are ready.

Batch ID: {batch_id or 'N/A'}
Total Chunks: {stats.get('total_chunks', 0)}
Average Sentiment Score: {round(stats.get('avg_score') or 0, 4)}
Positive: {stats.get('positive_count', 0)}
Negative: {stats.get('negative_count', 0)}
Neutral:  {stats.get('neutral_count', 0)}

View full results at your Lexon Analytics dashboard.
"""

        SMTP_USER = os.environ.get("SMTP_USER", "your_email@gmail.com")
        SMTP_PASS = os.environ.get("SMTP_PASS", "app_password")

        msg = MIMEMultipart()
        msg["Subject"] = "Lexon Analytics — Results Ready"
        msg["From"] = SMTP_USER
        msg["To"] = email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return jsonify({"status": "sent"})

    except Exception as e:
        app.logger.error("Email error: %s", e)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)