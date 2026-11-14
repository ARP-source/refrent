---
type: episode
title: Priya suggested the Joseph form fix
timestamp: 2026-11-07T12:00
portal: wiki
url: http://127.0.0.1:8000/portals/wiki/ekf-debugging
selector: '#log-2'
text_fragment: use the Joseph form covariance update and keep P in float64
snapshot_text: 'Suggestion: use the Joseph form covariance update and keep P in float64; symmetrize P after every update.'
people:
- Priya Raman
entities:
- Lab Wiki
- Priya Raman
- Kalman Filter Project
tags:
- Joseph form covariance update
session:
  viewport: 1280x800
  authenticated: true
  tab_path: []
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/wiki/ekf-debugging
- type: scroll_to
  selector: '#log-2'
- type: highlight
  selector: '#log-2'
  text: use the Joseph form covariance update and keep P in float64
generated_by: seed_vault
---

# Priya suggested the Joseph form fix

[[Priya Raman]] replied on the [[Lab Wiki]] debugging log: use the Joseph form update, keep P in float64, symmetrize after every update.

> use the Joseph form covariance update and keep P in float64

Related: [[ep-2026-11-03-1720-logged-the-filter-divergence-after-the-float32-s]]
