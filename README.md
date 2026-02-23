# 🎬 Anim Scene Validator – Maya 2025

Production-style scene validation tool for Autodesk Maya.

Designed as a lightweight demo of a real pipeline validation system used in animation workflows.

---

Anim Scene Validator is a modular validation tool built with:

- Python 3
- Maya 2025
- PySide6 (Qt6)

It simulates real production checks typically executed before publish.

The tool allows artists and TDs to:

✔ Run individual checks  
✔ Detect scene issues  
✔ Automatically fix common problems  
✔ Visually validate scene readiness  

---

## 🧩 Current Checks

- Naming validation (illegal / sanitized names)
- Camera near clip validation
- ImagePlane connections
- Time unit (FPS) validation
- Keyframes outside playback range

All checks include:

- Status indicator (WAIT / ERROR / OK)
- Detailed issue reporting
- One-click fix (when applicable)
- Scene selection on issue



