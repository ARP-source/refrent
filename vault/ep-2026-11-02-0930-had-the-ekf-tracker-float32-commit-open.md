---
type: episode
title: Had the ekf-tracker float32 commit open
timestamp: 2026-11-02T09:30
portal: code
url: http://127.0.0.1:8000/portals/code/ekf-tracker/commit/a3f9c21
selector: '#diff-hunk-1'
text_fragment: x = np.zeros(STATE_DIM, dtype=np.float32)
snapshot_text: null
people: []
entities:
- ekf-tracker
- Kalman Filter Project
tags:
- Extended Kalman Filter
- Kalman filter
- float32 numerical precision
session:
  viewport: 1280x800
  authenticated: true
  tab_path:
  - commit-a3f9c21 a
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/code/ekf-tracker
- type: click
  selector: '#commit-a3f9c21 a'
- type: scroll_to
  selector: '#diff-hunk-1'
- type: highlight
  selector: '#diff-hunk-1'
  text: x = np.zeros(STATE_DIM, dtype=np.float32)
generated_by: seed_vault
---

# Had the ekf-tracker float32 commit open

Was looking at the [[ekf-tracker]] repo, commit a3f9c21 'Switch state vector to float32 for speed'. This is the repo/commit I had open right before my [[Kalman Filter Project]] filter broke.

> x = np.zeros(STATE_DIM, dtype=np.float32)
