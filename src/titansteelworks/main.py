# src/titansteelworks/main.py
import os, re, sys
from pathlib import Path
from typing import List, Tuple
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# -------- Load env first (so we can detect demo mode) --------
load_dotenv()  # repo .env in dev OR user-level .env from GUI (if present)

# -------- Project paths (robust for PyInstaller) --------
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
PROJECT_ROOT = BASE if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[2]
DOCS_DIR = Path(os.getenv("DOCS_DIR") or (PROJECT_ROOT / "docs"))

# -------- Config (env override + safe fallbacks) --------
MODEL_GEN_EXPAND   = os.getenv("MODEL_GEN_EXPAND", "gpt-4o-mini")
MODEL_ANSWER       = os.getenv("MODEL_ANSWER",     "gpt-4o-mini")
EMBED_MODEL        = os.getenv("EMBED_MODEL",      "text-embedding-3-small")
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", "200"))
CHUNK_SIZE         = int(os.getenv("CHUNK_SIZE", "1400"))
CHUNK_OVERLAP      = int(os.getenv("CHUNK_OVERLAP", "200"))
RETR_TOP_K         = int(os.getenv("RETR_TOP_K", "5"))
POOL_PER_VARIANT   = int(os.getenv("POOL_PER_VARIANT", "8"))
RERANK_POOL_MAX    = int(os.getenv("RERANK_POOL_MAX", "30"))
SIM_THRESHOLD_LOG  = float(os.getenv("SIM_THRESHOLD_LOG", "0.08"))

# -------- Demo Mode: true when no API key present --------
DEMO_MODE = not bool(os.getenv("OPENAI_API_KEY"))

# -------- Client (only if NOT demo mode) --------
client = None
if not DEMO_MODE:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY.")
    client = OpenAI(api_key=api_key)

# -------- Small stable company summary --------
COMPANY_SUMMARY = (
    "Titan Steelworks Inc. (demo) supplies structural beams, plate/sheet, rebar, tubing/pipe, "
    "angles/channels, with basic fabrication (cutting, drilling, coating) and delivery services."
)

# -------- Utils --------
def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

# -------- Canned (Demo Mode) responses --------
# Match by simple keywords/regex; keep answers short & businesslike.
CANNED_QA: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(beams?|i[- ]?beam|h[- ]?beam|wide\s*flange|w\d+)\b", re.I),
     "We supply I-Beams, H-Beams, and Wide Flange (W-series), typically in ASTM A36, A992, and A572 Gr 50. Sizes commonly run W6–W36."),
    (re.compile(r"\b(angles?|channels?|mc\b)\b", re.I),
     "Angles (equal/unequal) and channels (C/MC) are stocked; details and cut lengths confirmed at quote."),
    (re.compile(r"\b(plate|sheet|checker|a1011|a1018)\b", re.I),
     "Plate & sheet options include hot-rolled, cold-rolled, and checker. We confirm thickness, grade, and tolerances at quote."),
    (re.compile(r"\b(rebar|#\d+|a615|a706)\b", re.I),
     "Rebar #3–#11 in common ASTM grades; MTRs available on request."),
    (re.compile(r"\b(tub(e|ing)|pipe|sch(edu)?le?\s*(40|80))\b", re.I),
     "Square/rectangular tubing and pipe (Sch 40/80). End-prep and cut-to-length available."),
    (re.compile(r"\b(delivery|ship|lead\s*time|turnaround)\b", re.I),
     "Typical stock delivery is 1–3 business days. Fabrication adds ~3–10 business days depending on scope."),
    (re.compile(r"\b(cut|cutting|plasma|saw|waterjet|bend|roll|shear|bevel|cope|miter)\b", re.I),
     "Shop services: saw & plasma cutting, limited rolling/bending, shearing, bevels, coping, and miter cuts per drawing."),
    (re.compile(r"\b(drill|punch|hole|weld|mig|tig|finish|coat|prime|galvan)\b", re.I),
     "Holes via drilling/punching, MIG/TIG per WPS, primer coating in-house; galvanization via partners."),
    (re.compile(r"\b(mtr|mill test report|traceability|cert(ificate)?)\b", re.I),
     "Yes—Mill Test Reports (MTRs) are available upon request at order time."),
    (re.compile(r"\b(quote|pricing|estimate|rfq|how to order)\b", re.I),
     "For quotes, share sizes/grade, lengths or cut list, quantity, and delivery city. We’ll confirm availability, lead time, and pricing."),
    (re.compile(r"\b(hello|hi|hey|good (morning|afternoon|evening)|greetings)\b", re.I),
     "Good day, and welcome to Titan Steelworks’ AI Assistant—how may I help you today?"),
    (re.compile(r"\b(thanks|thank you|thx|ty)\b", re.I),
     "You’re very welcome—happy to help anytime."),
]

