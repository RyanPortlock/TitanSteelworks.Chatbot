# src/titansteelworks/gui.py
import os
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# Ensure project src directory is on sys.path (so `import titansteelworks` resolves)
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
# Ensure project root on sys.path (works when double-clicked)
# When installed under src/titansteelworks, go up two levels to reach repo root
if SRC_ROOT.exists():
    add_path = str(SRC_ROOT)
else:
    add_path = str(REPO_ROOT)
if add_path not in sys.path:
    sys.path.insert(0, add_path)

# Lightweight env/key helpers (do this BEFORE importing titansteelworks.main)
from dotenv import load_dotenv  # type: ignore

APP_ENV_DIR = Path(os.getenv("APPDATA") or Path.home() / "AppData/Roaming") / "TitanSteelworks"
APP_ENV_PATH = APP_ENV_DIR / ".env"

def _load_saved_env() -> None:
    """Load repo .env (dev) and then user-level .env (persisted)."""
    try:
        load_dotenv()  # repo .env if present (dev only; not in the shipped exe)
    except Exception:
        pass
    if APP_ENV_PATH.exists():
        try:
            load_dotenv(APP_ENV_PATH)
        except Exception:
            pass

def ensure_api_key_or_demo() -> None:
    """
    If there's no OPENAI_API_KEY, offer Demo Mode or key entry.
    In Demo Mode we do nothing (titansteelworks.main will detect missing key and switch to canned answers).
    """
    _load_saved_env()
    if os.getenv("OPENAI_API_KEY"):
        return  # already set → live AI mode

    # No key found: ask user
    from tkinter import simpledialog
    use_demo = messagebox.askyesno(
        "Run in Demo Mode?",
        "No OpenAI API key found.\n\n"
        "Click 'Yes' to run in Demo Mode (canned answers only),\n"
        "or click 'No' to enter your own API key for live AI."
    )
    if use_demo:
        # Stay keyless; titansteelworks.main will run in Demo Mode automatically
        return

    # Loop: let the user retry entry until key validates or they cancel.
    from tkinter import simpledialog
    while True:
        key = simpledialog.askstring("OpenAI API Key", "Paste your OpenAI API key:", show="*")
        if not key:
            messagebox.showinfo("Demo Mode", "Continuing in Demo Mode without a key.")
            return

        try:
            APP_ENV_DIR.mkdir(parents=True, exist_ok=True)
            APP_ENV_PATH.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
            # Ensure the running process sees the key immediately
            os.environ["OPENAI_API_KEY"] = key
            load_dotenv(APP_ENV_PATH)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save API key:\n{e}")
            return

        # Validate the key by loading titansteelworks.main and making a tiny test call.
        try:
            import importlib
            import titansteelworks.main as _main
            importlib.reload(_main)
            if getattr(_main, "DEMO_MODE", True):
                raise RuntimeError("Key not recognized by application; still in Demo Mode.")

            # Try a lightweight embeddings request to validate credentials.
            try:
                _main.client.embeddings.create(model=_main.EMBED_MODEL, input=["test"])
            except Exception as api_err:
                raise api_err

            # If we reach here the key looks valid — proceed
            messagebox.showinfo("API Key Valid", "OpenAI API key validated. Launching Live AI mode.")
            return
        except Exception as err:
            # Ask the user if they'd like to retry entry or continue in Demo Mode.
            try_again = messagebox.askretrycancel(
                "Invalid API Key",
                f"Could not validate API key:\n{err}\n\nRetry entering your API key?"
            )
            if not try_again:
                # Remove the env key and continue in demo mode
                os.environ.pop("OPENAI_API_KEY", None)
                messagebox.showinfo("Demo Mode", "Continuing in Demo Mode without a key.")
                return
            # Otherwise loop and prompt again


