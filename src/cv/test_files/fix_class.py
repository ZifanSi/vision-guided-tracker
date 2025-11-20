from pathlib import Path

LABELS = Path(r"C:\Personal-Project\vision-guided-tracker\src\cv\data\grand_dataset\labels")  # adjust if needed
OLD = 1  # class index you want to remove
NEW = 0  # class index to merge into

for txt in LABELS.rglob("*.txt"):
    lines = []
    with txt.open("r") as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            cls = int(parts[0])
            if cls == OLD:
                parts[0] = str(NEW)
            lines.append(" ".join(parts))
    with txt.open("w") as f:
        f.write("\n".join(lines))

print("Done. All class", OLD, "→", NEW)
