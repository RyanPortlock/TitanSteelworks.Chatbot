import os
import re
from pathlib import Path
from typing import List, Tuple
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# ===================== Config =====================
MODEL_GEN_EXPAND   = "gpt-5-mini"   # query expansion + rerank
MODEL_ANSWER       = "gpt-5-nano"   # grounded answer synthesis
EMBED_MODEL        = "text-embedding-3-small"
MAX_COMPLETION_TOKENS = 200         # cap ONLY where supported (mini)
CHUNK_SIZE         = 1400           # larger so bullets stay intact
CHUNK_OVERLAP      = 200
RETR_TOP_K         = 8              # final excerpts to synthesize from
POOL_PER_VARIANT   = 8              # chunks per query variant to pool
RERANK_POOL_MAX    = 40             # upper bound for reranking set
SIM_THRESHOLD_LOG  = 0.08           # debug signal only

# ===================== Env & Client =====================
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Missing OPENAI_API_KEY in .env")
client = OpenAI(api_key=api_key)

# ===================== Company Summary (small, stable context) =====================
COMPANY_SUMMARY = (
    "Titan Steelworks Inc. (demo) supplies structural beams, plate/sheet, rebar, tubing/pipe, "
    "angles/channels, with basic fabrication (cutting, drilling, coating) and delivery services."
)

# ===================== Utility: Normalization (lightweight only) =====================
def normalize(text: str) -> str:
    """Lowercase + collapse whitespace; let the LLM infer synonyms/typos."""
    return re.sub(r"\s+", " ", text.lower()).strip()

# ===================== Docs loading & chunking =====================
def load_docs_text() -> str:
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs folder not found: {docs_dir}")
    parts = []
    for p in sorted(docs_dir.glob("*.md")):
        txt = p.read_text(encoding="utf-8")
        parts.append(f"# {p.name}\n{txt}")
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

# ===================== Embeddings index =====================
def embed_texts(texts: List[str]) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    return vecs / norms

def build_index(chunks: List[str]) -> Tuple[List[str], np.ndarray]:
    vectors = embed_texts(chunks)
    return chunks, vectors

# ===================== Greeting / Thanks handling =====================
_GREETING_PATTERNS = [
    r"^\s*hello\b", r"^\s*hi\b", r"^\s*hey\b",
    r"^\s*good (morning|afternoon|evening)\b",
    r"^\s*greetings\b", r"^\s*welcome\b", r"^\s*salutations\b"
]
_THANKS_PATTERNS = [
    r"\bthank(s| you)\b", r"\bthanks!\b", r"\bthx\b", r"\bty\b"
]
_greet_re = re.compile("|".join(_GREETING_PATTERNS), re.IGNORECASE)
_thanks_re = re.compile("|".join(_THANKS_PATTERNS), re.IGNORECASE)

def is_greeting(text: str) -> bool:
    return bool(_greet_re.search(text.strip()))

def is_thanks(text: str) -> bool:
    return bool(_thanks_re.search(text.strip()))

def greeting_reply() -> str:
    return "Good day, and welcome to Titan Steelworks’ AI Assistant—how may I help you today?"

def thanks_reply() -> str:
    return "You’re very welcome—happy to help anytime."

# ===================== LLM-Aided Retrieval =====================
def expand_queries(question: str) -> List[str]:
    """
    Ask the LLM for 4–6 diverse variants:
      (a) literal rewrite, (b) synonym-based, (c) policy/handbook phrasing,
      (d) typo-corrected, (e) short keyword query, (f) optional alternate wording.
    Keep each under 12 words. Return one per line.
    """
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

    # Always include the original and a lightly-normalized copy
    if question not in lines:
        lines.append(question)
    q_norm = normalize(question)
    if q_norm and q_norm not in [normalize(x) for x in lines]:
        lines.append(q_norm)

    # Deduplicate by light normalize
    seen, out = set(), []
    for q in lines:
        qn = normalize(q)
        if qn and qn not in seen:
            seen.add(qn)
            out.append(qn)
    return out[:6] if out else [normalize(question)]

