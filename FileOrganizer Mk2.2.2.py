import os
import shutil
import re
import tkinter as tk
from tkinter import filedialog


# -----------------------------
# KNOWN STAINS
# -----------------------------
KNOWN_STAINS = {
    "H&E": [r'h\s*&\s*e'],
    "PSR": [r'\bpsr\b'],
    "MT": [r'\bmt\b'],
    "TH": [r'\bth\b'],
    "LDH": [r'\bldh\b'],
    "VER": [r'\bver\b'],
    "TUBB3": [r'\btubb3\b'],
    "NF": [r'\bnf\b'],
    "PAS": [r'\bpas\b']
}


# -----------------------------
# NORMALIZE SCANNER SUFFIXES
# Handles:
# H&E_01
# PSR_02
# PAS_03
# etc.
# -----------------------------
def normalize_filename(name):
    name = re.sub(r'(_0\d+)(?=\.)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(_0\d+)$', '', name, flags=re.IGNORECASE)

    return name


# -----------------------------
# TIMEPOINT EXTRACTION (FIXED)
# -----------------------------
def extract_timepoint(filename):
    filename = normalize_filename(filename)

    f = filename.lower()

    # --------------------------------
    # PRIORITY 1:
    # Explicit numeric timepoints
    # --------------------------------
    patterns = [
        r'\bday\s+(\d+)\b',
        r'\b(\d+)\s+day\b',
        r'\bweek\s+(\d+)\b',
        r'\b(\d+)\s+week\b',
        r'\bhour\s+(\d+)\b',
        r'\b(\d+)\s+hour\b',
        r'\bhr\s+(\d+)\b',
        r'\b(\d+)\s+hr\b'
    ]

    for pattern in patterns:
        m = re.search(pattern, f)

        if m:
            value = m.group(1)

            if "day" in pattern:
                return f"Day_{value}"

            elif "week" in pattern:
                return f"Week_{value}"

            else:
                return f"Hour_{value}"

    # --------------------------------
    # PRIORITY 2:
    # Special labels
    # --------------------------------
    if re.search(r'\be\.?d\.?\b', f):
        return "Early_Dead"

    if re.search(r'\bacute\b', f):
        return "Acute"

    if re.search(r'\bna\b', f):
        return "NA"

    return "Unknown"


# -----------------------------
# STAIN EXTRACTION
# -----------------------------
def extract_stain(filename):
    filename = normalize_filename(filename)

    f = filename.lower()

    for stain, patterns in KNOWN_STAINS.items():
        for p in patterns:
            if re.search(p, f):
                return stain, "known"

    caps = re.findall(r'\b[A-Z0-9]{2,}\b', filename)

    if caps:
        return caps[-1], "auto"

    return "Unknown", "unknown"


# -----------------------------
# ANIMAL ID EXTRACTION
# Supports BOTH:
# 1. VHJ00718 25-95-3 ...
# 2. 25-95-3 ...
# -----------------------------
def extract_animal_id(filename):
    filename = normalize_filename(filename)

    tokens = filename.split()

    if len(tokens) == 0:
        return "Unknown_Animal"

    # --------------------------------
    # CASE 1:
    # Study ID present
    # Example:
    # VHJ00718 25-95-3 ...
    # --------------------------------
    if re.match(r'^[A-Za-z]{2,}\d+$', tokens[0]):
        if len(tokens) >= 2:
            candidate = tokens[1]

            if re.match(r'^[A-Za-z0-9-]+$', candidate):
                return candidate

    # --------------------------------
    # CASE 2:
    # No study ID
    # Example:
    # 25-95-3 ...
    # 56785 ...
    # 4FGHE ...
    # --------------------------------
    candidate = tokens[0]

    if re.match(r'^[A-Za-z0-9-]+$', candidate):
        return candidate

    return "Unknown_Animal"


# -----------------------------
# CLEANING FOR FOLDER MATCHING
# -----------------------------
def clean_key(name):
    name = normalize_filename(name)

    name = name.lower()

    # remove overview wrappers
    name = name.replace("_overview_", "")

    # remove recut/retest tags
    # examples:
    # RC-1
    # RT-2
    # RC1
    # RT3
    name = re.sub(r'\b(?:rc|rt)-?\d+\b', '', name)

    # remove outer underscores
    name = name.strip("_")

    # normalize spaces
    name = re.sub(r'\s+', ' ', name)

    return name.strip()


# -----------------------------
# FOLDER MATCH SCORE
# -----------------------------
def similarity_score(a, b):
    return len(set(a.split()) & set(b.split()))


# -----------------------------
# GUI MODE SELECTOR
# -----------------------------
def get_mode(root):
    from tkinter import Toplevel, StringVar, OptionMenu, Button, Label

    win = Toplevel(root)
    win.title("Select Stratification Mode")
    win.geometry("300x150")

    mode_var = StringVar(value="time")

    Label(
        win,
        text="Choose stratification mode:"
    ).pack(pady=10)

    OptionMenu(
        win,
        mode_var,
        "time",
        "stain",
        "animal"
    ).pack(pady=10)

    def confirm():
        win.destroy()

    Button(
        win,
        text="Confirm",
        command=confirm
    ).pack(pady=10)

    win.grab_set()
    root.wait_window(win)

    return mode_var.get()


