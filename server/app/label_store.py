from __future__ import annotations

from sqlite3 import Connection

PROTECTED_LABELS = {"unknown", "test"}


def normalize_label_name(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(str(name).strip().split())


def parse_labels(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_text = str(value).replace(";", ",")
        raw_items = raw_text.split(",")

    labels: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if isinstance(item, dict):
            label = normalize_label_name(item.get("name"))
        else:
            label = normalize_label_name(str(item))
        if not label or label.startswith("#") or label in seen:
            continue
        labels.append(label)
        seen.add(label)
    return labels


def serialize_labels(labels: list[str]) -> str:
    normalized: list[str] = []
    seen: set[str] = set()
    for label in labels:
        name = normalize_label_name(label)
        if not name or name in seen:
            continue
        normalized.append(name)
        seen.add(name)
    return ",".join(normalized) if normalized else "unknown"


def labels_status(labels: list[str]) -> str:
    active = [label for label in labels if label != "unknown"]
    return "labeled" if active else "unlabeled"


def ensure_labels(conn: Connection, labels: list[str]) -> list[str]:
    normalized = []
    for label in labels:
        name = normalize_label_name(label)
        if not name:
            continue
        conn.execute("INSERT OR IGNORE INTO labels (name) VALUES (?)", (name,))
        normalized.append(name)
    return normalized


def all_label_names(conn: Connection) -> list[str]:
    names: set[str] = set()
    rows = conn.execute("SELECT name FROM labels ORDER BY name").fetchall()
    names.update(row["name"] if hasattr(row, "keys") else row[0] for row in rows)

    image_rows = conn.execute("SELECT label FROM images").fetchall()
    for row in image_rows:
        value = row["label"] if hasattr(row, "keys") else row[0]
        names.update(parse_labels(value))

    names.discard("")
    names.update(PROTECTED_LABELS)
    return sorted(names)


def label_counts(conn: Connection) -> dict[str, int]:
    counts = {label: 0 for label in all_label_names(conn)}
    rows = conn.execute("SELECT label FROM images").fetchall()
    for row in rows:
        value = row["label"] if hasattr(row, "keys") else row[0]
        for label in set(parse_labels(value)):
            counts[label] = counts.get(label, 0) + 1
    return counts


def add_labels_to_existing(existing_value: object, label_names: list[str]) -> list[str]:
    labels = parse_labels(label_names)
    if "test" in labels:
        return ["test"]
    active = [label for label in labels if label != "unknown"]
    if active:
        return [active[0]]
    if "unknown" in labels:
        return ["unknown"]
    existing = parse_labels(existing_value)
    return [existing[0]] if existing else ["unknown"]


def remove_labels_from_existing(existing_value: object, label_names: list[str]) -> list[str]:
    remove_set = set(parse_labels(label_names))
    remaining = [label for label in parse_labels(existing_value) if label not in remove_set]
    return remaining or ["unknown"]
