---
type: episode
title: Reviewed Priya's Joseph form commit
timestamp: 2026-11-08T20:00
portal: code
url: http://127.0.0.1:8000/portals/code/ekf-tracker/commit/7be12d4
selector: '#diff-hunk-1'
text_fragment: P = IKH @ P @ IKH.T + K @ R @ K.T
snapshot_text: null
people:
- Priya Raman
entities:
- ekf-tracker
- Priya Raman
tags:
- Extended Kalman Filter
- Joseph form covariance update
session:
  viewport: 1280x800
  authenticated: true
  tab_path:
  - commit-7be12d4 a
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/code/ekf-tracker
- type: click
  selector: '#commit-7be12d4 a'
- type: scroll_to
  selector: '#diff-hunk-1'
- type: highlight
  selector: '#diff-hunk-1'
  text: P = IKH @ P @ IKH.T + K @ R @ K.T
generated_by: seed_vault
---

# Reviewed Priya's Joseph form commit

Reviewed [[Priya Raman]]'s commit 7be12d4 in [[ekf-tracker]]: Joseph form covariance update, float64 P, symmetrization.

> P = IKH @ P @ IKH.T + K @ R @ K.T

Related: [[ep-2026-11-07-1200-priya-suggested-the-joseph-form-fix]]
