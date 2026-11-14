---
type: episode
title: 'CI failed: covariance not positive definite'
timestamp: 2026-11-03T09:10
portal: code
url: http://127.0.0.1:8000/portals/code/ekf-tracker/actions
selector: '#ci-fail'
text_fragment: innovation covariance S is not positive definite at step 3127
snapshot_text: null
people: []
entities:
- ekf-tracker
- Kalman Filter Project
tags:
- Extended Kalman Filter
- positive definite covariance
session:
  viewport: 1280x800
  authenticated: true
  tab_path:
  - nav-actions
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/code/ekf-tracker
- type: click
  selector: '#nav-actions'
- type: scroll_to
  selector: '#ci-fail'
- type: highlight
  selector: '#ci-fail'
  text: innovation covariance S is not positive definite at step 3127
generated_by: seed_vault
---

# CI failed: covariance not positive definite

[[ekf-tracker]] CI went red on a3f9c21: test_covariance_psd failed at step 3127.

> innovation covariance S is not positive definite at step 3127

Related: [[ep-2026-11-02-0930-had-the-ekf-tracker-float32-commit-open]], [[ep-2026-11-03-1720-logged-the-filter-divergence-after-the-float32-s]]
