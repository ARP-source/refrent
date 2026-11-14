---
type: episode
title: Logged the filter divergence after the float32 switch
timestamp: 2026-11-03T17:20
portal: wiki
url: http://127.0.0.1:8000/portals/wiki/ekf-debugging
selector: '#log-1'
text_fragment: the innovation covariance S went negative after about 3,000 steps
snapshot_text: After switching the state vector to float32 the innovation covariance S went negative after about 3,000 steps and the filter diverged.
people: []
entities:
- Lab Wiki
- Kalman Filter Project
- ekf-tracker
tags:
- Extended Kalman Filter
- Kalman filter
- filter divergence
- float32 numerical precision
session:
  viewport: 1280x800
  authenticated: true
  tab_path:
  - wiki-ekf-debugging
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/wiki/
- type: click
  selector: '#wiki-ekf-debugging'
- type: scroll_to
  selector: '#log-1'
- type: highlight
  selector: '#log-1'
  text: the innovation covariance S went negative after about 3,000 steps
generated_by: seed_vault
---

# Logged the filter divergence after the float32 switch

My Kalman filter broke: after switching [[ekf-tracker]] to float32 the innovation covariance went negative around step 3,000 and the filter diverged. Logged it on the [[Lab Wiki]].

> the innovation covariance S went negative after about 3,000 steps

Related: [[ep-2026-11-02-0930-had-the-ekf-tracker-float32-commit-open]]
