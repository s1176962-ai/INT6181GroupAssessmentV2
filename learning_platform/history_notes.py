"""Profile-owned annotations and shared date/query rules for screen and export."""

from datetime import datetime

from .storage import DataError, JsonStore


def local_time(value):
    date = datetime.fromisoformat(value)
    return date.astimezone() if date.tzinfo else date


def display_time(value):
    return local_time(value).strftime("%Y/%m/%d %H:%M:%S")


class HistoryNotes:
    def __init__(self, profile_folder):
        self.store = JsonStore(profile_folder / "history_notes.json", {})

    def load(self):
        data = self.store.read()
        if not isinstance(data, dict) or any(
            not isinstance(item, dict)
            or type(item.get("liked")) is not bool
            or not isinstance(item.get("note"), str)
            for item in data.values()
        ):
            raise DataError("Invalid history notes; original file preserved.")
        return data

    def save(self, record_id, liked, note):
        data = self.load()
        data[record_id] = {"liked": bool(liked), "note": note.strip()}
        self.store.write(data)


def query_history(records, notes, start="", end="", liked="all", commented="all"):
    lower = datetime.strptime(start, "%Y/%m/%d").date() if start else None
    upper = datetime.strptime(end, "%Y/%m/%d").date() if end else None
    if lower and upper and lower > upper:
        raise ValueError("Start date must not be after end date")
    matches = []
    for record in records:
        day = local_time(record["date"]).date()
        annotation = notes.get(record["id"], {"liked": False, "note": ""})
        if lower and day < lower or upper and day > upper:
            continue
        if liked != "all" and annotation["liked"] != (liked == "yes"):
            continue
        if commented != "all" and bool(annotation["note"].strip()) != (commented == "yes"):
            continue
        matches.append({**record, **annotation})
    return sorted(matches, key=lambda item: local_time(item["date"]).timestamp(), reverse=True)
