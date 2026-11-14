"""Generate the demo Obsidian vault: 25 episodic memories over the last 30 days + entity hubs.

Episodes are derived from the portal registries in mock_portals.py so every stored
selector / text fragment really exists on the page the browser agent will replay.

Run standalone:  python seed_vault.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

import mock_portals as mp
from config import settings
from search_federation import extract_public_tags

GEN_TAG = "seed_vault"

# fmt: off
# key, days_ago, hh, mm, portal, title, people, hubs, start, clicks, selector, fragment, body, related
EPISODES: list[dict] = [
    dict(key="welcome", d=27, t=(10, 5), portal="canvas", title="Read CS229 welcome announcement (grading breakdown)",
         people=["Dana Chen"], hubs=["CS229", "Dana Chen"], start="/portals/canvas/courses/cs229", clicks=["#tab-announcements"],
         sel="#ann-1", frag=mp.ANNOUNCEMENTS["cs229"][0]["key"],
         body="First week of [[CS229]]. [[Dana Chen]] posted the syllabus: problem sets 40%, midterm 30%, final project 30%. Need to find a project group by Friday."),
    dict(key="guest", d=19, t=(16, 50), portal="canvas", title="Dana Chen announced guest lecture on diffusion models",
         people=["Dana Chen", "Sam Okafor"], hubs=["CS229", "Dana Chen", "Sam Okafor"], start="/portals/canvas/courses/cs229", clicks=["#tab-announcements"],
         sel="#ann-2", frag=mp.ANNOUNCEMENTS["cs229"][1]["key"],
         body="[[Dana Chen]] announced that [[Sam Okafor]] is giving a guest lecture in [[CS229]] on diffusion models for trajectory forecasting. No problem set that week."),
    dict(key="proposal_ann", d=14, t=(14, 22), portal="canvas", title="Dana Chen posted final project proposal requirements",
         people=["Dana Chen"], hubs=["CS229", "Dana Chen", "Final Project Proposal", "Kalman Filter Project"],
         start="/portals/canvas/courses/cs229", clicks=["#tab-announcements"],
         sel="#ann-3", frag=mp.ANNOUNCEMENTS["cs229"][2]["key"],
         body="[[Dana Chen]] posted the requirements for the [[Final Project Proposal]] in [[CS229]]: max 4 pages, NeurIPS template, and it MUST include a state-estimation baseline (Kalman or Extended Kalman Filter) with a quantified drift analysis over at least 10,000 steps. This is what my [[Kalman Filter Project]] needs to hit. Proposals without a baseline get returned."),
    dict(key="rubric", d=14, t=(14, 48), portal="canvas", title="Checked proposal rubric on the CS229 assignments page",
         people=["Dana Chen"], hubs=["CS229", "Final Project Proposal"], start="/portals/canvas/courses/cs229", clicks=["#tab-assignments"],
         sel="#asg-proposal", frag="State-estimation baseline (Kalman or EKF) with drift analysis: 40 points",
         body="Right after the announcement I opened the [[Final Project Proposal]] assignment in [[CS229]]. The baseline + drift analysis is worth 40 of 100 points - the biggest rubric item.", related=["proposal_ann"]),
    dict(key="oh", d=9, t=(11, 30), portal="canvas", title="Marcus Lee moved office hours to Thursday",
         people=["Marcus Lee"], hubs=["CS229", "Marcus Lee"], start="/portals/canvas/courses/cs229", clicks=["#tab-announcements"],
         sel="#ann-4", frag=mp.ANNOUNCEMENTS["cs229"][3]["key"],
         body="[[Marcus Lee]] moved [[CS229]] office hours to Thursday 4pm in Gates 104. He offered feedback on proposal baseline sections."),
    dict(key="midterm_ann", d=3, t=(9, 15), portal="canvas", title="Midterm grades released, regrade policy",
         people=["Dana Chen"], hubs=["CS229", "Dana Chen"], start="/portals/canvas/courses/cs229", clicks=["#tab-announcements"],
         sel="#ann-5", frag=mp.ANNOUNCEMENTS["cs229"][4]["key"],
         body="[[Dana Chen]] released [[CS229]] midterm grades (median 78). Regrade requests within one week via Gradescope."),
    dict(key="grades", d=3, t=(9, 40), portal="canvas", title="Looked at my CS229 midterm score",
         people=[], hubs=["CS229"], start="/portals/canvas/courses/cs229", clicks=["#tab-grades"],
         sel="#grade-midterm", frag="Midterm",
         body="Checked my [[CS229]] midterm: 84/100, above the median. Considering a regrade on question 3.", related=["midterm_ann"]),
    dict(key="ps6", d=14, t=(10, 10), portal="canvas", title="Elena Vasquez posted problem set 6 (eigenvalue perturbation)",
         people=["Elena Vasquez"], hubs=["MATH 340", "Elena Vasquez"], start="/portals/canvas/courses/math340", clicks=["#tab-announcements"],
         sel="#ann-2", frag=mp.ANNOUNCEMENTS["math340"][1]["key"],
         body="[[Elena Vasquez]] posted problem set 6 in [[MATH 340]] - eigenvalue perturbation theory and the Bauer-Fike theorem. Question 4 bounds the eigenvalue error of a perturbed covariance matrix."),
    dict(key="exam", d=21, t=(15, 5), portal="canvas", title="MATH 340 exam format announced",
         people=["Elena Vasquez"], hubs=["MATH 340", "Elena Vasquez"], start="/portals/canvas/courses/math340", clicks=["#tab-announcements"],
         sel="#ann-1", frag=mp.ANNOUNCEMENTS["math340"][0]["key"],
         body="[[Elena Vasquez]]: [[MATH 340]] exam is closed book with one double-sided page of notes; three proofs, two computational problems."),
    dict(key="recitation", d=6, t=(13, 25), portal="canvas", title="MATH 340 recitation rescheduled",
         people=["Tom Brandt"], hubs=["MATH 340", "Tom Brandt"], start="/portals/canvas/courses/math340", clicks=["#tab-announcements"],
         sel="#ann-3", frag=mp.ANNOUNCEMENTS["math340"][2]["key"],
         body="[[Tom Brandt]] moved the [[MATH 340]] recitation to Monday 5pm."),
    dict(key="abstract", d=13, t=(20, 15), portal="docs", title="Drafted the proposal abstract",
         people=["Priya Raman"], hubs=["Final Project Proposal", "Kalman Filter Project"], start="/portals/docs/proposal", clicks=[],
         sel="#sec-abstract", frag="propose a learned process-noise model that adapts Q online",
         body="Started writing the [[Final Project Proposal]] doc for the [[Kalman Filter Project]]: EKF drift on a low-cost IMU, with a learned process-noise model adapting Q online.", related=["proposal_ann"]),
    dict(key="baseline", d=12, t=(22, 30), portal="docs", title="Wrote the EKF vs UKF baseline section",
         people=[], hubs=["Final Project Proposal", "Kalman Filter Project"], start="/portals/docs/proposal", clicks=[],
         sel="#sec-baseline", frag="report drift over 10,000 steps using RMSE of position and the NEES consistency test",
         body="Wrote the Baseline section of the [[Final Project Proposal]]: constant-Q EKF vs UKF, drift over 10,000 steps with RMSE and NEES - directly answering the requirement from the announcement.", related=["proposal_ann"]),
    dict(key="dana_comment", d=10, t=(19, 5), portal="docs", title="Dana Chen commented on the baseline section",
         people=["Dana Chen"], hubs=["Dana Chen", "Final Project Proposal"], start="/portals/docs/proposal", clicks=[],
         sel="#cmt-1", frag="Please quantify the drift over 10k steps and include NEES",
         body="[[Dana Chen]] left a comment on the baseline in the [[Final Project Proposal]] doc: quantify drift over 10k steps and include NEES, not only RMSE.", related=["baseline"]),
    dict(key="method", d=8, t=(21, 40), portal="docs", title="Revised the method section (Joseph form)",
         people=["Priya Raman"], hubs=["Final Project Proposal", "Priya Raman"], start="/portals/docs/proposal", clicks=[],
         sel="#sec-method", frag="the covariance update uses the Joseph form to keep P symmetric positive definite",
         body="Revised the Method section of the [[Final Project Proposal]] after [[Priya Raman]]'s note: the covariance update now uses the Joseph form.", related=["dana_comment", "wiki_fix_suggest"]),
    dict(key="timeline", d=4, t=(18, 0), portal="docs", title="Added the project timeline",
         people=[], hubs=["Final Project Proposal"], start="/portals/docs/proposal", clicks=[],
         sel="#sec-timeline", frag="Week 3: ablations on window length and float precision",
         body="Added a three-week timeline to the [[Final Project Proposal]], including float precision ablations."),
    dict(key="wiki_break", d=11, t=(17, 20), portal="wiki", title="Logged the filter divergence after the float32 switch",
         people=[], hubs=["Lab Wiki", "Kalman Filter Project", "ekf-tracker"], start="/portals/wiki/", clicks=["#wiki-ekf-debugging"],
         sel="#log-1", frag="the innovation covariance S went negative after about 3,000 steps",
         body="My Kalman filter broke: after switching [[ekf-tracker]] to float32 the innovation covariance went negative around step 3,000 and the filter diverged. Logged it on the [[Lab Wiki]].", related=["commit_float32"]),
    dict(key="wiki_fix_suggest", d=7, t=(12, 0), portal="wiki", title="Priya suggested the Joseph form fix",
         people=["Priya Raman"], hubs=["Lab Wiki", "Priya Raman", "Kalman Filter Project"], start="/portals/wiki/ekf-debugging", clicks=[],
         sel="#log-2", frag="use the Joseph form covariance update and keep P in float64",
         body="[[Priya Raman]] replied on the [[Lab Wiki]] debugging log: use the Joseph form update, keep P in float64, symmetrize after every update.", related=["wiki_break"]),
    dict(key="wiki_fixed", d=5, t=(15, 30), portal="wiki", title="Confirmed the filter is stable again",
         people=[], hubs=["Lab Wiki", "Kalman Filter Project"], start="/portals/wiki/ekf-debugging", clicks=[],
         sel="#log-3", frag="The filter is stable for 50,000 steps",
         body="Fixed the [[Kalman Filter Project]] divergence: Joseph form + float64 covariance; stable for 50,000 steps, NEES within bounds.", related=["wiki_fix_suggest", "commit_joseph"]),
    dict(key="gpu", d=16, t=(11, 0), portal="wiki", title="Read GPU cluster booking rules",
         people=["Priya Raman"], hubs=["Lab Wiki", "Estimation Lab"], start="/portals/wiki/", clicks=["#wiki-gpu-cluster"],
         sel="#gpu-1", frag="at least 24 hours in advance",
         body="[[Estimation Lab]] GPU nodes must be booked 24h ahead on the [[Lab Wiki]]; jobs over 12 hours need approval."),
    dict(key="onboarding", d=23, t=(14, 0), portal="wiki", title="Went through lab onboarding page",
         people=["Priya Raman"], hubs=["Lab Wiki", "Estimation Lab", "Priya Raman"], start="/portals/wiki/", clicks=["#wiki-onboarding"],
         sel="#onb-1", frag="request cluster access",
         body="Onboarding for the [[Estimation Lab]]: request cluster access, join the lab channel, read coding conventions. [[Priya Raman]] maintains the page."),
    dict(key="commit_float32", d=12, t=(9, 30), portal="code", title="Had the ekf-tracker float32 commit open",
         people=[], hubs=["ekf-tracker", "Kalman Filter Project"], start="/portals/code/ekf-tracker", clicks=["#commit-a3f9c21 a"],
         sel="#diff-hunk-1", frag="x = np.zeros(STATE_DIM, dtype=np.float32)",
         body="Was looking at the [[ekf-tracker]] repo, commit a3f9c21 'Switch state vector to float32 for speed'. This is the repo/commit I had open right before my [[Kalman Filter Project]] filter broke."),
    dict(key="ci_fail", d=11, t=(9, 10), portal="code", title="CI failed: covariance not positive definite",
         people=[], hubs=["ekf-tracker", "Kalman Filter Project"], start="/portals/code/ekf-tracker", clicks=["#nav-actions"],
         sel="#ci-fail", frag="innovation covariance S is not positive definite at step 3127",
         body="[[ekf-tracker]] CI went red on a3f9c21: test_covariance_psd failed at step 3127.", related=["commit_float32", "wiki_break"]),
    dict(key="commit_joseph", d=6, t=(20, 0), portal="code", title="Reviewed Priya's Joseph form commit",
         people=["Priya Raman"], hubs=["ekf-tracker", "Priya Raman"], start="/portals/code/ekf-tracker", clicks=["#commit-7be12d4 a"],
         sel="#diff-hunk-1", frag="P = IKH @ P @ IKH.T + K @ R @ K.T",
         body="Reviewed [[Priya Raman]]'s commit 7be12d4 in [[ekf-tracker]]: Joseph form covariance update, float64 P, symmetrization.", related=["wiki_fix_suggest"]),
    dict(key="labmeeting", d=2, t=(16, 30), portal="docs", title="Lab meeting: Dana suggested a process-noise ablation",
         people=["Dana Chen", "Priya Raman"], hubs=["Estimation Lab", "Dana Chen", "Priya Raman", "Kalman Filter Project"], start="/portals/docs/lab-meeting", clicks=[],
         sel="#lm-2", frag="Dana suggested ablating process noise magnitude",
         body="At the [[Estimation Lab]] meeting [[Dana Chen]] suggested ablating process noise magnitude before training anything learned, and reporting NEES with RMSE. [[Priya Raman]] reported the float64 port works."),
    dict(key="dashboard", d=1, t=(10, 45), portal="canvas", title="Opened Canvas dashboard",
         people=["Dana Chen", "Elena Vasquez"], hubs=["CS229", "MATH 340"], start="/portals/canvas/", clicks=[],
         sel="#course-cs229", frag="CS229",
         body="Quick look at the Canvas dashboard: [[CS229]] and [[MATH 340]]."),

    # ---- STAT 310: high-clutter lookalike study guides / drafts (90%+ shared vocabulary) ----
    dict(key="stat_ann_q3", d=16, t=(9, 30), portal="canvas", title="Irina Rostova announced Quiz 3 and Friday office hours",
         people=["Irina Rostova"], hubs=["STAT 310", "Irina Rostova"], start="/portals/canvas/courses/stat310", clicks=["#tab-announcements"],
         sel="#ann-1", frag=mp.ANNOUNCEMENTS["stat310"][0]["key"],
         body="[[Irina Rostova]] announced [[STAT 310]] Quiz 3 on the discrete Kalman filter, with extra office hours Friday at 4pm."),
    dict(key="kf_v1", d=20, t=(19, 30), portal="docs", title="Opened Kalman Filter Study Guide (v1)",
         people=[], hubs=["STAT 310"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-kf-guide-v1"],
         sel="#sec-update", frag="the steady-state Kalman gain converges after about 25 steps",
         body="Started the first Kalman filter study guide for [[STAT 310]]: state-space model, prediction and update steps, Riccati recursion, tuning Q and R."),
    dict(key="ito", d=24, t=(21, 0), portal="docs", title="Read the Ito Calculus Primer",
         people=[], hubs=["STAT 310"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-ito-primer"],
         sel="#sec-update", frag="Ito isometry",
         body="Read the Ito calculus primer for [[STAT 310]]: Brownian motion, quadratic variation, Ito integral and Ito's lemma."),
    dict(key="prop_a", d=17, t=(22, 10), portal="docs", title="Edited Kalman Filter Project Proposal - Draft A",
         people=["Priya Raman"], hubs=["Kalman Filter Project", "Priya Raman", "STAT 310"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-kf-proposal-a"],
         sel="#sec-update", frag="Initial values Q = 0.01 I and R = 0.5",
         body="Worked on draft A of the [[Kalman Filter Project]] proposal with [[Priya Raman]]: adaptive Kalman filter study, tuning process noise Q and measurement noise R for the constant-velocity model."),
    dict(key="sc_guide", d=14, t=(10, 15), portal="docs", title="Reviewed the Stochastic Calculus Study Guide",
         people=[], hubs=["STAT 310"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-sc-guide"],
         sel="#sec-update", frag="Ito's lemma: df",
         body="Morning review of the stochastic calculus study guide for [[STAT 310]]: Ito's lemma, Kalman-Bucy filter, Q and R for the continuous-time Kalman filter."),
    dict(key="kf_quiz3", d=14, t=(15, 38), portal="docs", title="Reviewed Kalman Filter Study Guide - Quiz 3 prep",
         people=["Irina Rostova"], hubs=["STAT 310", "Irina Rostova"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-kf-guide-quiz3"],
         sel="#sec-update", frag="for the constant-velocity model; the steady-state Kalman gain converges after about",
         body="Went over the Quiz 3 prep Kalman filter study guide for [[STAT 310]] right before [[EVT:oh14]]. Copied down the worked example (Q, R and steps to convergence) to ask [[Irina Rostova]] about."),
    dict(key="kf_midterm", d=12, t=(20, 45), portal="docs", title="Reviewed Kalman Filter Study Guide v3 - Midterm review",
         people=[], hubs=["STAT 310"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-kf-guide-midterm"],
         sel="#sec-update", frag="the steady-state Kalman gain converges after about 60 steps",
         body="Midterm review Kalman filter study guide for [[STAT 310]]: prediction, update, Riccati recursion and tuning Q and R."),
    dict(key="prop_b", d=7, t=(21, 15), portal="docs", title="Edited Kalman Filter Project Proposal - Draft B",
         people=["Priya Raman"], hubs=["Kalman Filter Project", "Priya Raman", "STAT 310"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-kf-proposal-b"],
         sel="#sec-update", frag="Initial values Q = 0.03 I and R = 0.4",
         body="Draft B of the [[Kalman Filter Project]] proposal: adaptive Kalman filter study with online tuning of Q and R.", related=["prop_a"]),
    dict(key="kf_quiz4_faq", d=3, t=(18, 20), portal="docs", title="Read Kalman Filter Study Guide - Prof. Rostova quiz and office hours FAQ",
         people=["Irina Rostova"], hubs=["STAT 310", "Irina Rostova"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-kf-guide-quiz4"],
         sel="#sec-update", frag="Prof. Rostova said the quiz uses Q = 0.05 I and R = 0.2",
         body="Read the Kalman filter study guide with Prof. [[Irina Rostova]]'s quiz and office hours FAQ for [[STAT 310]]."),
    dict(key="sheet_kf", d=1, t=(20, 10), portal="docs", title="Opened Quiz 4 formula sheet - Kalman update",
         people=["Irina Rostova"], hubs=["STAT 310", "Irina Rostova"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-sheet-kf"],
         sel="#sec-formulas", frag="Quiz 4 formula sheet",
         body="Opened the [[STAT 310]] Quiz 4 formula sheet the night before [[EVT:quiz4]] with [[Irina Rostova]]: Kalman gain, update equations and Ito's lemma."),
    dict(key="sheet_ito", d=1, t=(20, 13), portal="docs", title="Opened Quiz 4 formula sheet - Ito's lemma",
         people=["Irina Rostova"], hubs=["STAT 310", "Irina Rostova"], start="/portals/canvas/courses/stat310", clicks=["#tab-files", "#file-sheet-ito"],
         sel="#sec-formulas", frag="Quiz 4 formula sheet",
         body="Opened the [[STAT 310]] Quiz 4 formula sheet the night before [[EVT:quiz4]] with [[Irina Rostova]]: Ito's lemma, Ito isometry and the Kalman gain."),
]

HUBS: dict[str, dict] = {
    "Dana Chen": dict(kind="person", aliases=["Prof. Chen", "Professor Chen"], body="Professor for [[CS229]]. Runs the [[Estimation Lab]]. Pronouns: she/her."),
    "Marcus Lee": dict(kind="person", aliases=["Marcus"], body="TA for [[CS229]]. Pronouns: he/him."),
    "Elena Vasquez": dict(kind="person", aliases=["Prof. Vasquez"], body="Professor for [[MATH 340]]. Pronouns: she/her."),
    "Tom Brandt": dict(kind="person", aliases=["Tom"], body="TA for [[MATH 340]]. Pronouns: he/him."),
    "Priya Raman": dict(kind="person", aliases=["Priya"], body="Labmate in the [[Estimation Lab]]; co-author on the [[Final Project Proposal]]. Pronouns: she/her."),
    "Sam Okafor": dict(kind="person", aliases=["Dr. Okafor"], body="Guest lecturer in [[CS229]] (diffusion models)."),
    "CS229": dict(kind="course", aliases=["cs229"], body="Machine Learning and State Estimation, taught by [[Dana Chen]] with TA [[Marcus Lee]]."),
    "MATH 340": dict(kind="course", aliases=["math340"], body="Numerical Linear Algebra, taught by [[Elena Vasquez]] with TA [[Tom Brandt]]."),
    "Final Project Proposal": dict(kind="project", aliases=["proposal"], body="CS229 final project proposal for the [[Kalman Filter Project]]."),
    "Kalman Filter Project": dict(kind="project", aliases=["EKF project"], body="EKF drift mitigation project; code in [[ekf-tracker]], debugging on the [[Lab Wiki]]."),
    "Estimation Lab": dict(kind="org", aliases=[], body="Research lab led by [[Dana Chen]]; members include [[Priya Raman]]."),
    "Lab Wiki": dict(kind="tool", aliases=["wiki"], body="Wiki of the [[Estimation Lab]]."),
    "ekf-tracker": dict(kind="repo", aliases=["ekf tracker"], body="Repository for the [[Kalman Filter Project]]."),
    "Irina Rostova": dict(kind="person", aliases=["Prof. Rostova", "Professor Rostova", "Rostova"], body="Professor for [[STAT 310]]. Holds office hours Fridays at 4pm. Pronouns: she/her."),
    "Wei Zhang": dict(kind="person", aliases=[], body="TA for [[STAT 310]]. Pronouns: he/him."),
    "STAT 310": dict(kind="course", aliases=["stat310"], body="Stochastic Processes and Filtering, taught by [[Irina Rostova]] with TA [[Wei Zhang]]."),
}
# fmt: on


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]


def _write(path: Path, fm: dict, body: str) -> None:
    text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text(f"---\n{text}---\n\n{body.strip()}\n", encoding="utf-8")


FINAL_PATH = {  # where the click chain lands (used for the url field)
    "#tab-announcements": "/announcements",
    "#tab-assignments": "/assignments",
    "#tab-grades": "/grades",
    "#tab-files": "/files",
}


def event_id(e: dict) -> str:
    return f"{e['title']} {mp.when(e['days_ago'], e['hour'], e['minute']):%Y-%m-%d}"


EVENT_IDS = {e["key"]: event_id(e) for e in mp.EVENTS}


def snapshot_for(ep: dict) -> str | None:
    """Text of the target element *as it was when the episode happened* (for change detection)."""
    sel = ep["sel"].lstrip("#")
    doc = next((c[len("#file-"):] for c in ep["clicks"] if c.startswith("#file-")), None)
    if not doc and ep["start"].startswith("/portals/docs/"):
        doc = ep["start"].rsplit("/", 1)[-1]
    if doc:
        return mp.section_text(doc, sel, viewed_days_ago=ep["d"])
    if ep["portal"] == "canvas" and sel.startswith("ann-"):
        cid = ep["start"].split("/courses/")[1].split("/")[0]
        a = next((a for a in mp.ANNOUNCEMENTS[cid] if a["id"] == sel), None)
        return " ".join(a["paras"]) if a else None
    if ep["portal"] == "wiki":
        for w in mp.WIKI.values():
            for eid, _d, _a, text in w["entries"]:
                if eid == sel:
                    return text
    return None


def final_url(ep: dict) -> str:
    start = ep["start"]
    for c in ep["clicks"]:
        if c in FINAL_PATH:
            start = start.rstrip("/") + FINAL_PATH[c]
        elif c.startswith("#file-"):
            start = "/portals/docs/" + c[len("#file-"):]
        elif c.startswith("#wiki-"):
            start = "/portals/wiki/" + c[len("#wiki-"):]
        elif c.startswith("#commit-"):
            start = "/portals/code/ekf-tracker/commit/" + c.split()[0][len("#commit-"):]
        elif c == "#nav-actions":
            start = "/portals/code/ekf-tracker/actions"
    return settings.base_url + start


def seed(vault_dir: Path | None = None) -> int:
    vault_dir = vault_dir or settings.vault_dir
    vault_dir.mkdir(parents=True, exist_ok=True)
    for p in vault_dir.glob("*.md"):  # only remove notes we generated - captured episodes survive
        try:
            if f"generated_by: {GEN_TAG}" in p.read_text(encoding="utf-8"):
                p.unlink()
        except OSError:
            pass

    ids: dict[str, str] = {}
    for ep in EPISODES:
        ts = mp.when(ep["d"], *ep["t"])
        ids[ep["key"]] = f"ep-{ts:%Y-%m-%d-%H%M}-{slug(ep['title'])}"

    for ep in EPISODES:
        ts = mp.when(ep["d"], *ep["t"])
        actions = [{"type": "goto", "url": settings.base_url + ep["start"]}]
        actions += [{"type": "click", "selector": c} for c in ep["clicks"]]
        actions += [
            {"type": "scroll_to", "selector": ep["sel"]},
            {"type": "highlight", "selector": ep["sel"], "text": ep["frag"]},
        ]
        fm = {
            "type": "episode",
            "title": ep["title"],
            "timestamp": ts.isoformat(timespec="minutes"),
            "portal": ep["portal"],
            "url": final_url(ep),
            "selector": ep["sel"],
            "text_fragment": ep["frag"],
            "snapshot_text": snapshot_for(ep),
            "people": ep["people"],
            "entities": [EVENT_IDS[h[4:]] if h.startswith("EVT:") else h for h in ep["hubs"]],
            "tags": extract_public_tags(f"{ep['title']} {ep['body']} {ep['frag']}"),
            "session": {
                "viewport": f"{settings.viewport_w}x{settings.viewport_h}",
                "authenticated": True,
                "tab_path": [c.lstrip("#") for c in ep["clicks"]],
            },
            "actions": actions,
            "generated_by": GEN_TAG,
        }
        related = [f"[[{ids[k]}]]" for k in ep.get("related", []) if k in ids]
        text = re.sub(r"\[\[EVT:(\w+)\]\]", lambda m: f"[[{EVENT_IDS[m.group(1)]}]]", ep["body"])
        body = f"# {ep['title']}\n\n{text}\n\n> {ep['frag']}\n"
        if related:
            body += "\nRelated: " + ", ".join(related) + "\n"
        _write(vault_dir / f"{ids[ep['key']]}.md", fm, body)

    for name, h in HUBS.items():
        fm = {"type": h["kind"], "title": name, "aliases": h["aliases"], "generated_by": GEN_TAG}
        _write(vault_dir / f"{name}.md", fm, f"# {name}\n\n{h['body']}\n")

    for e in mp.EVENTS:  # calendar events: temporal anchors + "calendar context" hubs
        eid = EVENT_IDS[e["key"]]
        ts = mp.when(e["days_ago"], e["hour"], e["minute"])
        fm = {"type": "event", "title": eid, "timestamp": ts.isoformat(timespec="minutes"), "where": e["where"],
              "people": e["people"], "url": settings.base_url + "/portals/calendar", "generated_by": GEN_TAG}
        links = " ".join(f"[[{p}]]" for p in e["people"])
        _write(vault_dir / f"{eid}.md", fm, f"# {eid}\n\n{e['title']} for [[{e['course']}]] with {links} in {e['where']} at {ts:%H:%M}.\n")
    return len(EPISODES) + len(HUBS) + len(mp.EVENTS)


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} notes into {settings.vault_dir}", file=sys.stderr)