# Globals filled after importing titansteelworks.main lazily (post key/demo choice)
MAIN = None  # will hold the imported titansteelworks.main module
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
            global CHUNKS, VECS, MAIN
            reply = MAIN.ask_chatbot(msg, CHUNKS, VECS)  # type: ignore[attr-defined]
        except Exception as e:
            # Detect invalid API key errors and offer an in-app retry flow.
            err_str = str(e)
            reply = None
            if any(k in err_str.lower() for k in ("invalid_api_key", "incorrect api key", "401")):
                # Use an event to run dialogs on the main thread and wait for the user's input.
                import importlib
                from tkinter import simpledialog
                done = threading.Event()
                result: dict = {"reply": None}

                def ui_retry_flow():
                    ask_retry = messagebox.askyesno(
                        "Invalid API key",
                        "The saved OpenAI API key looks invalid or was rejected by the service.\n\n"
                        "Click Yes to re-enter your API key now, or No to continue in Demo Mode."
                    )
                    if not ask_retry:
                        # Switch to demo mode by removing the env key and reloading main
                        os.environ.pop("OPENAI_API_KEY", None)
                        try:
                            importlib.reload(MAIN)
                        except Exception:
                            pass
                        result["reply"] = "[Error] Invalid API key. Running in Demo Mode."
                        done.set()
                        return

                    key = simpledialog.askstring("OpenAI API Key", "Paste your OpenAI API key:", show="*")
                    if not key:
                        result["reply"] = "[Error] No API key entered. Continuing in Demo Mode."
                        done.set()
                        return

                    try:
                        APP_ENV_DIR.mkdir(parents=True, exist_ok=True)
                        APP_ENV_PATH.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
                        os.environ["OPENAI_API_KEY"] = key
                        # Reload titansteelworks.main so module-level DEMO_MODE and client reinitialize
                        try:
                            importlib.reload(MAIN)
                        except Exception as reload_err:
                            result["reply"] = f"[Error] Could not reload app after saving key: {reload_err}"
                            done.set()
                            return

                        # Try the request again
                        try:
                            result["reply"] = MAIN.ask_chatbot(msg, CHUNKS, VECS)  # type: ignore[attr-defined]
                        except Exception as second_err:
                            result["reply"] = f"[Error] {second_err}"
                    except Exception as save_err:
                        result["reply"] = f"[Error] Could not save API key: {save_err}"
                    finally:
                        done.set()

                # Schedule the UI flow on the main thread and wait for completion (worker thread waits).
                output.after(0, ui_retry_flow)
                done.wait(120)
                reply = result.get("reply") or f"[Error] {e}"
            else:
                reply = f"[Error] {e}"

        def done():
            append_text(output, f"Chatbot: {reply}", "bot")
            send_btn.config(state="normal")
            status.config(text="Ready")

        output.after(0, done)

    threading.Thread(target=worker, daemon=True).start()


def build_ui(show_demo_banner: bool):
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
    def _enter_api_key():
        from tkinter import simpledialog
        key = simpledialog.askstring("OpenAI API Key", "Paste your OpenAI API key:", show="*")
        if not key:
            return
        try:
            APP_ENV_DIR.mkdir(parents=True, exist_ok=True)
            APP_ENV_PATH.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
            # Also set in-process so tools that re-check env can see it without restart.
            os.environ["OPENAI_API_KEY"] = key
            messagebox.showinfo(
                "Saved",
                "API key saved. Please restart the app to switch from Demo Mode to Live AI."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not save API key:\n{e}")

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
    help_menu.add_separator()
    help_menu.add_command(label="Enter/OpenAI API Key…", command=_enter_api_key)
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

    # Demo Mode banner
    if show_demo_banner:
        append_text(
            output,
            "System: Running in DEMO MODE (canned answers). Use Help → “Enter/OpenAI API Key…” to switch to Live AI.",
            "sys",
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
            global CHUNKS, VECS, MAIN
            # Import titansteelworks.main lazily here (after key/demo choice), then build index
            if MAIN is None:
                import titansteelworks.main as _main
                MAIN = _main

            text = MAIN.load_docs_text()  # type: ignore[attr-defined]
            chunks = MAIN.chunk_text(text, MAIN.CHUNK_SIZE, MAIN.CHUNK_OVERLAP)  # type: ignore[attr-defined]
            chunk_list, vecs = MAIN.build_index(chunks)  # type: ignore[attr-defined]
        except Exception as e:
            err_txt = str(e)
            def show_err(exc=err_txt):
                messagebox.showerror("Startup Error", exc)
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
    # Offer key import or continue in Demo Mode BEFORE importing titansteelworks.main
    ensure_api_key_or_demo()

    # Now import titansteelworks.main so it can detect DEMO_MODE correctly
    global MAIN
    if MAIN is None:
        import titansteelworks.main as _main
        MAIN = _main

    win, output, status, ready_cb = build_ui(show_demo_banner=bool(getattr(MAIN, "DEMO_MODE", False)))
    status.config(text="Loading documents… (building index)")
    init_index_async(status, ready_cb)
    win.mainloop()


if __name__ == "__main__":
    main()