def canned_answer(question: str) -> str:
    q = question.strip()
    for pat, ans in CANNED_QA:
        if pat.search(q):
            return ans
    # generic fallback
    return ("I can share basics on products, fabrication, lead time, and MTRs. "
            "For a quote, provide sizes/grade, quantities, and delivery city.")

# -------- Docs loading & chunking (unchanged) --------
def load_docs_text() -> str:
    docs_dir = DOCS_DIR
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs folder not found: {docs_dir}")
    parts = []
    for p in sorted(docs_dir.glob("*.md")):
        parts.append(f"# {p.name}\n{p.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(parts)

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if chunk_size <= 0:
        return [text]
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + chunk_size, n)
        cut = text.rfind("\n", start, end)
        if cut == -1 or cut <= start + int(chunk_size * 0.45):
            cut = end
        piece = text[start:cut].strip()
        if piece:
            chunks.append(piece)
        start = max(cut - overlap, start + 1)
    return chunks

# -------- Embeddings index (no API in Demo Mode) --------
def embed_texts(texts: List[str]) -> np.ndarray:
    if DEMO_MODE:
        # Return zero-vectors to avoid API usage; retrieval path will be skipped in ask_chatbot.
        vecs = np.zeros((len(texts), 1536), dtype=np.float32)
    else:
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
        vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs / norms

def build_index(chunks: List[str]) -> Tuple[List[str], np.ndarray]:
    vectors = embed_texts(chunks)
    return chunks, vectors

# -------- Greeting / Thanks (unchanged helpers) --------
_GREETING_PATTERNS = [r"^\s*hello\b", r"^\s*hi\b", r"^\s*hey\b",
                      r"^\s*good (morning|afternoon|evening)\b",
                      r"^\s*greetings\b", r"^\s*welcome\b", r"^\s*salutations\b"]
_THANKS_PATTERNS = [r"\bthank(s| you)\b", r"\bthanks!\b", r"\bthx\b", r"\bty\b"]
_greet_re  = re.compile("|".join(_GREETING_PATTERNS), re.IGNORECASE)
_thanks_re = re.compile("|".join(_THANKS_PATTERNS), re.IGNORECASE)

def is_greeting(text: str) -> bool: return bool(_greet_re.search(text.strip()))
def is_thanks(text: str)   -> bool: return bool(_thanks_re.search(text.strip()))
def greeting_reply() -> str: return "Good day, and welcome to Titan Steelworks’ AI Assistant—how may I help you today?"
def thanks_reply() -> str:   return "You’re very welcome—happy to help anytime."

# -------- LLM-aided retrieval (skip when demo) --------
def expand_queries(question: str) -> List[str]:
    if DEMO_MODE:
        # Minimal expansion in Demo Mode (no API)
        q = normalize(question)
        return [q, q.replace("delivery time", "lead time"), q.replace("beams", "wide flange"), question][:4]
    prompt = (
        "Rewrite the user's question into 4–6 diverse search queries for internal Markdown docs. "
        "Include: (a) literal rewrite, (b) synonym-based, (c) policy/handbook phrasing, "
        "(d) typo-fixed version, (e) short keyword query, (f) optional alternate wording. "
        "Each under 12 words. One per line.\n\n"
        f"User question: {question}"
    )
    r = client.responses.create(model=MODEL_GEN_EXPAND, input=prompt, max_output_tokens=MAX_COMPLETION_TOKENS)
    text = (getattr(r, "output_text", "") or "").strip()
    lines = [q.strip(" -•\t") for q in text.splitlines() if q.strip()]
    if len(lines) < 3:
        lines = [s.strip() for s in text.replace(";", "\n").split("\n") if s.strip()]
    if question not in lines:
        lines.append(question)
    q_norm = normalize(question)
    if q_norm and q_norm not in [normalize(x) for x in lines]:
        lines.append(q_norm)
    seen, out = set(), []
    for q in lines:
        qn = normalize(q)
        if qn and qn not in seen:
            seen.add(qn); out.append(qn)
    return out[:6] if out else [normalize(question)]

