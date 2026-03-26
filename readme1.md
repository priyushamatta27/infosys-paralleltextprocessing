# 🚀 Lexon - Parallel Text Handling Processor 

A high-performance **Parallel Text Processing & Sentiment Analysis Engine** built using Python with Flask, SQLite, and a modern UI dashboard.

This system can process **large-scale text files (up to lakhs of lines)** efficiently using **parallel processing**, perform **rule-based sentiment analysis**, and provide **interactive analytics dashboards**.

---

## 📌 Features

### ⚡ Core Capabilities

* Upload and process **any text-based file**
* Supports formats:

  * `.txt`, `.csv`, `.json`, `.xml`, `.html`, `.pdf`, `.docx`, `.xlsx`, `.log`, `.md`
* Handles **very large files efficiently** using streaming and chunking
* Automatic **dynamic chunking based on file size**

### 🧠 Sentiment Analysis

* Rule-based sentiment engine (no ML dependency)
* Detects:

  * Positive / Negative / Neutral sentiment
  * Keywords, patterns, tags
  * Negations (e.g., *"not good" → negative*)
  * Intensifiers (e.g., *"very good" → stronger positive*)

### ⚙️ Parallel Processing Engine

* Uses:

  * `ThreadPoolExecutor` (I/O bound)
  * `ProcessPoolExecutor` (CPU bound)
* Auto-selects optimal worker count
* Real-time progress tracking

### 📊 Analytics Dashboard

* Interactive charts (Chart.js)
* Metrics:

  * Sentiment distribution
  * Top positive/negative words
  * Pattern frequency
  * Total words & lines

### 🔍 Search & Export

* Keyword-based search across processed data
* Export results:

  * CSV
  * Excel
* Email export functionality

---

## 🏗️ Project Structure

```
ISB/
│
├── app.py                  # Flask main application
├── database.py             # Database operations (SQLite)
├── file_loader.py          # File parsing & dynamic chunking
├── parallel_processor.py   # Parallel execution engine
├── sentiment_engine.py     # Rule-based sentiment analysis
│
├── templates/
│   ├── index.html          # Upload page
│   ├── results.html        # Results dashboard
│   └── search.html         # Search page
│
├── static/
│   ├── app.js              # Frontend logic
│   └── style.css           # UI styling
│
├── uploads/                # Uploaded files
├── text_processor.db       # SQLite database (auto-created)
│
└── README.md
```

---

## ⚙️ Installation & Setup

### 1️⃣ Clone Repository

```bash
git clone https://github.com/priyushamatta27/infosys-paralleltextprocessing.git
cd lexon-analytics
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate   # Windows
```

### 3️⃣ Install Dependencies

```bash
pip install flask pandas
```

Optional (for full file support):

```bash
pip install python-docx pdfplumber openpyxl chardet
```

---

## ▶️ Running the Application

```bash
python app.py
```

Open browser:

```
http://localhost:5000
```

---

## 🔄 Workflow

1. Upload file via UI
2. File is saved → `/uploads` 
3. File is chunked dynamically 
4. Parallel processing starts 
5. Sentiment analysis applied 
6. Results stored in SQLite 
7. Dashboard displays analytics

---

## 🔌 API Endpoints

### 📂 Upload File

```
POST /upload
```

### ⚙️ Start Processing

```
POST /process
```

### 📊 Check Status

```
GET /status/<batch_id>
```

### 📈 Get Statistics

```
GET /api/stats?batch_id=<id>
```

### 📋 Get Results

```
GET /api/results
```

### 📤 Export Data

```
GET /api/export?type=csv|xlsx
```

---

## 🗄️ Database Design

### Tables:

* `text_chunks` → stores processed text
* `processing_jobs` → tracks job progress

Optimized with:

* Indexing
* WAL mode for concurrency

---

## 🧪 Example Use Cases

* Social media sentiment analysis
* Customer feedback processing
* Log file analysis
* News/article analytics
* Research text mining

---

## 🚀 Performance Highlights

* Handles **50,000+ lines efficiently**
* Parallel processing significantly faster than sequential
* Dynamic chunking prevents memory overload

---

## ⚠️ Notes

* Large files may take time depending on CPU
* Use multiprocessing for CPU-heavy workloads
* Ensure required libraries are installed for file formats

---

## 🔮 Future Enhancements

* ML-based sentiment analysis
* Real-time streaming analytics
* User authentication
* Cloud deployment (AWS/GCP)
* API rate limiting

---

## 👨‍💻 Author

**Priyusha Matta**

---

## 📜 License

This project is open-source and available under the MIT License.

---

## ⭐ Support

If you like this project:

* ⭐ Star the repo
* 🍴 Fork it
* 🚀 Contribute improvements

---
