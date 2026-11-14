---
type: episode
title: Confirmed the filter is stable again
timestamp: 2026-11-09T15:30
portal: wiki
url: http://127.0.0.1:8000/portals/wiki/ekf-debugging
selector: '#log-3'
text_fragment: The filter is stable for 50,000 steps
snapshot_text: 'Fixed: Joseph form plus float64 covariance. The filter is stable for 50,000 steps and NEES is back inside the 95 percent bounds.'
people: []
entities:
- Lab Wiki
- Kalman Filter Project
tags:
- Joseph form covariance update
- NEES consistency test
- Kalman filter
- filter divergence
session:
  viewport: 1280x800
  authenticated: true
  tab_path: []
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/wiki/ekf-debugging
- type: scroll_to
  selector: '#log-3'
- type: highlight
  selector: '#log-3'
  text: The filter is stable for 50,000 steps
generated_by: seed_vault
---

# Confirmed the filter is stable again

Fixed the [[Kalman Filter Project]] divergence: Joseph form + float64 covariance; stable for 50,000 steps, NEES within bounds.

> The filter is stable for 50,000 steps

Related: [[ep-2026-11-07-1200-priya-suggested-the-joseph-form-fix]], [[ep-2026-11-08-2000-reviewed-priya-s-joseph-form-commit]]