def retrieve_union(queries: List[str], chunks: List[str], vectors: np.ndarray) -> List[Tuple[str, float]]:
    if DEMO_MODE:
        return []
    q_vecs = embed_texts(queries)
    scored: List[Tuple[str, float]] = []
    for qv in q_vecs:
        sims = vectors @ qv
        idxs = np.argsort(-sims)[:POOL_PER_VARIANT]
        for i in idxs:
            scored.append((chunks[int(i)], float(sims[int(i)])))
    scored.sort(key=lambda x: -x[1])
    return scored[:RERANK_POOL_MAX]

def llm_rerank(question: str, candidates: List[Tuple[str, float]]) -> List[str]:
    if DEMO_MODE or not candidates:
        return []
    previews = []
    for i, (txt, score) in enumerate(candidates):
        snippet = txt[:400].replace("\n", " ")
        previews.append(f"[{i}] score={score:.3f} :: {snippet}")
    prompt = (
        "Select the most relevant excerpts to answer the user using ONLY these excerpts. "
        f"Return the best {RETR_TOP_K} indices in descending relevance as a comma-separated list of numbers.\n\n"
        f"User: {question}\n\nExcerpts:\n" + "\n".join(previews)
    )
    r = client.responses.create(model=MODEL_GEN_EXPAND, input=prompt, max_output_tokens=MAX_COMPLETION_TOKENS)
    raw = (getattr(r, "output_text", "") or "").strip()
    idxs = []
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.isdigit():
            idxs.append(int(tok))
        if len(idxs) == RETR_TOP_K: break
    if not idxs:
        idxs = list(range(min(RETR_TOP_K, len(candidates))))
    picked, seen = [], set()
    for i in idxs:
        if 0 <= i < len(candidates):
            txt = candidates[i][0]
            sig = " ".join(txt.lower().split()[:20])
            if sig not in seen:
                seen.add(sig); picked.append(txt)
    return picked

def synthesize_answer(question: str, excerpts: List[str]) -> str:
    if DEMO_MODE:
        return canned_answer(question)
    context = "\n\n---\n\n".join(excerpts) if excerpts else "[no excerpts]"
    system = (
        "You are Titan Steelworks’ virtual assistant.\n"
        "- Answer USING ONLY the Business Information provided.\n"
        "- Keep replies ≤ one short paragraph. Use brief bullets ONLY for specs/options.\n"
        "- If information is insufficient, say so briefly, ask ONE clarifying question, and suggest "
        "sales@titansteelworks.example for a formal quote.\n"
        "- Maintain a professional corporate tone."
    )
    prompt = (
        f"Company Summary:\n{COMPANY_SUMMARY}\n\n"
        f"Business Information (excerpts):\n{context}\n\n"
        f"User: {question}\nAssistant:"
    )
    r = client.responses.create(model=MODEL_ANSWER, input=system + "\n\n" + prompt)
    return (getattr(r, "output_text", "") or "").strip()

# -------- Public entry --------
def ask_chatbot(question: str, chunks: List[str], vectors: np.ndarray) -> str:
    print("\n==============================")
    print(f"[DEBUG] DemoMode={DEMO_MODE} | User question: {question!r}")

    if is_greeting(question): return greeting_reply()
    if is_thanks(question):   return thanks_reply()

    if DEMO_MODE:
        return canned_answer(question)

    variants   = expand_queries(question)
    candidates = retrieve_union(variants, chunks, vectors)
    if candidates:
        top_sim = max(s for _, s in candidates)
        print(f"[DEBUG] Retrieval pool: {len(candidates)}, top_sim={top_sim:.3f}")
        if top_sim < SIM_THRESHOLD_LOG:
            print("[DEBUG] WARNING: low similarity; may need clarifier.")
    excerpts = llm_rerank(question, candidates) if candidates else []
    out = synthesize_answer(question, excerpts)
    if out: return out
    return ("I don’t have that exact detail on hand. Share product, sizes/grade, quantity, and delivery city, "
            "and I’ll guide you—or email sales@titansteelworks.example for a formal quote.")

# -------- CLI (unchanged) --------
def main() -> None:
    print("Titan Steelworks Chatbot (type 'exit' to quit)\n")
    full_text = load_docs_text()
    chunks = chunk_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks: raise RuntimeError("No documentation found.")
    chunk_list, vecs = build_index(chunks)

    lens = [len(c) for c in chunk_list]
    print(f"[DEBUG] Built index: {len(chunk_list)} chunks (avg {int(np.mean(lens))} chars)")

    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "quit"}: print("Goodbye!"); break
        try:
            a = ask_chatbot(q, chunk_list, vecs)
            print(f"\nChatbot: {a}\n")
        except Exception:
            import traceback; traceback.print_exc()
            raise

if __name__ == "__main__":
    main()
