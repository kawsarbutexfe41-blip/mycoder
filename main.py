
import customtkinter as ctk
import json
import os
import psutil
import threading
import re
from datetime import datetime
import requests

# CONFIG PATHS
APP_DIR = os.path.join(os.getenv('APPDATA') or os.path.expanduser("~"), "MyCoder")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
PROJECTS_DIR = os.path.join(APP_DIR, "projects")
os.makedirs(PROJECTS_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except Exception: 
            return {}
    return {}

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)

# ---- UNIVERSAL API DETECTOR ----
def detect_provider(api_key):
    key = api_key.strip()
    if key.startswith("gsk_"):
        return "groq"
    elif key.startswith("sk-or-") or key.startswith("sk-or-v1-"):
        return "openrouter"
    elif key.startswith("sk-ant-"):
        return "anthropic"
    elif key.startswith("AIza"):
        return "gemini"
    elif key.startswith("sk-proj-") or key.startswith("sk-svc-") or key.startswith("sk-"):
        return "openai"
    else:
        # Default guess by length
        if len(key) > 30 and "AIza" not in key:
            return "openai"
        return "groq"

def get_api_info():
    cfg = load_config()
    key = cfg.get("groq_api_key") or cfg.get("api_key") or ""
    if not key:
        return None, None
    provider = cfg.get("provider") or detect_provider(key)
    return provider, key

# ---- UNIVERSAL CHAT FUNCTION ----
def universal_chat(provider, api_key, system_prompt, user_text):
    # GROQ
    if provider == "groq":
        from groq import Groq
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_text}]
        )
        return resp.choices[0].message.content

    # OPENAI
    elif provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_text}]
        )
        return resp.choices[0].message.content

    # OPENROUTER (OpenAI compatible)
    elif provider == "openrouter":
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        resp = client.chat.completions.create(
            model="meta-llama/llama-3.1-70b-instruct",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_text}]
        )
        return resp.choices[0].message.content

    # ANTHROPIC
    elif provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4000,
            system=system_prompt,
            messages=[{"role":"user","content":user_text}]
        )
        return resp.content[0].text

    # GEMINI
    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        full_prompt = f"{system_prompt}\n\nUser: {user_text}"
        resp = model.generate_content(full_prompt)
        return resp.text

    else:
        raise Exception(f"Unknown provider: {provider}")

# ---- API KEY WINDOW WITH AUTO DETECT ----
def ask_api_key_window():
    cfg = load_config()
    if cfg.get("api_key") or cfg.get("groq_api_key"):
        return cfg.get("api_key") or cfg.get("groq_api_key")

    root = ctk.CTk()
    root.geometry("560x460")
    root.title("MyCoder - Universal API Setup")

    ctk.CTkLabel(root, text="Welcome to MyCoder", font=("Segoe UI", 22, "bold")).pack(pady=(30,10))
    ctk.CTkLabel(root, text="Jekono API Key daw - Auto Detect hoye jabe!\nGroq / OpenAI / Gemini / Claude / OpenRouter", font=("Segoe UI", 12), text_color="#aaa", justify="center").pack(pady=10)

    entry = ctk.CTkEntry(root, width=460, height=45, placeholder_text="API Key paste koro (gsk_... / sk-... / AIza... / sk-or-...)")
    entry.pack(pady=15)

    # Provider label
    provider_label = ctk.CTkLabel(root, text="🔍 Key type: Auto-detect", font=("Consolas", 11), text_color="#4ade80")
    provider_label.pack()

    def on_key_change(event):
        k = entry.get().strip()
        if len(k) > 10:
            prov = detect_provider(k)
            emoji = {"groq":"⚡ Groq","openai":"🤖 OpenAI","gemini":"✨ Gemini","anthropic":"🧠 Claude","openrouter":"🌐 OpenRouter"}.get(prov, prov)
            provider_label.configure(text=f"🔍 Detected: {emoji}")

    entry.bind("<KeyRelease>", on_key_change)

    info_frame = ctk.CTkFrame(root, fg_color="#1e1e1e", corner_radius=8)
    info_frame.pack(pady=10, padx=20, fill="x")
    ctk.CTkLabel(info_frame, text="Free Keys:", font=("Segoe UI", 11, "bold"), text_color="#fff").pack(anchor="w", padx=10, pady=(8,2))
    ctk.CTkLabel(info_frame, text="• Groq: console.groq.com/keys (Free, Fast)\n• Gemini: aistudio.google.com/app/apikey (Free)\n• OpenRouter: openrouter.ai/keys (Free models)", font=("Segoe UI", 10), text_color="#888", justify="left").pack(anchor="w", padx=10, pady=(2,8))

    result = {"key": None}
    def save():
        k = entry.get().strip()
        if len(k) < 15:
            ctk.CTkLabel(root, text="⚠ Valid key daw!", text_color="red").pack()
            return
        prov = detect_provider(k)
        save_config({"api_key": k, "groq_api_key": k, "provider": prov})
        result["key"] = k
        root.destroy()

    ctk.CTkButton(root, text="Save & Start Coding", command=save, width=460, height=45, fg_color="#4ade80", hover_color="#22c55e", text_color="#111").pack(pady=15)

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
        header = ctk.CTkFrame(self, fg_color="#252526", corner_radius=12, height=40)
        header.pack(fill="x", padx=1, pady=1)
        ctk.CTkLabel(header, text=f"{filename} • {lang}", font=("Consolas", 12, "bold"), text_color="#ddd").pack(side="left", padx=12)
        copy_btn = ctk.CTkButton(header, text="📋 Copy", width=70, height=28, fg_color="#2a2a2a", hover_color="#3a3a3a", command=self.copy_code)
        copy_btn.pack(side="right", padx=5, pady=5)
        self.toggle_btn = ctk.CTkButton(header, text=f"▼ {len(self.lines)} lines", width=110, height=28, fg_color="#2a2a2a", command=self.toggle)
        self.toggle_btn.pack(side="right", padx=5, pady=5)
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
            self.toggle_btn.configure(text=f"▼ {len(self.lines)} lines")
        self.preview.configure(state="disabled")

    def copy_code(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.code_full)
            original_text = self.toggle_btn.cget("text")
            self.toggle_btn.configure(text="✅ Copied!")
            self.after(1500, lambda: self.toggle_btn.configure(text=original_text))
        except Exception:
            pass

class MyCoderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("1150x700")
        self.title("MyCoder - Universal API Edition")
        self.current_id = None
        self.projects = {}

        self.sidebar = ctk.CTkFrame(self, width=260, fg_color="#111113", corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkButton(self.sidebar, text="+ New chat", anchor="w", fg_color="transparent", hover_color="#2a2a2a", command=self.create_new_project).pack(fill="x", padx=10, pady=(15,2))
        self.search_entry = ctk.CTkEntry(self.sidebar, placeholder_text="🔍 Search", fg_color="#1e1e1e", border_width=0, height=36)
        self.search_entry.pack(fill="x", padx=10, pady=5)
        self.search_entry.bind("<KeyRelease>", self.filter_history)
        ctk.CTkLabel(self.sidebar, text="History", font=("Segoe UI", 11), text_color="#777", anchor="w").pack(fill="x", padx=15, pady=(15,5))
        self.history_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.history_frame.pack(fill="both", expand=True, padx=5)

        # Credit Footer
        self.credit_frame = ctk.CTkFrame(self.sidebar, fg_color="#0a0a0b", corner_radius=8, height=100)
        self.credit_frame.pack(side="bottom", fill="x", padx=10, pady=(5, 5))
        ctk.CTkButton(self.credit_frame, text="⚙ Settings - Change API", fg_color="transparent", hover_color="#2a2a2a", height=30, command=self.open_settings, anchor="w").pack(fill="x", padx=5, pady=(8, 0))
        prov, _ = get_api_info()
        prov_text = {"groq":"⚡ Groq","openai":"🤖 OpenAI","gemini":"✨ Gemini","anthropic":"🧠 Claude","openrouter":"🌐 OpenRouter"}.get(prov or "groq", prov or "Groq")
        self.provider_label_sidebar = ctk.CTkLabel(self.credit_frame, text=f"Active: {prov_text}", font=("Consolas", 10, "bold"), text_color="#4ade80")
        self.provider_label_sidebar.pack(pady=(2, 2))
        credit_label = ctk.CTkLabel(self.credit_frame, text="💻 Made by Masum Billah", font=("Segoe UI", 11, "bold"), text_color="#4ade80", cursor="hand2")
        credit_label.pack(pady=(2, 2))
        credit_label.bind("<Button-1>", lambda e: self.show_about_window())
        ctk.CTkLabel(self.credit_frame, text="Universal API • v2.0", font=("Segoe UI", 9), text_color="#666").pack(pady=(0, 8))

        self.main = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=0)
        self.main.pack(side="left", fill="both", expand=True)
        self.topbar = ctk.CTkFrame(self.main, height=50, fg_color="#111113", corner_radius=0)
        self.topbar.pack(fill="x")
        self.ram_label = ctk.CTkLabel(self.topbar, text="Live RAM: -- MB", font=("Consolas", 12, "bold"), text_color="#4ade80")
        self.ram_label.pack(side="left", padx=20)
        self.project_label = ctk.CTkLabel(self.topbar, text="", font=("Segoe UI", 13, "bold"))
        self.project_label.pack(side="left", padx=20)
        self.chat_frame = ctk.CTkScrollableFrame(self.main, fg_color="#18181b")
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.input_frame = ctk.CTkFrame(self.main, fg_color="#111113", height=70, corner_radius=0)
        self.input_frame.pack(fill="x", side="bottom")
        self.input_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Tomar project er kotha likho...", height=45, fg_color="#27272a", border_width=0)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=15, pady=15)
        self.input_entry.bind("<Return>", lambda e: self.send_message())
        ctk.CTkButton(self.input_frame, text="Send", width=100, height=45, command=self.send_message).pack(side="left", padx=(0,15))
        # Load projects AFTER UI is ready - FIX for history_frame bug
        self.projects = self.load_projects()
        if not self.projects:
            self.create_new_project()
        else:
            self.current_id = list(self.projects.keys())[0]
            self.refresh_history()
            self.load_current_project()
        
        # If create_new_project was called, it already set current_id and refreshed
        if self.current_id and not self.projects[self.current_id].get('name'):
            self.refresh_history()
            self.load_current_project()
            
        self.update_ram()

    def show_about_window(self):
        about = ctk.CTkToplevel(self)
        about.geometry("420x380")
        about.title("About - Universal API")
        about.grab_set()
        about.configure(fg_color="#111113")
        card = ctk.CTkFrame(about, fg_color="#1a1a1d", corner_radius=15)
        card.pack(pady=20, padx=20, fill="both", expand=True)
        avatar = ctk.CTkFrame(card, width=80, height=80, corner_radius=40, fg_color="#4ade80")
        avatar.pack(pady=(20, 10))
        ctk.CTkLabel(avatar, text="MB", font=("Segoe UI", 28, "bold"), text_color="#111113").place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text="Masum Billah", font=("Segoe UI", 22, "bold"), text_color="#fff").pack(pady=(10, 2))
        ctk.CTkLabel(card, text="Universal API Edition v2.0", font=("Segoe UI", 11, "bold"), text_color="#4ade80").pack()
        ctk.CTkLabel(card, text="Software Developer • Bangladesh 🇧🇩", font=("Segoe UI", 11), text_color="#aaa").pack()
        ctk.CTkFrame(card, height=1, fg_color="#333").pack(fill="x", padx=30, pady=15)
        ctk.CTkLabel(card, text="Supports: Groq • OpenAI • Gemini\nClaude • OpenRouter (Auto-Detect)", font=("Segoe UI", 10), text_color="#888", justify="center").pack(pady=5)
        ctk.CTkButton(about, text="Close", width=150, command=about.destroy, fg_color="#4ade80", hover_color="#22c55e", text_color="#111").pack(pady=10)

    def load_projects(self):
        projs = {}
        if os.path.exists(PROJECTS_DIR):
            for fname in os.listdir(PROJECTS_DIR):
                if fname.endswith(".json"):
                    try:
                        with open(os.path.join(PROJECTS_DIR, fname), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            projs[data["id"]] = data
                    except Exception: pass
        return projs

    def create_new_project(self):
        self.save_current()
        pid = datetime.now().strftime("%Y%m%d%H%M%S")
        data = {"id": pid, "name": f"Project {len(self.projects)+1}", "messages": [], "memory": {"goal": "", "last_code": ""}}
        with open(os.path.join(PROJECTS_DIR, f"{pid}.json"), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        self.projects[pid] = data
        self.current_id = pid
        self.refresh_history()
        self.load_current_project()

    def refresh_history(self):
        if not hasattr(self, 'history_frame'):
            return
        for w in self.history_frame.winfo_children(): w.destroy()
        query = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""
        for pid, p in reversed(list(self.projects.items())):
            if query and query not in p["name"].lower(): continue
            is_active = pid == self.current_id
            btn = ctk.CTkButton(self.history_frame, text=p["name"][:28], anchor="w", fg_color="#2a2a2a" if is_active else "transparent", hover_color="#2a2a2a", height=36, command=lambda _pid=pid: self.switch_project(_pid))
            btn.pack(fill="x", pady=2)

    def filter_history(self, e): self.refresh_history()
    def switch_project(self, pid):
        self.save_current()
        self.current_id = pid
        self.refresh_history()
        self.load_current_project()

    def load_current_project(self):
        if not hasattr(self, 'chat_frame'):
            return
        if not self.current_id:
            return
        for w in self.chat_frame.winfo_children(): w.destroy()
        proj = self.projects.get(self.current_id)
        if not proj: return
        self.project_label.configure(text=proj["name"])
        for msg in proj["messages"]:
            self.render_message(msg["role"], msg["content"])
        self.scroll_to_bottom()

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
            parts = re.split(r"```(\w*)\s*\n(.*?)```", content, flags=re.DOTALL)
            for i in range(0, len(parts), 3):
                txt = parts[i].strip()
                if txt:
                    ctk.CTkLabel(self.chat_frame, text=txt, wraplength=700, justify="left", anchor="w", text_color="#ddd").pack(fill="x", padx=15, pady=5)
                if i+1 < len(parts) and i+2 < len(parts):
                    lang = parts[i+1] or "Python"
                    code = parts[i+2]
                    ext = 'py' if lang.lower()=='python' else 'html' if 'html' in lang.lower() else 'js'
                    cb = CodeBlock(self.chat_frame, filename=f"main.{ext}", lang=lang.capitalize(), code=code)
                    cb.pack(fill="x", padx=10, pady=8)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        try:
            self.chat_frame._parent_canvas.yview_moveto(1.0)
        except Exception: pass

    def send_message(self):
        text = self.input_entry.get().strip()
        if not text: return
        self.input_entry.delete(0, "end")
        proj = self.projects[self.current_id]
        if len(proj["messages"]) == 0:
            proj["name"] = text[:30] + ("..." if len(text)>30 else "")
            self.project_label.configure(text=proj["name"])
        proj["messages"].append({"role": "user", "content": text})
        self.save_current()
        self.render_message("user", text)
        self.refresh_history()

        def ai_thread():
            try:
                provider, api_key = get_api_info()
                if not api_key:
                    self.after(0, lambda: self.render_message("assistant", "⚠ API Key pai ni. Settings theke check koro."))
                    return
                sys_prompt = f"You are an expert coder. Project Goal: {proj['memory'].get('goal','')} Last code: {proj['memory'].get('last_code','')[:1500]} RULE: Always remember previous project context. Provide full code with language tag like ```python. Write clean, production-ready code."
                if not proj["memory"].get("goal"):
                    proj["memory"]["goal"] = text
                ans = universal_chat(provider, api_key, sys_prompt, text)
                proj["messages"].append({"role":"assistant","content":ans})
                if "```" in ans:
                    proj["memory"]["last_code"] = ans
                self.after(0, lambda: self.render_message("assistant", ans))
                self.after(0, self.save_current)
            except Exception as e:
                self.after(0, lambda: self.render_message("assistant", f"❌ Error ({provider}): {str(e)}. API Key ba connection check koro."))

        threading.Thread(target=ai_thread, daemon=True).start()

    def open_settings(self):
        win = ctk.CTkToplevel(self)
        win.geometry("500x400")
        win.title("Settings - Universal API")
        win.grab_set()
        ctk.CTkLabel(win, text="Change API Key (Auto-Detect)", font=("Segoe UI", 18, "bold")).pack(pady=20)
        cfg = load_config()
        e = ctk.CTkEntry(win, width=440, height=45)
        e.insert(0, cfg.get("api_key") or cfg.get("groq_api_key",""))
        e.pack(pady=10)
        prov_label = ctk.CTkLabel(win, text="", text_color="#4ade80")
        prov_label.pack()
        def on_change(ev):
            k = e.get().strip()
            if k:
                prov_label.configure(text=f"Detected: {detect_provider(k)}")
        e.bind("<KeyRelease>", on_change)
        def save():
            k = e.get().strip()
            prov = detect_provider(k)
            save_config({"api_key": k, "groq_api_key": k, "provider": prov})
            win.destroy()
            self.provider_label_sidebar.configure(text=f"Active: {prov}")
            self.render_message("assistant",f"✅ API Changed to {prov}!")
        ctk.CTkButton(win, text="Save New Key", command=save, fg_color="#4ade80", text_color="#111").pack(pady=20)
        ctk.CTkLabel(win, text=f"Config: {CONFIG_PATH}", text_color="#666", font=("Consolas", 10)).pack()

    def update_ram(self):
        try:
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            self.ram_label.configure(text=f"● Live RAM: {mem:.1f} MB | CPU: {psutil.cpu_percent(interval=0.1)}%")
        except Exception: pass
        self.after(1000, self.update_ram)

if __name__ == "__main__":
    app = MyCoderApp()
    app.mainloop()
