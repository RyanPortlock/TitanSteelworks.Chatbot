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

## Example Conversations (Planned)
- **Q: What kinds of beams do you sell?**  
  A: Titan Steelworks supplies I-Beams, H-Beams, and Wide Flange (W) beams, typically in ASTM A36, A992, and A572 Gr 50 grades. Sizes range from W6 to W36.  

- **Q: How long does delivery usually take?**  
  A: Stock items typically ship in 1–3 business days. Fabrication orders may take an additional 3–10 business days.  

- **Q: Can I get mill test reports (MTRs)?**  
  A: Yes, MTRs are available upon request at the time of ordering.  

---

## Roadmap
- **Step 1**: Add business documentation (profile, catalog, FAQ) ✅  
- **Step 2**: Build chatbot (CLI demo) that answers using docs 🚧  
- **Step 3**: Add lightweight web UI & Docker support 🚧  
- **Step 4**: Integrate GitHub Actions for automated testing 🚧  

---

## Running locally (dev)

1) Create & activate a venv and install deps:

```powershell
py -3.11 -m venv .venv
& .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Run the GUI from the repo root:

```powershell
& .\.venv\Scripts\python.exe .\src\titansteelworks\gui.py
```

3) Build a Windows EXE (one-file) using the provided script:

```powershell
& .\.venv\Scripts\Activate.ps1
.\packaging\build_exe.ps1
```

Notes:
- Keep your OpenAI API key out of source control; the app will prompt to save it to a local per-user `.env` when needed.
- Use `packaging/clean_build.ps1` to remove build artifacts.

---

## License
This project is for **portfolio/demo purposes only**.  
**Titan Steelworks Inc.** is a fictional company.  
