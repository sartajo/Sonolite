"""
SonoLite GUI – Ultrasound Scan Controller Interface

This application provides a graphical interface to control the full ultrasound
scanning pipeline, including signal generation, servo-based scanning, and image
reconstruction. It launches the scan controller, streams real-time terminal output,
and automatically displays the reconstructed B-mode images upon completion.

Features:
- One-click signal generator initialization and scan start
- Live terminal output for debugging and monitoring
- Automatic loading and visualization of reconstructed images
- Dark-themed interface optimized for readability and usability

Authored by Omar Sartaj
"""

import os
import glob
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except Exception:
    PIL_OK = False


BG = "#181a1b"
PANEL = "#232629"
PANEL_2 = "#2b2f33"
TEXT = "#f2f2f2"
MUTED = "#b8bec5"
ACCENT = "#4da3ff"
ACCENT_2 = "#2d7dd2"
BORDER = "#3a3f44"
TERM_BG = "#0f1113"
TERM_FG = "#e8e8e8"


class ScanControllerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SonoLite Scan Controller")
        self.root.geometry("1500x900")
        self.root.minsize(1250, 760)
        self.root.configure(bg=BG)

        self.process = None
        self.output_queue = queue.Queue()
        self.current_folder = None

        self.build_style()
        self.build_ui()
        self.poll_output()

    def build_style(self):
        style = ttk.Style()
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=BG, foreground=TEXT)
        style.configure("Main.TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG)

        style.configure(
            "Title.TLabel",
            background=BG,
            foreground=TEXT,
            font=("Arial", 24, "bold")
        )
        style.configure(
            "Sub.TLabel",
            background=BG,
            foreground=MUTED,
            font=("Arial", 12)
        )
        style.configure(
            "InfoLabel.TLabel",
            background=BG,
            foreground=MUTED,
            font=("Arial", 11, "bold")
        )
        style.configure(
            "InfoValue.TLabel",
            background=BG,
            foreground=TEXT,
            font=("Arial", 11)
        )

        style.configure(
            "Card.TLabelframe",
            background=PANEL,
            foreground=TEXT,
            borderwidth=1,
            relief="solid"
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=PANEL,
            foreground=TEXT,
            font=("Arial", 12, "bold")
        )

        style.configure(
            "Dark.TButton",
            background=ACCENT_2,
            foreground=TEXT,
            bordercolor=ACCENT_2,
            font=("Arial", 11, "bold"),
            padding=(16, 11)
        )
        style.map(
            "Dark.TButton",
            background=[("active", ACCENT), ("disabled", "#4d545b")],
            foreground=[("disabled", "#c2c7cc")]
        )

        style.configure(
            "Secondary.TButton",
            background=PANEL_2,
            foreground=TEXT,
            bordercolor=BORDER,
            font=("Arial", 11, "bold"),
            padding=(16, 11)
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#394047"), ("disabled", "#3a3f44")],
            foreground=[("disabled", "#9ea5ad")]
        )

    def build_ui(self):
        main = ttk.Frame(self.root, padding=16, style="Main.TFrame")
        main.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(main, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 12))

        ttk.Label(header, text="SonoLite GUI", style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="PicoScope + Servo + Image Viewer",
            style="Sub.TLabel"
        ).pack(side="left", padx=(14, 0), pady=(9, 0))

        # Controls
        controls = ttk.LabelFrame(main, text="Controls", padding=12, style="Card.TLabelframe")
        controls.pack(fill="x", pady=(0, 10))

        self.turn_on_btn = ttk.Button(
            controls,
            text="1. Turn Signal ON",
            command=self.launch,
            style="Dark.TButton"
        )
        self.turn_on_btn.pack(side="left", padx=(0, 10))

        self.start_scan_btn = ttk.Button(
            controls,
            text="2. Start Scan",
            command=self.start_scan,
            state="disabled",
            style="Secondary.TButton"
        )
        self.start_scan_btn.pack(side="left")

        # Status row
        info = ttk.Frame(main, style="Main.TFrame")
        info.pack(fill="x", pady=(0, 12))

        self.status_var = tk.StringVar(value="Idle")
        self.folder_var = tk.StringVar(value="-")

        ttk.Label(info, text="Status:", style="InfoLabel.TLabel").pack(side="left")
        ttk.Label(info, textvariable=self.status_var, style="InfoValue.TLabel").pack(side="left", padx=(8, 24))
        ttk.Label(info, text="Capture Folder:", style="InfoLabel.TLabel").pack(side="left")
        ttk.Label(info, textvariable=self.folder_var, style="InfoValue.TLabel").pack(side="left", padx=(8, 0))

        # Images row
        image_row = ttk.Frame(main, style="Main.TFrame")
        image_row.pack(fill="both", expand=True, pady=(0, 12))

        image_row.columnconfigure(0, weight=1)
        image_row.columnconfigure(1, weight=1)
        image_row.rowconfigure(0, weight=1)

        viewer1 = ttk.LabelFrame(image_row, text="Image 1", padding=10, style="Card.TLabelframe")
        viewer1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.img1 = tk.Label(
            viewer1,
            text="Waiting for image...",
            bg=PANEL,
            fg=MUTED,
            font=("Arial", 13),
            bd=0
        )
        self.img1.pack(fill="both", expand=True)

        viewer2 = ttk.LabelFrame(image_row, text="Image 2", padding=10, style="Card.TLabelframe")
        viewer2.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        self.img2 = tk.Label(
            viewer2,
            text="Waiting for image...",
            bg=PANEL,
            fg=MUTED,
            font=("Arial", 13),
            bd=0
        )
        self.img2.pack(fill="both", expand=True)

        # Terminal bottom
        terminal_frame = ttk.LabelFrame(main, text="Terminal Output", padding=10, style="Card.TLabelframe")
        terminal_frame.pack(fill="both", expand=False)
        terminal_frame.configure(height=250)

        self.log = tk.Text(
            terminal_frame,
            wrap="word",
            height=13,
            font=("Courier New", 12),
            bg=TERM_BG,
            fg=TERM_FG,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=12
        )
        self.log.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(terminal_frame, orient="vertical", command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)

        self.configure_terminal_tags()

        if not PIL_OK:
            self.img1.configure(text="Pillow not installed.\nRun: python3 -m pip install pillow")
            self.img2.configure(text="Pillow not installed.\nRun: python3 -m pip install pillow")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def configure_terminal_tags(self):
        self.log.tag_configure("good", foreground="#7CFC98")
        self.log.tag_configure("warn", foreground="#FFD166")
        self.log.tag_configure("info", foreground="#7AB8FF")
        self.log.tag_configure("title", foreground="#FFFFFF")

    def set_status(self, text):
        self.status_var.set(text)

    def log_print(self, text):
        tag = None
        lower = text.lower()

        if "scan complete" in lower or "saved regular image" in lower or "saved tracking figure" in lower:
            tag = "good"
        elif "warning" in lower:
            tag = "warn"
        elif "running image reconstruction" in lower or "created folder:" in lower or "signal generator" in lower:
            tag = "info"

        if tag:
            self.log.insert("end", text, tag)
        else:
            self.log.insert("end", text)

        self.log.see("end")

    def clear_images(self):
        self.img1.configure(image="", text="Waiting for image...")
        self.img1.image = None
        self.img2.configure(image="", text="Waiting for image...")
        self.img2.image = None

    def launch(self):
        if self.process is not None:
            return

        self.clear_images()
        self.current_folder = None
        self.folder_var.set("-")
        self.log.delete("1.0", "end")

        try:
            self.process = subprocess.Popen(
                ["./scan_controller"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True
            )
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))
            return

        threading.Thread(target=self.read_output, daemon=True).start()

        self.turn_on_btn.config(state="disabled")
        self.start_scan_btn.config(state="normal")
        self.set_status("Signal Generator ON")

    def start_scan(self):
        if self.process is None or self.process.stdin is None:
            return

        try:
            self.process.stdin.write("\n")
            self.process.stdin.flush()
            self.start_scan_btn.config(state="disabled")
            self.set_status("Scanning...")
        except Exception as e:
            messagebox.showerror("Start Scan Error", str(e))

    def read_output(self):
        try:
            for line in self.process.stdout:
                self.output_queue.put(line)
        finally:
            self.output_queue.put("__PROCESS_ENDED__")

    def poll_output(self):
        try:
            while True:
                item = self.output_queue.get_nowait()

                if item == "__PROCESS_ENDED__":
                    self.process = None
                    self.turn_on_btn.config(state="normal")
                    self.start_scan_btn.config(state="disabled")
                    self.load_images_after_completion()

                    if self.status_var.get() not in ["Scan complete", "Reconstruction warning"]:
                        self.set_status("Idle")
                    break

                self.log_print(item)
                self.parse_line(item)

        except queue.Empty:
            pass

        self.root.after(100, self.poll_output)

    def parse_line(self, line):
        stripped = line.strip()
        lower = stripped.lower()

        if "Created folder:" in line:
            folder = line.split("Created folder:", 1)[1].strip()
            self.current_folder = os.path.abspath(folder)
            self.folder_var.set(self.current_folder)

        elif "signal generator on" in lower or "signal generator is on" in lower:
            self.set_status("Signal Generator ON")

        elif "starting scan" in lower:
            self.set_status("Scanning...")

        elif "running image reconstruction" in lower:
            self.set_status("Building images...")

        elif "scan complete" in lower:
            self.set_status("Scan complete")

        elif "warning: image_constructor.py returned non-zero status." in lower:
            self.set_status("Reconstruction warning")

    def load_images_after_completion(self):
        if not PIL_OK:
            return

        if not self.current_folder or not os.path.isdir(self.current_folder):
            return

        pngs = sorted(
            glob.glob(os.path.join(self.current_folder, "*.png")),
            key=os.path.getmtime
        )

        if not pngs:
            self.img1.configure(text="No images found.", image="")
            self.img2.configure(text="No images found.", image="")
            self.img1.image = None
            self.img2.image = None
            return

        regular = None
        tracking = None

        for path in pngs:
            name = os.path.basename(path).lower()
            if regular is None and "regular" in name:
                regular = path
            elif tracking is None and ("tracking" in name or "demo" in name or "tracked" in name):
                tracking = path

        if regular is None and len(pngs) >= 1:
            regular = pngs[0]

        if tracking is None and len(pngs) >= 2:
            for path in pngs:
                if path != regular:
                    tracking = path
                    break

        loaded1 = False
        loaded2 = False

        if regular is not None:
            loaded1 = self.load_image_into_label(regular, self.img1, (680, 420))

        if tracking is not None:
            loaded2 = self.load_image_into_label(tracking, self.img2, (680, 420))

        if not loaded1:
            self.img1.configure(text="Could not load image 1.", image="")
            self.img1.image = None

        if not loaded2:
            self.img2.configure(text="Could not load image 2.", image="")
            self.img2.image = None

    def load_image_into_label(self, path, label, size):
        try:
            img = Image.open(path)
            img.load()

            resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            img.thumbnail(size, resample)

            tk_img = ImageTk.PhotoImage(img)
            label.configure(image=tk_img, text="")
            label.image = tk_img
            return True
        except Exception:
            return False

    def on_close(self):
        if self.process is not None:
            if not messagebox.askyesno("Exit", "The scan is still running. Close anyway?"):
                return
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ScanControllerGUI(root)
    root.mainloop()
