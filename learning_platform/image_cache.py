"""Bounded, Tk-interpreter-local image cache with file-change invalidation."""

import tkinter as tk
from collections import OrderedDict
from pathlib import Path


def _remember(cache, key, factory, limit):
    if key in cache:
        cache.move_to_end(key)
        return cache[key]
    value = factory()
    cache[key] = value
    while len(cache) > limit:
        cache.popitem(last=False)
    return value


def source_image(root, path):
    path = Path(path).resolve()
    stamp = path.stat()
    key = (str(path), stamp.st_mtime_ns, stamp.st_size)
    cache = root.__dict__.setdefault("_source_images", OrderedDict())
    return _remember(cache, key, lambda: tk.PhotoImage(master=root, file=str(path)), 16)


def portrait_image(root, path, state, target, sheet=True):
    path = Path(path).resolve()
    stamp = path.stat()
    key = (str(path), stamp.st_mtime_ns, stamp.st_size, state, target, sheet)
    cache = root.__dict__.setdefault("_portrait_images", OrderedDict())

    def build():
        base = source_image(root, path)
        if sheet:
            width = base.width() // 3
            index = {"thinking": 0, "correct": 1, "wrong": 2}[state]
            cropped = tk.PhotoImage(master=root, width=width, height=base.height())
            cropped.tk.call(
                str(cropped),
                "copy",
                str(base),
                "-from",
                index * width,
                0,
                (index + 1) * width,
                base.height(),
                "-to",
                0,
                0,
            )
            base = cropped
        factor = max(1, (max(base.width(), base.height()) + target - 1) // target)
        return base.subsample(factor) if factor > 1 else base

    return _remember(cache, key, build, 12)
