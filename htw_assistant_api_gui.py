#!/usr/bin/env python3
"""
HTW Berlin Student Services Assistant - API-Backed GUI
Connects to the running HANS HTTP API (/health, /ask)
"""

import os
import json
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import requests  # pip install requests

# ---- CONFIG ----
# For HTW Server deployment: Set the actual server hostname/IP
# Example: export HANS_API_BASE="http://hans-server.htw-berlin.de:8080"
# or:      export HANS_API_BASE="http://10.x.x.x:8080"
API_BASE = os.getenv("HANS_API_BASE", "http://127.0.0.1:8080")  # set to your server URL if needed
HEALTH_URL = f"{API_BASE}/health"
ASK_URL = f"{API_BASE}/ask"
TIMEOUT = float(os.getenv("HANS_API_TIMEOUT", "30"))  # seconds

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hans_gui")

class HTWAssistantAPIGUI:
    """HTTP API-backed GUI for HTW Student Services Assistant"""
    def __init__(self, root):
        self.root = root
        self.root.title("HTW Berlin Assistant (API Version)")
        self.root.geometry("1000x700")

        self.processing = False
        self.last_response_metadata = None

        self.setup_gui()
        self.check_api_status()

    # -------- UI wiring (unchanged structure) --------
    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        title_label = ttk.Label(main_frame, text="HTW Berlin Student Services Assistant",
                                font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))

        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(self.status_frame, text="API Status:").grid(row=0, column=0, sticky=tk.W)
        self.status_var = tk.StringVar(value="Checking API connectivity…")
        self.status_label = ttk.Label(self.status_frame, textvariable=self.status_var, foreground="orange")
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

        self.test_button = ttk.Button(self.status_frame, text="Test API", command=self.test_api, state='disabled')
        self.test_button.grid(row=0, column=2, padx=(10, 0))

        input_frame = ttk.LabelFrame(main_frame, text="Ask a Question", padding="10")
        input_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)

        self.input_text = scrolledtext.ScrolledText(input_frame, height=4, wrap=tk.WORD)
        self.input_text.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        button_frame = ttk.Frame(input_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W)

        self.process_button = ttk.Button(button_frame, text="Generate Response",
                                         command=self.process_query_async, state='disabled')
        self.process_button.grid(row=0, column=0, padx=(0, 10))

        self.clear_button = ttk.Button(button_frame, text="Clear", command=self.clear_input)
        self.clear_button.grid(row=0, column=1)

        response_frame = ttk.LabelFrame(main_frame, text="Response", padding="10")
        response_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        response_frame.columnconfigure(0, weight=1)
        response_frame.rowconfigure(0, weight=1)

        self.response_text = scrolledtext.ScrolledText(response_frame, height=15, wrap=tk.WORD, state='disabled')
        self.response_text.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        metadata_frame = ttk.Frame(response_frame)
        metadata_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.metadata_button = ttk.Button(metadata_frame, text="Show Details",
                                          command=self.show_metadata, state='disabled')
        self.metadata_button.grid(row=0, column=0, padx=(0, 10))

        self.copy_button = ttk.Button(metadata_frame, text="Copy Response",
                                      command=self.copy_response, state='disabled')
        self.copy_button.grid(row=0, column=1)

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5))

    # -------- API checks --------
    def check_api_status(self):
        def check():
            try:
                r = requests.get(HEALTH_URL, timeout=TIMEOUT)
                r.raise_for_status()
                self.root.after(0, self.update_api_status, True, "API online")
            except Exception as e:
                self.root.after(0, self.update_api_status, False, f"{e}")

        threading.Thread(target=check, daemon=True).start()

    def update_api_status(self, ok: bool, message: str):
        if ok:
            self.status_var.set(f"✅ {message} ({API_BASE})")
            self.status_label.configure(foreground="green")
            self.process_button.configure(state='normal')
            self.test_button.configure(state='normal')
        else:
            self.status_var.set(f"❌ {message}")
            self.status_label.configure(foreground="red")
            self.process_button.configure(state='disabled')
            self.test_button.configure(state='normal')
            self.show_api_error(message)

    def show_api_error(self, message: str):
        # Detect if trying to connect to localhost
        is_localhost = API_BASE in ["http://127.0.0.1:8080", "http://localhost:8080"]

        if is_localhost:
            error_msg = f"""API Error: {message}

Cannot connect to HANS API at {API_BASE}

🔧 Solution: Set up SSH tunnel to the HTW server

Since the HANS API runs on a remote server bound to localhost,
you need to create an SSH tunnel first:

Mac/Linux:
  1. Open Terminal
  2. Run: ./connect_to_hans.sh
  3. Keep that terminal open
  4. Restart this GUI in a new terminal

Windows:
  1. Edit connect_to_hans.bat with your server details
  2. Run connect_to_hans.bat
  3. Keep that window open
  4. Restart this GUI in a new Command Prompt

Or manually:
  ssh -L 8080:127.0.0.1:8080 user@htw-server.de -N

Then restart this GUI.
"""
        else:
            error_msg = f"""API Error: {message}

This app expects a running HANS API at:
  {API_BASE}

Troubleshooting:
1) Confirm the API process is running on the server
2) Verify network connectivity to the server
3) Check if you need an SSH tunnel (if server binds to 127.0.0.1)
4) Verify firewall/proxy settings allow the connection

For SSH tunnel setup, see connect_to_hans.sh or connect_to_hans.bat
"""

        messagebox.showerror("API Connection Required", error_msg)

    def test_api(self):
        self.status_var.set("Testing API…")
        self.progress.start()

        def run():
            try:
                r = requests.get(HEALTH_URL, timeout=TIMEOUT)
                r.raise_for_status()
                self.root.after(0, self.update_api_status, True, "API online")
            except Exception as e:
                self.root.after(0, self.update_api_status, False, str(e))
            finally:
                self.root.after(0, self.progress.stop)

        threading.Thread(target=run, daemon=True).start()

    # -------- Ask flow --------
    def process_query_async(self):
        query = self.input_text.get("1.0", tk.END).strip()
        if not query:
            messagebox.showwarning("Input Required", "Please enter a question.")
            return
        if self.processing:
            return

        self.processing = True
        self.process_button.configure(state='disabled', text="Processing…")
        self.progress.start()

        # clear previous response
        self.response_text.configure(state='normal')
        self.response_text.delete("1.0", tk.END)
        self.response_text.configure(state='disabled')
        self.last_response_metadata = None
        self.metadata_button.configure(state='disabled')
        self.copy_button.configure(state='disabled')

        threading.Thread(target=self.process_query_thread, args=(query,), daemon=True).start()

    def process_query_thread(self, query: str):
        try:
            t0 = time.time()
            r = requests.post(ASK_URL, json={"q": query}, timeout=TIMEOUT)
            t1 = time.time()
            latency_ms = int((t1 - t0) * 1000)

            r.raise_for_status()
            data = r.json()
            # Your API returns: answer, sources, confidence_pct, metadata (nullable)
            answer = data.get("answer") or data.get("error") or "No answer."
            meta = {
                "latency_ms": latency_ms,
                "confidence_pct": data.get("confidence_pct"),
                "sources": data.get("sources", []),
                "raw": data
            }
            self.root.after(0, self.display_response, {"final_response": answer, "metadata": meta}, None)
        except Exception as e:
            self.root.after(0, self.display_response, None, f"Error processing query: {e}")
        finally:
            self.root.after(0, self.reset_processing_state)

    # -------- UI helpers --------
    def display_response(self, result: dict = None, error: str = None):
        self.response_text.configure(state='normal')
        if error:
            self.response_text.insert(tk.END, f"{error}")
        elif result:
            resp = result.get("final_response", "No response generated.")
            self.response_text.insert(tk.END, resp)
            self.last_response_metadata = result.get("metadata", {})
            self.metadata_button.configure(state='normal')
            self.copy_button.configure(state='normal')
            logger.info("Query processed: %s chars; %.1f ms",
                        len(resp), float(self.last_response_metadata.get("latency_ms", 0)))
        self.response_text.configure(state='disabled')

    def reset_processing_state(self):
        self.processing = False
        self.process_button.configure(state='normal', text="Generate Response")
        self.progress.stop()

    def show_metadata(self):
        if not self.last_response_metadata:
            return
        w = tk.Toplevel(self.root)
        w.title("Response Details")
        w.geometry("700x500")
        txt = scrolledtext.ScrolledText(w, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt.insert(tk.END, json.dumps(self.last_response_metadata, indent=2, default=str))
        txt.configure(state='disabled')

    def clear_input(self):
        self.input_text.delete("1.0", tk.END)

    def copy_response(self):
        response = self.response_text.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(response)
        messagebox.showinfo("Copied", "Response copied to clipboard!")

    def on_closing(self):
        self.root.destroy()

def main():
    root = tk.Tk()
    app = HTWAssistantAPIGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
