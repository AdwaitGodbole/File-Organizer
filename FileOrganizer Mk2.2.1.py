
#Improvement over Mk 2.2: works with filenames without the Study Number. Handles RC and RT inserts as well as scanner
#triggered rescans such as H&E_01

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
    # remove scanner-generated suffixes
    # examples:
    # H&E_01
    # PSR_02
    # MT_03
    name = re.sub(r'(_0\d+)(?=\.)', '', name, flags=re.IGNORECASE)
    name = re.sub(r'(_0\d+)$', '', name, flags=re.IGNORECASE)

    return name


# -----------------------------
# TIMEPOINT EXTRACTION
# -----------------------------
def extract_timepoint(filename):
    filename = normalize_filename(filename)

    f = filename.lower()

    # ---- special cases ----
    if re.search(r'\be\.?d\.?\b', f):
        return "Early_Dead"

    if re.search(r'\bna\b', f):
        return "NA"

    if re.search(r'\bacute\b', f):
        return "Acute"

    # ---- standard timepoints ----
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
    # First token is study ID
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

    preview += "---- ORGANIZATION PLAN ----\n\n"

    for k, files in plan.items():
        preview += f"{k}:\n"

        for f in files:
            preview += f"  - {f}\n"

        preview += "\n"

    proceed = messagebox.askyesno(
        "Preview",
        preview + "\nProceed?"
    )

    if not proceed:
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

    messagebox.showinfo(
        "Done",
        "Files organized successfully!"
    )


# -----------------------------
# ENTRY
# -----------------------------
if __name__ == "__main__":
    organize_files()