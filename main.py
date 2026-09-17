
import customtkinter as ctk
import json
import os
import psutil
import threading
import time
from groq import Groq
import re
from datetime import datetime

# CONFIG PATHS
APP_DIR = os.path.join(os.getenv('APPDATA') or ".", "MyCoder")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
PROJECTS_DIR = os.path.join(APP_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f: return json.load(f)
        except: return {}
    return {}

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)

def get_client():
    cfg = load_config()
    key = cfg.get("groq_api_key")
    if not key: return None
    return Groq(api_key=key)

# ---- API KEY WINDOW ----
def ask_api_key_window():
    cfg = load_config()
    if cfg.get("groq_api_key"):
        return cfg.get("groq_api_key")

    root = ctk.CTk()
    root.geometry("500x350")
    root.title("MyCoder - API Key Setup")
    
    ctk.CTkLabel(root, text="Welcome to MyCoder", font=("Segoe UI", 22, "bold")).pack(pady=(40,10))
    ctk.CTkLabel(root, text="Groq Free API Key daw. Eta tomar PC te save thakbe,\ncode er vitor thakbe na.", font=("Segoe UI", 12), text_color="#aaa").pack(pady=10)
    
    entry = ctk.CTkEntry(root, width=400, height=45, placeholder_text="gsk_... diye suru key ta paste koro", show="")
    entry.pack(pady=20)
    
    info = ctk.CTkLabel(root, text="Key paba: console.groq.com/keys", text_color="#5aa9ff", cursor="hand2")
    info.pack()

    result = {"key": None}
    def save():
        k = entry.get().strip()
        if len(k) < 20:
            ctk.CTkLabel(root, text="Valid key daw!").pack()
            return
        save_config({"groq_api_key": k})
        result["key"] = k
        root.destroy()

    ctk.CTkButton(root, text="Save & Start Coding", command=save, width=400, height=45).pack(pady=20)
    ctk.CTkLabel(root, text="Made with ❤ by Masum Billah", font=("Segoe UI", 10, "italic"), text_color="#666").pack(side="bottom", pady=10)
    root.mainloop()
    return result["key"]

API_KEY = ask_api_key_window()
if not API_KEY:
    exit()

# ---- MAIN APP ----
class CodeBlock(ctk.CTkFrame):
    def __init__(self, master, filename, lang, code):
        super().__init__(master, fg_color="#1e1e1e", border_width=1, border_color="#2a2a2a", corner_radius=12)
        self.code_full = code
        self.is_expanded = False
        self.lines = code.split("\n")
        
        # Header
        header = ctk.CTkFrame(self, fg_color="#252526", corner_radius=12, height=40)
        header.pack(fill="x", padx=1, pady=1)
        
        ctk.CTkLabel(header, text=f"{filename} - {lang}", font=("Consolas", 12, "bold"), text_color="#ddd").pack(side="left", padx=12)
        ctk.CTkLabel(header, text=lang, fg_color="#333", corner_radius=6, padx=8, font=("Consolas", 10)).pack(side="left", padx=5)
        
        self.toggle_btn = ctk.CTkButton(header, text=f"▼ {len(self.lines)} lines hidden", width=140, height=28, fg_color="#2a2a2a", command=self.toggle)
        self.toggle_btn.pack(side="right", padx=10, pady=5)

        # Code preview (collapsed)
        self.preview = ctk.CTkTextbox(self, height=70, fg_color="#1e1e1e", font=("Consolas", 12), text_color="#9cdcfe")
        self.preview.pack(fill="x", padx=10, pady=(0,10))
        preview_text = "\n".join(self.lines[:3])
        self.preview.insert("1.0", preview_text + "\n# ...")
        self.preview.configure(state="disabled")

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if self.is_expanded:
            self.preview.insert("1.0", self.code_full)
            self.preview.configure(height=min(400, len(self.lines)*18 + 20))
            self.toggle_btn.configure(text="▲ Hide")
        else:
            self.preview.insert("1.0", "\n".join(self.lines[:3]) + "\n# ...")
            self.preview.configure(height=70)
            self.toggle_btn.configure(text=f"▼ {len(self.lines)} lines hidden")
        self.preview.configure(state="disabled")

class MyCoderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("1150x700")
        self.title("MyCoder - 100MB Edition")
        
        # Projects state
        self.projects = self.load_projects()
        if not self.projects:
            self.create_new_project()
        self.current_id = list(self.projects.keys())[0]

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=260, fg_color="#111113", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkButton(self.sidebar, text="+ New chat   Ctrl+Shift+O", anchor="w", fg_color="transparent", hover_color="#2a2a2a", command=self.create_new_project).pack(fill="x", padx=10, pady=(15,2))
        
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="🔍 Search Ctrl+K", fg_color="#1e1e1e", border_width=0, height=36)
        self.search_entry.pack(fill="x", padx=10, pady=5)
        self.search_entry.bind("<KeyRelease>", self.filter_history)

        ctk.CTkLabel(self.sidebar, text="History", font=("Segoe UI", 11), text_color="#777", anchor="w").pack(fill="x", padx=15, pady=(15,5))
        
        self.history_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.history_frame.pack(fill="both", expand=True, padx=5)

        # Settings bottom
        ctk.CTkButton(self.sidebar, text="⚙ Settings - API Key Change", fg_color="transparent", hover_color="#2a2a2a", height=36, command=self.open_settings).pack(side="bottom", fill="x", padx=10, pady=10)

        # Main
        self.main = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=0)
        self.main.pack(side="left", fill="both", expand=True)

        # Top bar with RAM
        self.topbar = ctk.CTkFrame(self.main, height=50, fg_color="#111113", corner_radius=0)
        self.topbar.pack(fill="x")
        self.ram_label = ctk.CTkLabel(self.topbar, text="Live RAM: -- MB", font=("Consolas", 12, "bold"), text_color="#4ade80")
        self.ram_label.pack(side="left", padx=20)
        self.project_label = ctk.CTkLabel(self.topbar, text="", font=("Segoe UI", 13, "bold"))
        self.project_label.pack(side="left", padx=20)
        
        # Chat
        self.chat_frame = ctk.CTkScrollableFrame(self.main, fg_color="#18181b")
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Input
        self.input_frame = ctk.CTkFrame(self.main, fg_color="#111113", height=70, corner_radius=0)
        self.input_frame.pack(fill="x", side="bottom")
        self.input_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Tomar project er kotha likho...", height=45, fg_color="#27272a", border_width=0)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=15, pady=15)
        self.input_entry.bind("<Return>", lambda e: self.send_message())
        ctk.CTkButton(self.input_frame, text="Send", width=100, height=45, command=self.send_message).pack(side="left", padx=(0,15))

        self.refresh_history()
        self.load_current_project()
        self.update_ram()

    def load_projects(self):
        projs = {}
        for fname in os.listdir(PROJECTS_DIR):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(PROJECTS_DIR, fname), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        projs[data["id"]] = data
                except: pass
        return projs

    def create_new_project(self):
        pid = datetime.now().strftime("%Y%m%d%H%M%S")
        data = {"id": pid, "name": f"Project {len(self.projects)+1}", "messages": [], "memory": {"goal": "", "last_code": ""}}
        with open(os.path.join(PROJECTS_DIR, f"{pid}.json"), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        self.projects[pid] = data
        self.current_id = pid
        self.refresh_history()
        self.load_current_project()

    def refresh_history(self):
        for w in self.history_frame.winfo_children(): w.destroy()
        query = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""
        for pid, p in reversed(list(self.projects.items())):
            if query and query not in p["name"].lower(): continue
            is_active = pid == self.current_id
            btn = ctk.CTkButton(self.history_frame, text=p["name"][:28], anchor="w", 
                               fg_color="#2a2a2a" if is_active else "transparent",
                               hover_color="#2a2a2a", height=36,
                               command=lambda _pid=pid: self.switch_project(_pid))
            btn.pack(fill="x", pady=2)

    def filter_history(self, e): self.refresh_history()

    def switch_project(self, pid):
        self.save_current()
        self.current_id = pid
        self.refresh_history()
        self.load_current_project()

    def load_current_project(self):
        for w in self.chat_frame.winfo_children(): w.destroy()
        proj = self.projects.get(self.current_id)
        if not proj: return
        self.project_label.configure(text=proj["name"])
        for msg in proj["messages"]:
            self.render_message(msg["role"], msg["content"])

    def save_current(self):
        if not self.current_id: return
        path = os.path.join(PROJECTS_DIR, f"{self.current_id}.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.projects[self.current_id], f, indent=2, ensure_ascii=False)

    def render_message(self, role, content):
        if role == "user":
            bubble = ctk.CTkFrame(self.chat_frame, fg_color="#2a2a2a", corner_radius=12)
            bubble.pack(fill="x", pady=5, padx=10, anchor="e")
            ctk.CTkLabel(bubble, text=content, wraplength=600, justify="left", anchor="w").pack(padx=12, pady=8)
        else:
            # Parse code blocks
            parts = re.split(r"```(\w+)?\n(.*?)```", content, flags=re.DOTALL)
            # parts: text, lang, code, text, lang, code...
            for i in range(0, len(parts), 3):
                txt = parts[i].strip()
                if txt:
                    ctk.CTkLabel(self.chat_frame, text=txt, wraplength=700, justify="left", anchor="w", text_color="#ddd").pack(fill="x", padx=15, pady=5)
                if i+1 < len(parts) and i+2 < len(parts):
                    lang = parts[i+1] or "Python"
                    code = parts[i+2]
                    cb = CodeBlock(self.chat_frame, filename=f"main.{ 'py' if lang.lower()=='python' else 'html' if 'html' in lang.lower() else 'js'}", lang=lang.capitalize(), code=code)
                    cb.pack(fill="x", padx=10, pady=8)

    def send_message(self):
        text = self.input_entry.get().strip()
        if not text: return
        self.input_entry.delete(0, "end")
        
        proj = self.projects[self.current_id]
        if len(proj["messages"]) == 0:
            proj["name"] = text[:30]
        proj["messages"].append({"role": "user", "content": text})
        self.render_message("user", text)
        self.refresh_history()

        def ai_thread():
            try:
                client = get_client()
                sys_prompt = f"""You are expert coder. Project Goal: {proj['memory'].get('goal','')} Last code: {proj['memory'].get('last_code','')[:1500]} 
                RULE: Always remember previous project context. Provide full code with language tag like ```python. Write clean code."""
                if not proj["memory"].get("goal"):
                    proj["memory"]["goal"] = text

                resp = client.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role":"system","content":sys_prompt},{"role":"user","content":text}]
                )
                ans = resp.choices[0].message.content
                proj["messages"].append({"role":"assistant","content":ans})
                if "```" in ans:
                    proj["memory"]["last_code"] = ans
                self.after(0, lambda: self.render_message("assistant", ans))
                self.after(0, self.save_current)
            except Exception as e:
                self.after(0, lambda: self.render_message("assistant", f"Error: {e}. API Key check koro Settings theke."))

        threading.Thread(target=ai_thread, daemon=True).start()

    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.geometry("450x300")
        win.title("Settings")
        ctk.CTkLabel(win, text="API Key Change", font=("Segoe UI", 18, "bold")).pack(pady=20)
        cfg = load_config()
        e = ctk.CTkEntry(win, width=400, height=45)
        e.insert(0, cfg.get("groq_api_key",""))
        e.pack(pady=10)
        def save():
            save_config({"groq_api_key": e.get().strip()})
            win.destroy()
            self.render_message("assistant","API Key update kora hoyeche! ✅")
        ctk.CTkButton(win, text="Save New Key", command=save).pack(pady=20)
        ctk.CTkLabel(win, text="Key save hobe: %APPDATA%\\MyCoder\\config.json", text_color="#666", font=("Consolas", 10)).pack()

    def update_ram(self):
        mem = psutil.Process().memory_info().rss / 1024 / 1024
        self.ram_label.configure(text=f"● Live RAM: {mem:.1f} MB / 4GB  |  {psutil.cpu_percent()}% CPU")
        self.after(1000, self.update_ram)

if __name__ == "__main__":
    app = MyCoderApp()
    app.mainloop()
