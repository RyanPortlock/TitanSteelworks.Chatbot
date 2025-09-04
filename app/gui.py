# app/gui.py
import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# --- Ensure project root on sys.path (works when double-clicked) ---
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Import pipeline from app.main ---
try:
    from app.main import (
        load_docs_text,
        chunk_text,
        build_index,
        ask_chatbot,
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
except Exception as e:
    messagebox.showerror("Import Error", f"Could not import from app.main:\n{e}")
    raise

# Globals for retrieval index
CHUNKS = None
VECS = None


# ----------------- UI helpers -----------------
def append_text(widget: tk.Text, text: str, tag: str | None = None) -> None:
    widget.configure(state="normal")
    widget.insert("end", (text + "\n"), (tag,) if tag else ())
    widget.see("end")
    widget.configure(state="disabled")


def on_send(entry: ttk.Entry, output: tk.Text, send_btn: ttk.Button, status: ttk.Label) -> None:
    msg = entry.get().strip()
    if not msg:
        return

    entry.delete(0, "end")
    append_text(output, f"You: {msg}", "user")
    send_btn.config(state="disabled")
    status.config(text="Thinking…")

    def worker():
        try:
            global CHUNKS, VECS
            reply = ask_chatbot(msg, CHUNKS, VECS)
        except Exception as e:
            reply = f"[Error] {e}"

        def done():
            append_text(output, f"Chatbot: {reply}", "bot")
            send_btn.config(state="normal")
            status.config(text="Ready")

        output.after(0, done)

    threading.Thread(target=worker, daemon=True).start()


def build_ui():
    win = tk.Tk()
    win.title("Titan Steelworks Chatbot")
    win.geometry("840x580")
    win.minsize(720, 480)

    # Native theme where available
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass

    # --- Top bar ---
    top = ttk.Frame(win, padding=(10, 10, 10, 0))
    top.pack(fill="x")
    ttk.Label(top, text="Titan Steelworks AI Assistant", font=("Segoe UI", 14, "bold")).pack(side="left")
    status = ttk.Label(top, text="Loading…", foreground="#666")
    status.pack(side="right")

    # --- Transcript area ---
    mid = ttk.Frame(win, padding=(10, 10))
    mid.pack(fill="both", expand=True)

    output = tk.Text(
        mid,
        wrap="word",
        state="disabled",
        font=("Segoe UI", 10),
        padx=6,
        pady=6,
    )
    vscroll = ttk.Scrollbar(mid, command=output.yview)
    output.configure(yscrollcommand=vscroll.set)

    output.grid(row=0, column=0, sticky="nsew")
    vscroll.grid(row=0, column=1, sticky="ns")
    mid.rowconfigure(0, weight=1)
    mid.columnconfigure(0, weight=1)

    # Tag styles
    output.tag_configure("user", foreground="#1f6feb")
    output.tag_configure("bot", foreground="#0a0a0a")
    output.tag_configure("sys", foreground="#6e7781", font=("Segoe UI", 9, "italic"))

    # --- Input row ---
    bottom = ttk.Frame(win, padding=(10, 0, 10, 10))
    bottom.pack(fill="x")

    entry = ttk.Entry(bottom)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

    send_btn = ttk.Button(
        bottom,
        text="Send",
        command=lambda: on_send(entry, output, send_btn, status),
        state="disabled",
    )
    send_btn.pack(side="right")

    # --- Menu ---
    menubar = tk.Menu(win)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Exit", command=win.destroy)
    menubar.add_cascade(label="File", menu=file_menu)

    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(
        label="About",
        command=lambda: messagebox.showinfo(
            "About",
            "Titan Steelworks AI Assistant\nDesktop interface (Tkinter) for the docs-grounded chatbot.",
        ),
    )
    menubar.add_cascade(label="Help", menu=help_menu)
    win.config(menu=menubar)

    # Enter to send
    def _enter(evt):
        on_send(entry, output, send_btn, status)
        return "break"

    entry.bind("<Return>", _enter)

    # Friendly greeting
    append_text(
        output,
        "Chatbot: Good day, and welcome to Titan Steelworks’ AI Assistant—how may I help you today?",
        "bot",
    )

    # Enable controls once index is ready
    def enable_ready():
        status.config(text="Ready")
        send_btn.config(state="normal")
        entry.focus_set()

    return win, output, status, enable_ready


def init_index_async(status_label: ttk.Label, ready_cb) -> None:
    """Build embeddings index off the UI thread."""
    def worker():
        try:
            text = load_docs_text()
            chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            chunk_list, vecs = build_index(chunks)
        except Exception as e:
            def show_err():
                messagebox.showerror("Startup Error", str(e))
                status_label.config(text="Error")
            status_label.after(0, show_err)
            return

        def set_globals():
            global CHUNKS, VECS
            CHUNKS, VECS = chunk_list, vecs
            ready_cb()

        status_label.after(0, set_globals)

    threading.Thread(target=worker, daemon=True).start()


# ----------------- Entrypoint -----------------
def main() -> None:
    # Require API key (env or .env via main.py’s loader)
    if not os.getenv("OPENAI_API_KEY"):
        messagebox.showerror("Missing API Key", "OPENAI_API_KEY not found in environment/.env")
        return

    win, output, status, ready_cb = build_ui()
    status.config(text="Loading documents… (building index)")
    init_index_async(status, ready_cb)
    win.mainloop()


if __name__ == "__main__":
    main()
