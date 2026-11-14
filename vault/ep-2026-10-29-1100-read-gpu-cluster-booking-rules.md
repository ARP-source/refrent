---
type: episode
title: Read GPU cluster booking rules
timestamp: 2026-10-29T11:00
portal: wiki
url: http://127.0.0.1:8000/portals/wiki/gpu-cluster
selector: '#gpu-1'
text_fragment: at least 24 hours in advance
snapshot_text: Book the A100 nodes through the lab calendar at least 24 hours in advance; jobs longer than 12 hours need approval.
people:
- Priya Raman
entities:
- Lab Wiki
- Estimation Lab
tags: []
session:
  viewport: 1280x800
  authenticated: true
  tab_path:
  - wiki-gpu-cluster
actions:
- type: goto
  url: http://127.0.0.1:8000/portals/wiki/
- type: click
  selector: '#wiki-gpu-cluster'
- type: scroll_to
  selector: '#gpu-1'
- type: highlight
  selector: '#gpu-1'
  text: at least 24 hours in advance
generated_by: seed_vault
---

# Read GPU cluster booking rules

[[Estimation Lab]] GPU nodes must be booked 24h ahead on the [[Lab Wiki]]; jobs over 12 hours need approval.

> at least 24 hours in advance
