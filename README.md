# Titan Steelworks Chatbot (Showcase Project)

## Overview
AI-powered chatbot demo for **Titan Steelworks Inc.**, a fictional steel manufacturing and fabrication company.  
The chatbot is designed to act as a **virtual sales and support representative**, answering customer questions using the documentation included in this repository.  

---

## Why This Project
- **Recognizable industry**: Steel manufacturing is professional and easy to understand.  
- **Applied AI**: Demonstrates how a chatbot can be tailored to a business using structured documentation.  
- **Portfolio value**: Showcases practical AI integration in a business-relevant scenario.  

---

## Repository Structure
- **docs/** → Knowledge base for the chatbot  
  - `BusinessProfile.md` → Company overview, services, policies  
  - `ProductCatalog.md` → Core products with specifications  
  - `FAQ.md` → Customer Q&A  
- **app/** → Chatbot implementation (to be added)  
  - `main.py` / `main.cs` → CLI or API chatbot  
 - **src/titansteelworks/** → Python package with the chatbot implementation
  - `gui.py` → Desktop GUI entrypoint
  - `main.py` → Core chatbot logic and retrieval
- **README.md** → Project overview  

---

## Example Conversations
- **Q: What kinds of beams do you sell?**  
  A: Titan Steelworks supplies I-Beams, H-Beams, and Wide Flange (W) beams, typically in ASTM A36, A992, and A572 Gr 50 grades. Sizes range from W6 to W36.  

- **Q: How long does delivery usually take?**  
  A: Stock items typically ship in 1–3 business days. Fabrication orders may take an additional 3–10 business days.  

- **Q: Can I get mill test reports (MTRs)?**  
  A: Yes, MTRs are available upon request at the time of ordering.  

---

## Roadmap
- **Step 1**: Add business documentation (profile, catalog, FAQ) ✅  
- **Step 2**: Build chatbot (CLI demo) that answers using docs ✅   

---

## Running locally (dev)

1) Create & activate a venv and install deps:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\Activate.ps1
# Titan Steelworks Chatbot (Showcase Project)

## Overview
AI-powered chatbot demo for **Titan Steelworks Inc.**, a fictional steel manufacturing and fabrication company.
This repo contains the documentation, a small Python package and a desktop GUI demo used to showcase an industry-specific assistant.

## Current project state
- Source code: implemented under `src/titansteelworks/` (GUI entrypoint: `src/titansteelworks/gui.py`).
- Documentation: `docs/` contains the knowledge base used by the bot (FAQ, product catalog, etc.).
- Packaging: `packaging/build_exe.ps1` builds a single-file Windows EXE using PyInstaller.
- CI: a GitHub Actions workflow (`.github/workflows/release-windows.yml`) builds and uploads a release artifact when you push a tag matching `v*`.

Notes:
- Build artifacts (folder `dist/`, `build/`, and `*.spec`) are intentionally git-ignored — we publish EXE artifacts via GitHub Releases instead of checking binaries into source control.

## Repository structure (important files)
- `docs/` — knowledge base used by the chatbot
- `src/titansteelworks/` — Python package and demo GUI
- `packaging/` — packaging helpers and scripts (see `build_exe.ps1`)
- `.github/workflows/release-windows.yml` — CI workflow that builds Windows EXE and publishes Releases (tag-triggered)
- `.gitattributes` — marks binary patterns as binary for git

## Builds and Releases (recommended way)
We publish built EXE artifacts via GitHub Releases produced by CI. This keeps the repository clean and makes builds reproducible.

Typical flow (recommended):
1. Push a semver tag to the repo (example: `v1.0.0`). CI will run and create a Release with the ZIP artifact attached.

Local commands to tag and push:
```powershell
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

What the CI does (overview):
- Installs Python and dependencies
- Runs `packaging/build_exe.ps1` (produces `dist/TitanSteelworks.Chatbot.exe`)
- Creates a SHA256 checksum and zips EXE + checksum
- Creates a GitHub Release for the tag and uploads the zip as an asset

## Building locally (dev)
If you want to build locally for testing:

1) Create & activate a venv and install deps:
```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Run the GUI (dev mode):
```powershell
& .\.venv\Scripts\python.exe .\src\titansteelworks\gui.py
```

3) Build a single-file Windows EXE locally:
```powershell
& .\.venv\Scripts\Activate.ps1
.\packaging\build_exe.ps1
```

After a successful local build, the EXE will be at `dist\TitanSteelworks.Chatbot.exe` (this folder is ignored by git by default).

If you need to distribute the build manually, create a zip including the EXE and a `.sha256` checksum, then upload it to a Release (recommended) or distribute out-of-band.

## If you want binaries tracked in git (not recommended)
- `dist/` is ignored by default. To force-add a built artifact (not recommended), use:
```powershell
git add -f .\dist\TitanSteelworks.Chatbot.exe
git commit -m "Add built EXE"
git push origin main
```

Better alternatives are using GitHub Releases (automated by CI), a package registry, or an external file host.

## Optional next steps you can ask me to implement
- Add `workflow_dispatch` to the CI so you can trigger a release build from the Actions UI.
- Add a code-signing step (requires storing a signing certificate in GitHub Secrets).
- Add Release Drafter or automated changelog generation.

## License
This project is for portfolio/demo purposes only. **Titan Steelworks Inc.** is a fictional company.