def retrieve_union(queries: List[str], chunks: List[str], vectors: np.ndarray) -> List[Tuple[str, float]]:
    """For each variant: embed → cosine rank → take top pool; return union sorted by score."""
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
    """Show short previews to LLM; get best RETR_TOP_K indices back."""
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
        if len(idxs) == RETR_TOP_K:
            break
    if not idxs:
        idxs = list(range(min(RETR_TOP_K, len(candidates))))
    picked, seen_signatures = [], set()
    for i in idxs:
        if 0 <= i < len(candidates):
            txt = candidates[i][0]
            sig = " ".join(txt.lower().split()[:20])
            if sig not in seen_signatures:
                seen_signatures.add(sig)
                picked.append(txt)
    return picked

def synthesize_answer(question: str, excerpts: List[str]) -> str:
    """Constrain the answer to provided excerpts; ask one clarifier if insufficient."""
    context = "\n\n---\n\n".join(excerpts) if excerpts else "[no excerpts]"
    system = (
        "You are Titan Steelworks’ virtual assistant.\n"
        "- Answer USING ONLY the Business Information provided.\n"
        "- Keep replies ≤ one short paragraph. Use brief bullets ONLY for specs/options.\n"
        "- If information is insufficient, say so briefly, ask ONE clarifying question, and suggest "
        "sales@titansteelworks.example for a formal quote.\n"
        "- Maintain a professional corporate tone (no slang, humor, or character voices)."
    )
    prompt = (
        f"Company Summary:\n{COMPANY_SUMMARY}\n\n"
        f"Business Information (excerpts):\n{context}\n\n"
        f"User: {question}\nAssistant:"
    )
    r = client.responses.create(model=MODEL_ANSWER, input=system + "\n\n" + prompt)
    return (getattr(r, "output_text", "") or "").strip()

# ===================== Main chat =====================
def ask_chatbot(question: str, chunks: List[str], vectors: np.ndarray) -> str:
    print("\n==============================")
    print(f"[DEBUG] User question: {question!r}")

    if is_greeting(question):
        print("[DEBUG] Detected greeting → canned greeting.")
        return greeting_reply()

    if is_thanks(question):
        print("[DEBUG] Detected thanks → canned reply.")
        return thanks_reply()

    variants = expand_queries(question)
    print(f"[DEBUG] Query variants: {variants}")

    candidates = retrieve_union(variants, chunks, vectors)
    if candidates:
        top_sim = max(s for _, s in candidates)
        print(f"[DEBUG] Retrieval pool size: {len(candidates)}, top_sim={top_sim:.3f}")
        if top_sim < SIM_THRESHOLD_LOG:
            print("[DEBUG] WARNING: top similarity is low; may need clarifier.")
    else:
        print("[DEBUG] Retrieval pool empty; proceeding with no excerpts.")
        candidates = []

    excerpts = llm_rerank(question, candidates) if candidates else []
    print(f"[DEBUG] Selected {len(excerpts)} excerpts for synthesis.")

    out = synthesize_answer(question, excerpts)
    if out:
        print(f"[DEBUG] Final reply (head): {repr(out[:200])}")
        return out

    return ("I don’t have that exact detail on hand. Share product, sizes/grade, quantity, and delivery city, "
            "and I’ll guide you—or email sales@titansteelworks.example for a formal quote.")

# ===================== CLI =====================
def main() -> None:
    print("Titan Steelworks Chatbot (type 'exit' to quit)\n")
    full_text = load_docs_text()
    chunks = chunk_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        raise RuntimeError("No documentation found. Please add content to the docs folder.")
    chunk_list, vecs = build_index(chunks)

    lens = [len(c) for c in chunk_list]
    print(f"[DEBUG] Built index: {len(chunk_list)} chunks "
          f"(avg {int(np.mean(lens))} chars, max {max(lens)}, min {min(lens)})")

    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break
        try:
            a = ask_chatbot(q, chunk_list, vecs)
            print(f"\nChatbot: {a}\n")
        except Exception as e:
            print(f"\n[Error] {e}\n")

if __name__ == "__main__":
    main()
