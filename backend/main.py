from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
import ast

app = FastAPI(title="EcoCode Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    code: str
    filename: str | None = "main.py"

@app.get("/")
def root():
    return {"status": "ok", "message": "EcoCode backend running"}

def get_max_loop_depth(func_node):
    max_depth = 0

    def visit(node, depth=0):
        nonlocal max_depth

        if isinstance(node, (ast.For, ast.While)):
            depth += 1
            max_depth = max(max_depth, depth)

        for child in ast.iter_child_nodes(node):
            visit(child, depth)

    visit(func_node)
    return max_depth

def is_recursive(func_node):
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == func_node.name:
                return True
    return False

EXPENSIVE_FUNCS = {"sorted", "open", "print"}

def detect_expensive_calls(func_node):
    found = []

    for node in ast.walk(func_node):
        # direct calls like sorted()
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in EXPENSIVE_FUNCS:
                found.append(node.func.id)

            # method calls like list.sort()
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "sort":
                    found.append("sort()")

    return list(set(found))

def detect_loop_issues(func_node):
    issues = []

    for node in ast.walk(func_node):
        # Only interested in loops
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                # Detect string concatenation using +=
                if isinstance(child, ast.AugAssign):
                    if isinstance(child.op, ast.Add):
                        issues.append("string concatenation in loop (+=)")

                # Detect list append calls
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute):
                        if child.func.attr == "append":
                            issues.append("list append in loop (.append)")

    return list(set(issues))  # remove duplicates

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    # --- constants for heuristic estimation ---
    ELECTRICITY_RATE_PER_KWH = 8.0  # INR (change to 0.20 for USD if you want)
    JOULES_PER_SCORE_POINT = 0.05   # heuristic: score 100 => 5 Joules per run

    # --- parse code safely ---
    try:
        tree = ast.parse(req.code)
    except SyntaxError as e:
        return {
            "summary": {
                "filename": req.filename,
                "language": "python",
                "function_count": 0,
                "hotspot_count": 0,
                "note": "Energy and cost are heuristic estimates from static analysis (not hardware power counters)."
            },
            "hotspots": [],
            "error": f"SyntaxError at line {e.lineno}: {e.msg}"
        }
    except Exception as e:
        return {
            "summary": {
                "filename": req.filename,
                "language": "python",
                "function_count": 0,
                "hotspot_count": 0,
                "note": "Energy and cost are heuristic estimates from static analysis (not hardware power counters)."
            },
            "hotspots": [],
            "error": f"Invalid Python code: {str(e)}"
        }

    # --- extract functions ---
    function_nodes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]

    hotspots = []
    code_lines = req.code.splitlines()

    for func in function_nodes:
        loop_depth = get_max_loop_depth(func)
        recursive = is_recursive(func)
        expensive_calls = detect_expensive_calls(func)
        loop_issues = detect_loop_issues(func)

        # Safe line extraction (end_lineno may not exist in older versions)
        start_line = getattr(func, "lineno", 1)
        end_line = getattr(func, "end_lineno", start_line)

        # Extract code snippet for frontend + LLM
        try:
            code_snippet = "\n".join(code_lines[start_line - 1:end_line])
        except Exception:
            code_snippet = ""

        # ---- Compute score (0-100) ----
        score = loop_depth * 12
        if recursive:
            score += 20
        score += len(expensive_calls) * 15
        score += len(loop_issues) * 10
        score = min(score, 100)

        # ---- Build reasons list (human readable) ----
        reasons = []

        if loop_depth > 0:
            reasons.append(f"Loop nesting depth = {loop_depth}")

        if recursive:
            reasons.append("Recursion detected")

        if expensive_calls:
            reasons.append("Expensive calls: " + ", ".join(expensive_calls))

        for issue in loop_issues:
            reasons.append(issue)

        # ---- Category (simple heuristic) ----
        # If file I/O is present, label as I/O.
        # Else if loops/recursion exist, label as CPU.
        # Else label as CPU (default).
        if "open" in expensive_calls:
            category = "I/O"
        elif loop_depth >= 2 or recursive or ("sorted" in expensive_calls) or ("sort()" in expensive_calls):
            category = "CPU"
        else:
            category = "CPU"

        # ---- Energy estimation (heuristic) ----
        estimated_joules_per_run = round(score * JOULES_PER_SCORE_POINT, 4)

        # Convert joules -> kWh -> cost
        # 1 kWh = 3,600,000 Joules
        estimated_cost_per_run = (estimated_joules_per_run / 3_600_000) * ELECTRICITY_RATE_PER_KWH

        # More meaningful display
        estimated_cost_per_1000_runs = round(estimated_cost_per_run * 1000, 6)
        estimated_cost_per_1m_runs = round(estimated_cost_per_run * 1_000_000, 4)

        hotspots.append({
            "name": func.name,
            "score": score,
            "category": category,
            "reasons": reasons,
            "start_line": start_line,
            "end_line": end_line,
            "code_snippet": code_snippet,
            "estimated_joules_per_run": estimated_joules_per_run,
            "estimated_cost_per_1000_runs": estimated_cost_per_1000_runs,
            "estimated_cost_per_1m_runs": estimated_cost_per_1m_runs
        })

    # Sort hotspots by score descending (important for UI)
    hotspots.sort(key=lambda x: x["score"], reverse=True)

    return {
        "summary": {
            "filename": req.filename,
            "language": "python",
            "function_count": len(function_nodes),
            "hotspot_count": len(hotspots),
            "electricity_rate_per_kwh": ELECTRICITY_RATE_PER_KWH,
            "note": "Energy and cost are heuristic estimates from static analysis (not hardware power counters)."
        },
        "hotspots": hotspots
    }
