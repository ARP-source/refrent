"""Local, authenticated demo portals (Canvas LMS, Docs, Lab Wiki, Code host).

They are served by the same FastAPI app so the live stage demo never depends on a
third-party site. Every page carries machine-readable hints the resolver reads from
the live DOM:

    <body data-recall='{"type":"course","name":"CS229"}'>   page-level context
    <span data-entity="Dana Chen" data-entity-type="person" data-pronouns="she">   people

Content lives in registries below; seed_vault.py builds episodes from the same data,
so every selector / text fragment stored in the vault exists on the real page.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/portals")
COOKIE = "recall_session"
SESSION_VALUE = "demo-student"


def when(days_ago: float, hour: int = 12, minute: int = 0) -> datetime:
    return (datetime.now() - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def esc(s: str) -> str:
    return html.escape(s, quote=False)


# --------------------------------------------------------------------------- data
PEOPLE = {
    "Dana Chen": ("she", "Professor, CS229"),
    "Marcus Lee": ("he", "TA, CS229"),
    "Elena Vasquez": ("she", "Professor, MATH 340"),
    "Tom Brandt": ("he", "TA, MATH 340"),
    "Priya Raman": ("she", "Labmate, Estimation Lab"),
    "Sam Okafor": ("he", "Guest lecturer"),
    "Irina Rostova": ("she", "Professor, STAT 310"),
    "Wei Zhang": ("he", "TA, STAT 310"),
    "You": ("they", "Student"),
}

COURSES = {
    "cs229": {"code": "CS229", "title": "Machine Learning and State Estimation", "prof": "Dana Chen", "ta": "Marcus Lee", "color": "#b5162b"},
    "math340": {"code": "MATH 340", "title": "Numerical Linear Algebra", "prof": "Elena Vasquez", "ta": "Tom Brandt", "color": "#1f5fa8"},
    "stat310": {"code": "STAT 310", "title": "Stochastic Processes and Filtering", "prof": "Irina Rostova", "ta": "Wei Zhang", "color": "#0f7b5f"},
}

# Course files: lookalike study guides / drafts that share 90%+ of their vocabulary.
FILES = {
    "stat310": [
        "kf-guide-v1", "ito-primer", "kf-proposal-a", "sc-guide", "kf-guide-quiz3",
        "kf-guide-midterm", "kf-proposal-b", "kf-guide-quiz4", "sheet-kf", "sheet-ito",
    ],
}

# Calendar events (become `event` notes in the vault and act as temporal anchors).
EVENTS = [
    {"key": "oh14", "title": "Rostova office hours", "days_ago": 14, "hour": 16, "minute": 0, "course": "STAT 310", "people": ["Irina Rostova"], "where": "Sequoia 200"},
    {"key": "quiz3", "title": "STAT 310 Quiz 3", "days_ago": 13, "hour": 10, "minute": 0, "course": "STAT 310", "people": ["Irina Rostova"], "where": "Hewlett 201"},
    {"key": "oh7", "title": "Rostova office hours", "days_ago": 7, "hour": 16, "minute": 0, "course": "STAT 310", "people": ["Irina Rostova"], "where": "Sequoia 200"},
    {"key": "quiz4", "title": "STAT 310 Quiz 4", "days_ago": 0, "hour": 10, "minute": 0, "course": "STAT 310", "people": ["Irina Rostova"], "where": "Hewlett 201"},
]

ANNOUNCEMENTS = {
    "cs229": [
        {
            "id": "ann-1", "days_ago": 27, "hour": 9, "author": "Dana Chen",
            "title": "Welcome to CS229 - syllabus and grading",
            "paras": [
                "Welcome everyone! The syllabus is posted under Files. Problem sets are worth 40 percent, the midterm 30 percent and the final project 30 percent.",
                "Please join the course forum and introduce yourself to your project group by Friday.",
            ],
            "key": "the midterm 30 percent and the final project 30 percent",
        },
        {
            "id": "ann-2", "days_ago": 19, "hour": 16, "author": "Dana Chen",
            "title": "Guest lecture: diffusion models for trajectory forecasting",
            "paras": [
                "On Thursday Dr. Sam Okafor will give a guest lecture on diffusion models for trajectory forecasting. Attendance is strongly encouraged.",
                "Slides will be posted after class; there is no problem set that week.",
            ],
            "key": "diffusion models for trajectory forecasting",
        },
        {
            "id": "ann-3", "days_ago": 14, "hour": 14, "author": "Dana Chen",
            "title": "Final project proposal requirements",
            "paras": [
                "The final project proposal is due in three weeks. It should be at most 4 pages and follow the NeurIPS template.",
                "Your final project proposal must include a state-estimation baseline (a Kalman or Extended Kalman Filter) with a quantified drift analysis over at least 10,000 steps.",
                "Proposals without a clear baseline and evaluation plan will be returned for revision. Office hours this week are dedicated to proposal feedback.",
            ],
            "key": "must include a state-estimation baseline (a Kalman or Extended Kalman Filter) with a quantified drift analysis over at least 10,000 steps",
        },
        {
            "id": "ann-4", "days_ago": 9, "hour": 11, "author": "Marcus Lee",
            "title": "Office hours moved to Thursday 4pm",
            "paras": [
                "My office hours are moving to Thursday 4pm in Gates 104 for the rest of the quarter.",
                "Bring your proposal drafts if you want feedback on the baseline section.",
            ],
            "key": "Thursday 4pm in Gates 104",
        },
        {
            "id": "ann-5", "days_ago": 3, "hour": 9, "author": "Dana Chen",
            "title": "Midterm grades released and regrade policy",
            "paras": [
                "Midterm grades are now released. The median was 78.",
                "Regrade requests must be submitted within one week through Gradescope with a written justification.",
            ],
            "key": "Regrade requests must be submitted within one week",
        },
    ],
    "math340": [
        {
            "id": "ann-1", "days_ago": 21, "hour": 15, "author": "Elena Vasquez",
            "title": "Exam format",
            "paras": [
                "The exam is closed book with one double-sided page of notes. Expect three proofs and two computational problems.",
            ],
            "key": "one double-sided page of notes",
        },
        {
            "id": "ann-2", "days_ago": 14, "hour": 10, "author": "Elena Vasquez",
            "title": "Problem set 6 posted",
            "paras": [
                "Problem set 6 is posted. It covers eigenvalue perturbation theory and the Bauer-Fike theorem.",
                "Question 4 asks you to bound the eigenvalue error of a perturbed covariance matrix.",
            ],
            "key": "eigenvalue perturbation theory and the Bauer-Fike theorem",
        },
        {
            "id": "ann-3", "days_ago": 6, "hour": 13, "author": "Tom Brandt",
            "title": "Recitation rescheduled",
            "paras": [
                "Friday recitation is rescheduled to Monday at 5pm because of the department colloquium.",
            ],
            "key": "rescheduled to Monday at 5pm",
        },
    ],
    "stat310": [
        {
            "id": "ann-1", "days_ago": 16, "hour": 9, "author": "Irina Rostova",
            "title": "Quiz 3 on Kalman filtering - office hours Friday",
            "paras": [
                "Quiz 3 covers the discrete Kalman filter: prediction, update and the Riccati recursion. I will hold extra office hours on Friday at 4pm.",
            ],
            "key": "extra office hours on Friday at 4pm",
        },
        {
            "id": "ann-2", "days_ago": 4, "hour": 9, "author": "Irina Rostova",
            "title": "Quiz 4 covers Ito's lemma and the Kalman update",
            "paras": [
                "Quiz 4 covers Ito's lemma, the Ito isometry and the Kalman update equations. One formula sheet is allowed.",
            ],
            "key": "One formula sheet is allowed",
        },
    ],
}

ASSIGNMENTS = {
    "cs229": [
        {
            "id": "asg-proposal", "title": "Final Project Proposal", "due_in": 7, "points": 100,
            "desc": "Submit a 4 page proposal describing your problem, baseline, method and evaluation plan.",
            "rubric": [
                "Problem statement and motivation: 20 points",
                "State-estimation baseline (Kalman or EKF) with drift analysis: 40 points",
                "Proposed method and evaluation plan: 30 points",
                "Clarity and formatting: 10 points",
            ],
        },
        {"id": "asg-ps3", "title": "Problem Set 3", "due_in": -5, "points": 50, "desc": "Linear dynamical systems and smoothing.", "rubric": []},
    ],
    "math340": [
        {"id": "asg-ps6", "title": "Problem Set 6", "due_in": 2, "points": 50, "desc": "Eigenvalue perturbation.", "rubric": []},
    ],
}

GRADES = {
    "cs229": [("grade-ps1", "Problem Set 1", 92), ("grade-ps2", "Problem Set 2", 88), ("grade-ps3", "Problem Set 3", 95), ("grade-midterm", "Midterm", 84)],
    "math340": [("grade-ps5", "Problem Set 5", 90)],
}

DOCS = {
    "proposal": {
        "title": "EKF Drift Mitigation - Final Project Proposal",
        "context": "Final Project Proposal",
        "collaborators": ["You", "Priya Raman"],
        "sections": [
            ("sec-abstract", "Abstract", "We study long-horizon drift in Extended Kalman Filter state estimates for a low-cost IMU and propose a learned process-noise model that adapts Q online."),
            ("sec-related", "Related work", "Prior work on adaptive Kalman filtering estimates Q from innovation statistics; learned approaches regress noise parameters from sensor windows."),
            ("sec-baseline", "Baseline", "Our baseline is a standard EKF with constant process noise. We compare it to a UKF and report drift over 10,000 steps using RMSE of position and the NEES consistency test."),
            ("sec-method", "Method", "A small recurrent network predicts a diagonal Q from the last 50 IMU samples; the covariance update uses the Joseph form to keep P symmetric positive definite."),
            ("sec-timeline", "Timeline", "Week 1: reproduce baseline drift. Week 2: train the noise model. Week 3: ablations on window length and float precision."),
            ("sec-risks", "Risks", "Numerical instability in the covariance update and overfitting the noise model to a single trajectory."),
        ],
        "comments": [
            ("cmt-1", "Dana Chen", 10, "sec-baseline", "Please quantify the drift over 10k steps and include NEES, not only RMSE."),
            ("cmt-2", "Priya Raman", 8, "sec-method", "Joseph form fixed our negative covariance issue on the lab robot too."),
        ],
    },
    "lab-meeting": {
        "title": "Estimation Lab - Weekly Meeting Notes",
        "context": "Estimation Lab",
        "collaborators": ["Priya Raman", "Dana Chen", "You"],
        "sections": [
            ("lm-1", "Updates", "Priya finished the float64 port of the tracker. The covariance stays positive definite across all test logs."),
            ("lm-2", "Discussion", "Dana suggested ablating process noise magnitude before training anything learned, and reporting NEES alongside RMSE."),
            ("lm-3", "Action items", "You: run the Q ablation. Priya: write up the Joseph form fix on the lab wiki."),
        ],
        "comments": [],
    },
}

def _guide(title: str, owner_people: list[str], overview: str, model: str, update: str, practice: str) -> dict:
    return {
        "title": title,
        "context": "STAT 310",
        "collaborators": owner_people,
        "sections": [
            ("sec-overview", "Overview", overview),
            ("sec-model", "State-space model", model),
            ("sec-update", "Worked example: tuning Q and R", update),
            ("sec-practice", "Practice", practice),
        ],
        "comments": [],
    }


_MODEL = "State x_k = A x_(k-1) + w_k with process noise covariance Q; measurement z_k = H x_k + v_k with measurement noise covariance R. The Kalman gain is K = P H^T (H P H^T + R)^-1."
DOCS.update({
    "kf-guide-v1": _guide(
        "Kalman Filter Study Guide (v1)", ["You"],
        "Study guide for the Kalman filter in STAT 310: linear Gaussian state-space model, prediction step, update step and the Riccati recursion for the error covariance.",
        _MODEL,
        "Use Q = 0.1 I and R = 1.0 for the random-walk model; the steady-state Kalman gain converges after about 25 steps.",
        "Derive the prediction and update equations and show that the error covariance stays positive definite.",
    ),
    "kf-guide-quiz3": _guide(
        "Kalman Filter Study Guide - Quiz 3 prep", ["You", "Irina Rostova"],
        "Study guide for Quiz 3 in STAT 310: Kalman filter prediction and update steps for a linear Gaussian state-space model and the Riccati recursion for the error covariance.",
        _MODEL,
        "Use Q = 0.05 I and R = 0.2 for the constant-velocity model; the steady-state Kalman gain converges after about 40 steps.",
        "Compute two prediction and update cycles by hand and check the innovation covariance at each step.",
    ),
    "sc-guide": _guide(
        "Stochastic Calculus Study Guide", ["You"],
        "Study guide for stochastic calculus in STAT 310: Brownian motion, the Ito integral, Ito's lemma and the link between stochastic differential equations and the Kalman-Bucy filter.",
        "dX = a X dt + b dW with Brownian motion W. The Kalman-Bucy filter is the continuous-time Kalman filter with process noise covariance Q and measurement noise covariance R.",
        "Ito's lemma: df = (f_t + a x f_x + 0.5 b^2 x^2 f_xx) dt + b x f_x dW. Use Q = 0.05 and R = 0.2 in the Kalman-Bucy example.",
        "Apply Ito's lemma to log X and compare with the discrete Kalman filter covariance recursion.",
    ),
    "kf-guide-midterm": _guide(
        "Kalman Filter Study Guide v3 - Midterm review", ["You"],
        "Midterm review study guide for STAT 310: Kalman filter prediction and update steps, linear Gaussian state-space model and the Riccati recursion for the error covariance.",
        _MODEL,
        "Use Q = 0.02 I and R = 0.3 for the constant-velocity model; the steady-state Kalman gain converges after about 60 steps.",
        "Show that the Kalman filter is the minimum mean square error estimator for the linear Gaussian state-space model.",
    ),
    "kf-guide-quiz4": _guide(
        "Kalman Filter Study Guide - Prof. Rostova quiz and office hours FAQ", ["You"],
        "Study guide for Prof. Rostova's quiz in STAT 310 with notes from office hours: Kalman filter prediction and update steps, the Riccati recursion and the error covariance.",
        _MODEL,
        "Office hours FAQ: Prof. Rostova said the quiz uses Q = 0.05 I and R = 0.2 for the constant-velocity Kalman filter model.",
        "Office hours tip from Prof. Rostova: check the innovation covariance before the quiz.",
    ),
    "kf-proposal-a": _guide(
        "Kalman Filter Project Proposal - Draft A", ["You", "Priya Raman"],
        "Proposal draft: an adaptive Kalman filter for a constant-velocity tracking model that tunes the process noise covariance Q and measurement noise covariance R online.",
        _MODEL,
        "Initial values Q = 0.01 I and R = 0.5 for the constant-velocity model; the steady-state Kalman gain converges after about 120 steps.",
        "Evaluate error covariance consistency with NEES over 10,000 steps.",
    ),
    "kf-proposal-b": _guide(
        "Kalman Filter Project Proposal - Draft B", ["You", "Priya Raman"],
        "Proposal draft B: an adaptive Kalman filter for a constant-velocity tracking model with online tuning of the process noise covariance Q and measurement noise covariance R.",
        _MODEL,
        "Initial values Q = 0.03 I and R = 0.4 for the constant-velocity model; the steady-state Kalman gain converges after about 80 steps.",
        "Evaluate error covariance consistency with NEES and compare to the Riccati recursion steady state.",
    ),
    "ito-primer": _guide(
        "Ito Calculus Primer", ["You"],
        "Primer on Ito calculus for STAT 310: Brownian motion, quadratic variation, the Ito integral and Ito's lemma for stochastic differential equations.",
        "dX = mu dt + sigma dW. Quadratic variation of Brownian motion over [0, t] equals t.",
        "Ito isometry: E[(int f dW)^2] = E[int f^2 dt]. Worked example with sigma = 0.3.",
        "Prove Ito's lemma for f(t, X_t) using a second order Taylor expansion.",
    ),
    "sheet-kf": {
        "title": "Quiz 4 formula sheet - Kalman update", "context": "STAT 310", "collaborators": ["You"],
        "sections": [("sec-formulas", "Formulas", "Quiz 4 formula sheet: Kalman gain K = P H^T (H P H^T + R)^-1, state update x = x + K (z - H x), covariance update P = (I - K H) P, and Ito's lemma for f(t, X_t).")],
        "comments": [],
    },
    "sheet-ito": {
        "title": "Quiz 4 formula sheet - Ito's lemma", "context": "STAT 310", "collaborators": ["You"],
        "sections": [("sec-formulas", "Formulas", "Quiz 4 formula sheet: Ito's lemma for f(t, X_t), Ito isometry, quadratic variation of Brownian motion, and the Kalman gain K = P H^T (H P H^T + R)^-1 with state update x = x + K (z - H x).")],
        "comments": [],
    },
})

# Edits made AFTER the user last looked: the vault snapshot keeps `previous`, the live page shows the new text.
REVISIONS = {
    ("kf-guide-quiz3", "sec-update"): {
        "previous": "Use Q = 0.01 I and R = 0.5 for the constant-velocity model; the steady-state Kalman gain converges after about 120 steps.",
        "by": "Irina Rostova",
        "days_ago": 6,
    },
}


def section_text(doc_id: str, sid: str, viewed_days_ago: float | None = None) -> str | None:
    """Text of a doc section as it was when viewed `viewed_days_ago` (None -> today)."""
    d = DOCS.get(doc_id)
    if not d:
        return None
    for s_id, _h, text in d["sections"]:
        if s_id == sid:
            rev = REVISIONS.get((doc_id, sid))
            if rev and viewed_days_ago is not None and viewed_days_ago > rev["days_ago"]:
                return rev["previous"]
            return text
    for cid, _a, _d, _on, text in d["comments"]:
        if cid == sid:
            return text
    return None


WIKI = {
    "ekf-debugging": {
        "title": "EKF debugging log",
        "entries": [
            ("log-1", 11, "You", "After switching the state vector to float32 the innovation covariance S went negative after about 3,000 steps and the filter diverged."),
            ("log-2", 7, "Priya Raman", "Suggestion: use the Joseph form covariance update and keep P in float64; symmetrize P after every update."),
            ("log-3", 5, "You", "Fixed: Joseph form plus float64 covariance. The filter is stable for 50,000 steps and NEES is back inside the 95 percent bounds."),
        ],
    },
    "gpu-cluster": {
        "title": "GPU cluster booking",
        "entries": [
            ("gpu-1", 16, "Priya Raman", "Book the A100 nodes through the lab calendar at least 24 hours in advance; jobs longer than 12 hours need approval."),
        ],
    },
    "onboarding": {
        "title": "Lab onboarding",
        "entries": [
            ("onb-1", 23, "Priya Raman", "New members should request cluster access, join the lab channel and read the coding conventions page."),
        ],
    },
}

REPO = {
    "name": "ekf-tracker",
    "commits": [
        ("7be12d4", "Use Joseph form covariance update and float64 P", "Priya Raman", 6),
        ("c41e0b8", "Add NEES consistency test", "You", 10),
        ("a3f9c21", "Switch state vector to float32 for speed", "You", 12),
        ("19d2f70", "Initial EKF with constant process noise", "You", 20),
    ],
    "diffs": {
        "a3f9c21": [
            "-    x = np.zeros(STATE_DIM, dtype=np.float64)",
            "-    P = np.eye(STATE_DIM, dtype=np.float64) * 1e-3",
            "+    x = np.zeros(STATE_DIM, dtype=np.float32)",
            "+    P = np.eye(STATE_DIM, dtype=np.float32) * 1e-3",
            "     Q = process_noise(dt)",
        ],
        "7be12d4": [
            "-    P = (I - K @ H) @ P",
            "+    IKH = I - K @ H",
            "+    P = IKH @ P @ IKH.T + K @ R @ K.T  # Joseph form",
            "+    P = 0.5 * (P + P.T)",
        ],
        "c41e0b8": ["+def nees(err, P):", "+    return float(err @ np.linalg.solve(P, err))"],
        "19d2f70": ["+class EKF:", "+    def predict(self, u, dt): ..."],
    },
    "ci": [
        ("ci-pass", "c41e0b8", "passing", 10, "All 24 tests passed"),
        ("ci-fail", "a3f9c21", "failing", 11, "test_covariance_psd failed: innovation covariance S is not positive definite at step 3127"),
        ("ci-fixed", "7be12d4", "passing", 6, "All 25 tests passed"),
    ],
}


# --------------------------------------------------------------------------- html
CSS = """
*{box-sizing:border-box}body{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1f2933;background:#f5f6f8}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.top{height:56px;display:flex;align-items:center;gap:16px;padding:0 24px;background:var(--brand);color:#fff;position:sticky;top:0;z-index:5}
.top .logo{font-weight:700;letter-spacing:.3px}.top .crumb{opacity:.85}.top .who{margin-left:auto;font-size:13px;opacity:.9}
.wrap{display:flex;min-height:calc(100vh - 56px)}
.side{width:220px;flex:none;background:#fff;border-right:1px solid #e3e6ea;padding:18px 0}
.side a{display:block;padding:9px 22px;color:#374151;border-left:3px solid transparent}
.side a.on{border-left-color:var(--accent);color:var(--accent);font-weight:600;background:#f8fafc}
main{flex:1;padding:26px 36px;max-width:980px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:0 0 6px}.sub{color:#6b7280;margin-bottom:22px}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:8px;padding:18px 20px;margin-bottom:16px}
.meta{color:#6b7280;font-size:13px;margin-bottom:8px}.person{font-weight:600;color:#111827}
.pill{display:inline-block;font-size:12px;padding:2px 8px;border-radius:99px;background:#eef2f7;color:#374151}
.pill.fail{background:#fde8e8;color:#9b1c1c}.pill.pass{background:#e3f6ea;color:#14532d}
table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #eef0f3;text-align:left}
.doc{background:#fff;max-width:780px;margin:0 auto;padding:56px 72px;box-shadow:0 1px 4px rgba(0,0,0,.12);min-height:1100px}
.doc h2{margin-top:28px}.cmt{border-left:3px solid #fbbc04;background:#fffbea;padding:10px 12px;margin:10px 0;font-size:14px}
pre{background:#0d1117;color:#e6edf3;padding:14px;border-radius:6px;font:13px/1.6 ui-monospace,Consolas,monospace;overflow:auto}
.add{color:#7ee787}.del{color:#ff7b72}.btn{display:inline-block;background:var(--accent);color:#fff;padding:8px 14px;border-radius:6px;border:0;font-weight:600;cursor:pointer}
"""


def person(name: str) -> str:
    pron, role = PEOPLE.get(name, ("", ""))
    return (
        f'<span class="person" data-entity="{esc(name)}" data-entity-type="person" '
        f'data-pronouns="{pron}" data-role="{esc(role)}">{esc(name)}</span>'
    )


def fmt_date(d: datetime) -> str:
    return d.strftime("%b %d, %Y at %I:%M %p").replace(" 0", " ")


def shell(*, title: str, brand: str, accent: str, logo: str, crumb: str, ctx: dict, side: str, body: str) -> HTMLResponse:
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>:root{{--brand:{brand};--accent:{accent}}}{CSS}</style></head>
<body data-recall='{html.escape(json.dumps(ctx), quote=True)}'>
<div class="top"><span class="logo">{esc(logo)}</span><span class="crumb">{crumb}</span><span class="who">Signed in - demo student</span></div>
<div class="wrap">{side}<main>{body}</main></div></body></html>"""
    return HTMLResponse(page)


def guard(request: Request) -> RedirectResponse | None:
    if request.cookies.get(COOKIE) != SESSION_VALUE:
        return RedirectResponse(f"/portals/login?next={request.url.path}", status_code=303)
    return None


# --------------------------------------------------------------------------- auth
@router.get("/login", response_class=HTMLResponse)
async def login_page(next: str = "/portals/canvas/"):
    safe_next = next if next.startswith("/portals/") else "/portals/canvas/"
    return HTMLResponse(
        f"""<!doctype html><html><head><title>University SSO</title><style>{CSS}:root{{--accent:#b5162b}}</style></head>
<body><div class="card" style="max-width:380px;margin:120px auto;text-align:center">
<h2>University Single Sign-On</h2><p class="sub">Local demo identity provider</p>
<form method="post" action="/portals/login"><input type="hidden" name="next" value="{esc(safe_next)}">
<button class="btn" id="sso-continue">Continue as demo student</button></form></div></body></html>"""
    )


@router.post("/login")
async def login_submit(next: str = Form("/portals/canvas/")):
    safe_next = next if next.startswith("/portals/") else "/portals/canvas/"
    resp = RedirectResponse(safe_next, status_code=303)
    resp.set_cookie(COOKIE, SESSION_VALUE, httponly=True, samesite="lax")
    return resp


@router.get("/", response_class=HTMLResponse)
async def portal_index(request: Request):
    return RedirectResponse("/portals/canvas/", status_code=303)


# --------------------------------------------------------------------------- canvas
def canvas_side(cid: str, active: str) -> str:
    items = [("home", "Home", ""), ("announcements", "Announcements", "/announcements"),
             ("assignments", "Assignments", "/assignments"), ("grades", "Grades", "/grades")]
    if cid in FILES:
        items.append(("files", "Files", "/files"))
    links = "".join(
        f'<a id="tab-{k}" class="{"on" if k == active else ""}" href="/portals/canvas/courses/{cid}{suf}">{lbl}</a>'
        for k, lbl, suf in items
    )
    return f'<nav class="side">{links}</nav>'


def canvas_page(cid: str, active: str, title: str, body: str) -> HTMLResponse:
    c = COURSES[cid]
    crumb = f'<span data-entity="{esc(c["code"])}" data-entity-type="course">{esc(c["code"])}</span> &rsaquo; {esc(title)}'
    return shell(
        title=f'{title} - {c["code"]}', brand="#2d3b45", accent=c["color"], logo="Canvas",
        crumb=crumb, ctx={"type": "course", "name": c["code"], "portal": "canvas"},
        side=canvas_side(cid, active), body=body,
    )


@router.get("/canvas/", response_class=HTMLResponse)
async def canvas_dashboard(request: Request):
    if r := guard(request):
        return r
    cards = "".join(
        f'<a class="card" id="course-{cid}" style="display:block;border-top:6px solid {c["color"]}" href="/portals/canvas/courses/{cid}">'
        f'<h2>{esc(c["code"])}</h2><div class="sub" style="margin:0">{esc(c["title"])}</div>'
        f'<div class="meta">Instructor: {person(c["prof"])}</div></a>'
        for cid, c in COURSES.items()
    )
    return shell(
        title="Dashboard", brand="#2d3b45", accent="#2d3b45", logo="Canvas", crumb="Dashboard",
        ctx={"type": "dashboard", "name": "Canvas Dashboard", "portal": "canvas"},
        side='<nav class="side"><a class="on" href="/portals/canvas/">Dashboard</a><a href="/portals/docs/proposal">Docs</a><a href="/portals/wiki/">Lab Wiki</a><a href="/portals/code/ekf-tracker">Code</a></nav>',
        body=f'<h1>Dashboard</h1><div class="sub">Fall quarter</div>{cards}',
    )


@router.get("/canvas/courses/{cid}", response_class=HTMLResponse)
async def canvas_home(cid: str, request: Request):
    if r := guard(request):
        return r
    if cid not in COURSES:
        return HTMLResponse("Not found", status_code=404)
    c = COURSES[cid]
    latest = ANNOUNCEMENTS[cid][-1]
    body = (
        f'<h1>{esc(c["code"])}: {esc(c["title"])}</h1>'
        f'<div class="sub">Instructor {person(c["prof"])} - TA {person(c["ta"])}</div>'
        f'<div class="card" id="home-latest"><h2>Latest announcement</h2><div class="meta">{person(latest["author"])} - {fmt_date(when(latest["days_ago"], latest["hour"]))}</div>'
        f'<a href="/portals/canvas/courses/{cid}/announcements">{esc(latest["title"])}</a></div>'
        f'<div class="card"><h2>Course modules</h2><p>Week 1-3: linear dynamical systems. Week 4-6: Kalman filtering and smoothing. Week 7-9: learning for estimation.</p></div>'
    )
    return canvas_page(cid, "home", "Home", body)


@router.get("/canvas/courses/{cid}/announcements", response_class=HTMLResponse)
async def canvas_announcements(cid: str, request: Request):
    if r := guard(request):
        return r
    if cid not in COURSES:
        return HTMLResponse("Not found", status_code=404)
    cards = []
    for a in sorted(ANNOUNCEMENTS[cid], key=lambda a: a["days_ago"]):
        paras = "".join(f"<p>{esc(p)}</p>" for p in a["paras"])
        cards.append(
            f'<article class="card" id="{a["id"]}"><h2>{esc(a["title"])}</h2>'
            f'<div class="meta">{person(a["author"])} - {fmt_date(when(a["days_ago"], a["hour"]))}</div><div data-snapshot>{paras}</div></article>'
        )
    return canvas_page(cid, "announcements", "Announcements", "<h1>Announcements</h1><div class='sub'>Newest first</div>" + "".join(cards))


@router.get("/canvas/courses/{cid}/assignments", response_class=HTMLResponse)
async def canvas_assignments(cid: str, request: Request):
    if r := guard(request):
        return r
    if cid not in COURSES:
        return HTMLResponse("Not found", status_code=404)
    cards = []
    for a in ASSIGNMENTS.get(cid, []):
        due = datetime.now() + timedelta(days=a["due_in"])
        rubric = "".join(f"<li>{esc(x)}</li>" for x in a["rubric"])
        cards.append(
            f'<div class="card" id="{a["id"]}"><h2>{esc(a["title"])}</h2>'
            f'<div class="meta">Due {due:%b %d} - {a["points"]} points</div><p>{esc(a["desc"])}</p>'
            + (f"<h3>Rubric</h3><ul>{rubric}</ul>" if rubric else "")
            + "</div>"
        )
    return canvas_page(cid, "assignments", "Assignments", "<h1>Assignments</h1><div class='sub'>Upcoming and past</div>" + "".join(cards))


@router.get("/canvas/courses/{cid}/grades", response_class=HTMLResponse)
async def canvas_grades(cid: str, request: Request):
    if r := guard(request):
        return r
    if cid not in COURSES:
        return HTMLResponse("Not found", status_code=404)
    rows = "".join(f'<tr id="{gid}"><td>{esc(n)}</td><td>{s}/100</td></tr>' for gid, n, s in GRADES.get(cid, []))
    return canvas_page(cid, "grades", "Grades", f"<h1>Grades</h1><div class='card'><table><tr><th>Item</th><th>Score</th></tr>{rows}</table></div>")


@router.get("/canvas/courses/{cid}/files", response_class=HTMLResponse)
async def canvas_files(cid: str, request: Request):
    if r := guard(request):
        return r
    if cid not in FILES:
        return HTMLResponse("Not found", status_code=404)
    rows = "".join(
        f'<tr id="file-row-{d}"><td><a id="file-{d}" href="/portals/docs/{d}">{esc(DOCS[d]["title"])}</a></td>'
        f'<td>{", ".join(person(p) for p in DOCS[d]["collaborators"])}</td></tr>'
        for d in FILES[cid]
    )
    return canvas_page(cid, "files", "Files", f"<h1>Files</h1><div class='sub'>Study guides, drafts and formula sheets</div><div class='card'><table><tr><th>Name</th><th>Shared with</th></tr>{rows}</table></div>")


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    if r := guard(request):
        return r
    rows = "".join(
        f'<tr id="evt-{e["key"]}"><td>{fmt_date(when(e["days_ago"], e["hour"], e["minute"]))}</td><td><b>{esc(e["title"])}</b></td>'
        f'<td>{", ".join(person(p) for p in e["people"])}</td><td>{esc(e["where"])}</td></tr>'
        for e in sorted(EVENTS, key=lambda e: -e["days_ago"])
    )
    return shell(title="Calendar", brand="#2d3b45", accent="#0f7b5f", logo="Calendar", crumb="Upcoming and past events",
                 ctx={"type": "calendar", "name": "Calendar", "portal": "calendar"},
                 side='<nav class="side"><a href="/portals/canvas/">Dashboard</a><a class="on" href="/portals/calendar">Calendar</a></nav>',
                 body=f"<h1>Calendar</h1><div class='card'><table><tr><th>When</th><th>Event</th><th>With</th><th>Where</th></tr>{rows}</table></div>")


# --------------------------------------------------------------------------- docs
@router.get("/docs/{doc_id}", response_class=HTMLResponse)
async def doc_page(doc_id: str, request: Request):
    if r := guard(request):
        return r
    d = DOCS.get(doc_id)
    if not d:
        return HTMLResponse("Not found", status_code=404)
    parts = []
    for sid, heading, text in d["sections"]:
        cmts = "".join(
            f'<div class="cmt" id="{cid}"><b>{person(author)}</b> - {fmt_date(when(days, 19))}<br><span data-snapshot>{esc(t)}</span></div>'
            for cid, author, days, on, t in d["comments"] if on == sid
        )
        rev = REVISIONS.get((doc_id, sid))
        edit_attr = edit_meta = ""
        if rev:
            at = when(rev["days_ago"], 11, 20)
            edit_attr = f' data-last-edited-by="{esc(rev["by"])}" data-last-edited-at="{at.isoformat()}"'
            edit_meta = f'<div class="meta">Last edited by {person(rev["by"])} - {fmt_date(at)}</div>'
        parts.append(f'<section id="{sid}"{edit_attr}><h2>{esc(heading)}</h2>{edit_meta}<p data-snapshot>{esc(text)}</p>{cmts}</section>')
    collab = ", ".join(person(p) for p in d["collaborators"])
    body = (
        f'<div class="doc"><h1 data-entity="{esc(d["title"])}" data-entity-type="document">{esc(d["title"])}</h1>'
        f'<div class="sub">Shared with {collab}</div>{"".join(parts)}</div>'
    )
    side = "".join(f'<a class="{"on" if k == doc_id else ""}" href="/portals/docs/{k}">{esc(v["title"][:28])}</a>' for k, v in DOCS.items())
    return shell(
        title=d["title"], brand="#1a73e8", accent="#1a73e8", logo="Docs", crumb=esc(d["title"]),
        ctx={"type": "document", "name": d["context"], "portal": "docs"},
        side=f'<nav class="side">{side}</nav>', body=body,
    )


# --------------------------------------------------------------------------- wiki
def wiki_side(active: str) -> str:
    return '<nav class="side">' + "".join(
        f'<a class="{"on" if k == active else ""}" href="/portals/wiki/{k}">{esc(v["title"])}</a>' for k, v in WIKI.items()
    ) + "</nav>"


@router.get("/wiki/", response_class=HTMLResponse)
async def wiki_index(request: Request):
    if r := guard(request):
        return r
    items = "".join(f'<div class="card"><a id="wiki-{k}" href="/portals/wiki/{k}"><h2>{esc(v["title"])}</h2></a></div>' for k, v in WIKI.items())
    return shell(title="Lab Wiki", brand="#3f3d56", accent="#5b54c9", logo="Estimation Lab Wiki", crumb="Index",
                 ctx={"type": "wiki", "name": "Lab Wiki", "portal": "wiki"}, side=wiki_side(""), body=f"<h1>Lab Wiki</h1>{items}")


@router.get("/wiki/{page}", response_class=HTMLResponse)
async def wiki_page(page: str, request: Request):
    if r := guard(request):
        return r
    w = WIKI.get(page)
    if not w:
        return HTMLResponse("Not found", status_code=404)
    entries = "".join(
        f'<div class="card" id="{eid}"><div class="meta">{person(author)} - {fmt_date(when(days, 17))}</div><p data-snapshot>{esc(text)}</p></div>'
        for eid, days, author, text in w["entries"]
    )
    return shell(title=w["title"], brand="#3f3d56", accent="#5b54c9", logo="Estimation Lab Wiki", crumb=esc(w["title"]),
                 ctx={"type": "wiki", "name": "Lab Wiki", "portal": "wiki"}, side=wiki_side(page),
                 body=f"<h1>{esc(w['title'])}</h1><div class='sub'>Chronological log</div>{entries}")


# --------------------------------------------------------------------------- code
def code_side(active: str) -> str:
    return (
        '<nav class="side">'
        f'<a id="nav-code" class="{"on" if active == "code" else ""}" href="/portals/code/ekf-tracker">Code</a>'
        f'<a id="nav-actions" class="{"on" if active == "actions" else ""}" href="/portals/code/ekf-tracker/actions">Actions</a>'
        "</nav>"
    )


def code_shell(title: str, active: str, body: str) -> HTMLResponse:
    return shell(title=title, brand="#24292f", accent="#0969da", logo="Codehub",
                 crumb=f'<span data-entity="ekf-tracker" data-entity-type="repo">estimation-lab / ekf-tracker</span>',
                 ctx={"type": "repo", "name": "ekf-tracker", "portal": "code"}, side=code_side(active), body=body)


@router.get("/code/ekf-tracker", response_class=HTMLResponse)
async def repo_page(request: Request):
    if r := guard(request):
        return r
    rows = "".join(
        f'<tr id="commit-{sha}"><td><a href="/portals/code/ekf-tracker/commit/{sha}">{sha}</a></td><td>{esc(msg)}</td>'
        f'<td>{person(author)}</td><td>{fmt_date(when(days, 10))}</td></tr>'
        for sha, msg, author, days in REPO["commits"]
    )
    body = (
        "<h1>ekf-tracker</h1><div class='sub'>Extended Kalman Filter tracker for the lab IMU rig</div>"
        f"<div class='card'><h2>Commits</h2><table>{rows}</table></div>"
        "<div class='card' id='readme'><h2>README</h2><p>Run <code>python -m ekf_tracker.replay logs/imu.bin</code> to replay a recorded trajectory. Tests: <code>pytest -q</code>.</p></div>"
    )
    return code_shell("ekf-tracker", "code", body)


@router.get("/code/ekf-tracker/commit/{sha}", response_class=HTMLResponse)
async def commit_page(sha: str, request: Request):
    if r := guard(request):
        return r
    meta = next((c for c in REPO["commits"] if c[0] == sha), None)
    if not meta:
        return HTMLResponse("Not found", status_code=404)
    lines = []
    for ln in REPO["diffs"].get(sha, []):
        cls = "add" if ln.startswith("+") else "del" if ln.startswith("-") else ""
        lines.append(f'<span class="{cls}">{esc(ln)}</span>')
    body = (
        f"<h1>{esc(meta[1])}</h1><div class='sub'>{person(meta[2])} committed {fmt_date(when(meta[3], 10))} - {sha}</div>"
        f"<div class='card' id='diff-hunk-1'><div class='meta'>ekf_tracker/filter.py</div><pre>{chr(10).join(lines)}</pre></div>"
    )
    return code_shell(meta[1], "code", body)


@router.get("/code/ekf-tracker/actions", response_class=HTMLResponse)
async def actions_page(request: Request):
    if r := guard(request):
        return r
    rows = "".join(
        f'<div class="card" id="{rid}"><span class="pill {"fail" if st == "failing" else "pass"}">{st}</span> '
        f'<b>CI on {sha}</b><div class="meta">{fmt_date(when(days, 9))}</div><p>{esc(msg)}</p></div>'
        for rid, sha, st, days, msg in REPO["ci"]
    )
    return code_shell("Actions", "actions", f"<h1>Actions</h1>{rows}")
