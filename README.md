# EcoCode 🌱

AI-powered Python Code Energy Profiler

---

## 🚀 Problem

Developers write inefficient code unknowingly.
EcoCode detects energy-heavy functions and suggests improvements.

---

## 🛠 Tech Stack

- Backend: FastAPI
- Frontend: React (Vite)
- LLM: OpenAI / Gemini (with fallback)

---

# 🧠 How It Works

1. Paste Python code
2. Click Analyze
3. View hotspots (energy-heavy functions)
4. Click a hotspot
5. Get AI suggestions + improved code

---

# ⚙️ Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Runs at:
```
http://localhost:8000
```

---

# 💻 Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Runs at:
```
http://localhost:5173
```

---

# 🌍 Environment Variable (Frontend)

Create a `.env` file inside `frontend`:

```
VITE_API_URL=http://localhost:8000
```

---

# 🧪 Demo Sample Code

```python
def slow_function(data):
    result = []
    for i in data:
        for j in data:
            result.append(i + j)
    return sorted(result)
```

---

# 👥 Team

- Backend Profiler
- LLM Suggestions
- Frontend UI
- Integration & Deployment
