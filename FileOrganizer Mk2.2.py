import os
import shutil
import re
import tkinter as tk
from tkinter import filedialog, messagebox


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
    "PAS": [r'\bpas\b'], "unstained": [r'\bunstained\b']
}


# -----------------------------
# TIMEPOINT EXTRACTION
# -----------------------------
def extract_timepoint(filename):
    f = filename.lower()

    if re.search(r'\be\.?d\.?\b', f):
        return "Early_Dead"

    if re.search(r'\bna\b', f):
        return "NA"

    if re.search(r'\bacute\b', f):
        return "Acute"

    pattern = r'\b(day|week|hour|hr)s?\s*(\d+)|\b(\d+)\s*(day|week|hour|hr)s?\b'
    m = re.search(pattern, f)

    if not m:
        return "Unknown"

    if m.group(1) and m.group(2):
        unit, val = m.group(1), m.group(2)
    else:
        val, unit = m.group(3), m.group(4)

    unit = unit.lower()

    if unit.startswith('d'):
        unit = "Day"
    elif unit.startswith('w'):
        unit = "Week"
    else:
        unit = "Hour"

    return f"{unit}_{val}"


# -----------------------------
# STAIN EXTRACTION
# -----------------------------
def extract_stain(filename):
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
# -----------------------------
def extract_animal_id(filename):
    tokens = filename.split()

    if len(tokens) < 2:
        return "Unknown_Animal"

    candidate = tokens[1]

    if re.match(r'^[A-Za-z0-9-]+$', candidate):
        return candidate

    return "Unknown_Animal"


# -----------------------------
# CLEAN KEY (folder matching)
# -----------------------------
def clean_key(name):
    name = name.lower()
    name = name.replace("_overview_", "")
    name = name.strip("_")
    name = re.sub(r'\s+', ' ', name)
    return name


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

    Label(win, text="Choose stratification mode:").pack(pady=10)

    OptionMenu(win, mode_var, "time", "stain", "animal").pack(pady=10)

    def confirm():
        win.destroy()

    Button(win, text="Confirm", command=confirm).pack(pady=10)

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
    # PREVIEW
    # -----------------------------
    preview = ""

    if auto_detected:
        preview += "Auto-detected stains:\n"
        for f, k in auto_detected:
            preview += f"  {f} -> {k}\n"
        preview += "\n"

    if unknown_files:
        preview += "Unknown stains:\n"
        for f in unknown_files:
            preview += f"  {f}\n"
        preview += "\n"

    preview += "---- PLAN ----\n\n"

    for k, files in plan.items():
        preview += f"{k}:\n"
        for f in files:
            preview += f"  - {f}\n"
        preview += "\n"

    if not messagebox.askyesno("Preview", preview + "\nProceed?"):
        return

    # -----------------------------
    # EXECUTE
    # -----------------------------
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]

        if mode == "time":
            key = extract_timepoint(filename)
        elif mode == "stain":
            key, _ = extract_stain(filename)
        else:
            key = extract_animal_id(filename)

        target_folder = os.path.join(base_dir, key)
        os.makedirs(target_folder, exist_ok=True)

        shutil.move(file_path, os.path.join(target_folder, filename))

        file_key = clean_key(name_no_ext)

        best_match = None
        best_score = 0

        for item in all_items:
            item_path = os.path.join(base_dir, item)

            if not os.path.isdir(item_path):
                continue

            folder_key = clean_key(item)

            score = similarity_score(file_key, folder_key)

            if score > best_score and score >= 6:
                best_score = score
                best_match = item_path

        if best_match:
            shutil.move(
                best_match,
                os.path.join(target_folder, os.path.basename(best_match))
            )

    messagebox.showinfo("Done", "Files organized successfully!")


if __name__ == "__main__":
    organize_files()