# -----------------------------
# MAIN
# -----------------------------
def organize_files():
    root = tk.Tk()
    root.withdraw()

    file_paths = filedialog.askopenfilenames(
        title="Select .vsi files",
        filetypes=[("VSI files", "*.vsi")]
    )

    if not file_paths:
        return

    mode = get_mode(root)

    base_dir = os.path.dirname(file_paths[0])
    all_items = os.listdir(base_dir)

    plan = {}
    auto_detected = []
    unknown_files = []

    # -----------------------------
    # BUILD PLAN
    # -----------------------------
    for file_path in file_paths:
        filename = os.path.basename(file_path)

        if mode == "time":
            key = extract_timepoint(filename)

        elif mode == "stain":
            key, status = extract_stain(filename)

            if status == "auto":
                auto_detected.append((filename, key))

            elif status == "unknown":
                unknown_files.append(filename)

        else:  # animal
            key = extract_animal_id(filename)

        plan.setdefault(key, []).append(filename)

    # -----------------------------
    # BUILD PREVIEW TEXT
    # -----------------------------
    preview = ""

    if auto_detected:
        preview += "Auto-detected stains:\n\n"

        for f, k in auto_detected:
            preview += f"{f} -> {k}\n"

        preview += "\n"

    if unknown_files:
        preview += "Unknown stains:\n\n"

        for f in unknown_files:
            preview += f"{f}\n"

        preview += "\n"

    preview += "---- ORGANIZATION PLAN ----\n\n"

    for k, files in plan.items():
        preview += f"{k}:\n"

        for f in files:
            preview += f"  - {f}\n"

        preview += "\n"

    # -----------------------------
    # SCROLLABLE PREVIEW WINDOW
    # -----------------------------
    preview_window = tk.Toplevel(root)
    preview_window.title("Organization Preview")
    preview_window.geometry("900x700")

    text_frame = tk.Frame(preview_window)
    text_frame.pack(fill="both", expand=True)

    scrollbar = tk.Scrollbar(text_frame)
    scrollbar.pack(side="right", fill="y")

    text_widget = tk.Text(
        text_frame,
        wrap="word",
        yscrollcommand=scrollbar.set
    )

    text_widget.insert("1.0", preview)
    text_widget.config(state="disabled")

    text_widget.pack(fill="both", expand=True)

    scrollbar.config(command=text_widget.yview)

    proceed_var = tk.BooleanVar(value=False)

    def proceed_action():
        proceed_var.set(True)
        preview_window.destroy()

    def cancel_action():
        preview_window.destroy()

    button_frame = tk.Frame(preview_window)
    button_frame.pack(pady=10)

    tk.Button(
        button_frame,
        text="Proceed",
        command=proceed_action,
        width=15
    ).pack(side="left", padx=10)

    tk.Button(
        button_frame,
        text="Cancel",
        command=cancel_action,
        width=15
    ).pack(side="left", padx=10)

    preview_window.grab_set()
    root.wait_window(preview_window)

    if not proceed_var.get():
        return

    # -----------------------------
    # EXECUTE MOVES
    # -----------------------------
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        # Determine grouping key
        if mode == "time":
            key = extract_timepoint(filename)

        elif mode == "stain":
            key, _ = extract_stain(filename)

        else:
            key = extract_animal_id(filename)

        target_folder = os.path.join(base_dir, key)
        os.makedirs(target_folder, exist_ok=True)

        # Move VSI file
        shutil.move(
            file_path,
            os.path.join(target_folder, filename)
        )

        # --------------------------------
        # STACK FOLDER MATCHING
        # --------------------------------
        file_key = clean_key(name_no_ext)

        best_match = None
        best_score = 0

        for item in all_items:
            item_path = os.path.join(base_dir, item)

            if not os.path.isdir(item_path):
                continue

            folder_key = clean_key(item)

            score = similarity_score(
                file_key,
                folder_key
            )

            if score > best_score and score >= 6:
                best_score = score
                best_match = item_path

        if best_match:
            shutil.move(
                best_match,
                os.path.join(
                    target_folder,
                    os.path.basename(best_match)
                )
            )

    # -----------------------------
    # DONE MESSAGE
    # -----------------------------
    done_window = tk.Toplevel(root)
    done_window.title("Done")
    done_window.geometry("300x120")

    tk.Label(
        done_window,
        text="Files organized successfully!"
    ).pack(pady=20)

    tk.Button(
        done_window,
        text="OK",
        command=done_window.destroy,
        width=12
    ).pack(pady=10)

    done_window.grab_set()
    root.wait_window(done_window)


# -----------------------------
# ENTRY
# -----------------------------
if __name__ == "__main__":
    organize_files()