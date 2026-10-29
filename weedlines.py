"""weedlines.py - smart weeding lines for single-color vinyl lettering
Version 0.1.0-beta
Copyright (c) 2026 George Sladic, Studio 57 Design
Released under the MIT License. Provided as is, with no warranty. See LICENSE.

Takes an Illustrator SVG with outlined lettering, draws a margin rectangle around it,
makes the negative (waste), and splits the waste into easy-to-weed pieces. Cuts go
across the narrowest gaps between letters, and hairline openings into counters
(tops of a's, bottoms of p bowls) are always closed off.

Output, saved next to the input file:
  <name>_weed_cut.svg      negative pieces as closed shapes, ready for Cricut Design Space
  <name>_weed_preview.png  preview: each tint is one waste piece, red lines are the weed cuts
If those files already exist, it asks whether to replace them, save new numbered copies,
or skip that file.

Using the program (weedlines.exe):
  Double-click it to pick one or more SVG files, or drag SVG files onto it.
  A progress window shows each file as it works and the results when it's done.

Command line:
  python weedlines.py                (no file: opens a file picker)
  python weedlines.py topper.svg
  python weedlines.py topper.svg --amax 1.0 --emax 1.75 --amin 0.08     (finer pieces)
  python weedlines.py topper.svg --margin 0.375                         (wider margin)
  python weedlines.py topper.svg --overwrite                            (replace old results, no prompt)
  python weedlines.py --help                                            (all options)

Needs: pip install shapely scipy svgpathtools numpy matplotlib

Build (Windows), with weedlines.ico and splash.png in the same folder:
  py -m PyInstaller --onedir --noconsole --icon=weedlines.ico --splash=splash.png weedlines.py
"""
__version__ = "0.1.0-beta"

try:
    import pyi_splash          # only present in a PyInstaller build made with --splash
except ImportError:
    pyi_splash = None

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import shapely
from scipy.spatial import Delaunay
from shapely import make_valid
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree
from svgpathtools import parse_path

PT = 72.0          # Illustrator SVG units: 72 per inch
PACE = 0.00066     # progress-bar pacing constant, fitted on test designs
STEP = 0.25        # curve sampling step in pt
NS = {"svg": "http://www.w3.org/2000/svg"}


# ---------------------------------------------------------------- reading the SVG

def sample_subpath(sp):
    pts = []
    for seg in sp:
        L = seg.length(error=1e-4)
        n = max(2, int(np.ceil(L / STEP)) + 1)
        pts.extend(seg.point(t) for t in np.linspace(0, 1, n)[:-1])
    pts.append(sp[-1].end)
    return [(p.real, p.imag) for p in pts]


def ring_area_signed(coords):
    a = np.asarray(coords)
    x, y = a[:, 0], a[:, 1]
    return 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)


def nonzero_fill(rings):
    """Region with nonzero winding, so overlapping script glyphs merge into one shape."""
    rings = [r for r in rings if len(r) >= 4]
    if not rings:
        return Polygon()
    polys = [(make_valid(Polygon(r)), 1 if ring_area_signed(r) > 0 else -1) for r in rings]
    lines = unary_union([Polygon(r).exterior for r in rings])
    keep = []
    for f in polygonize(lines):
        rp = f.representative_point()
        if sum(s for p, s in polys if p.contains(rp)) != 0:
            keep.append(f)
    return unary_union(keep)


def load_letters(svg_file, progress=None):
    root = ET.parse(svg_file).getroot()
    total = max(1, sum(1 for el in root.iter() if el.tag.endswith("}path")))
    seen = [0]
    clips = {}
    for cp in root.iter("{http://www.w3.org/2000/svg}clipPath"):
        r = cp.find("svg:rect", NS)
        if r is not None:
            x, y = float(r.get("x", 0)), float(r.get("y", 0))
            clips[cp.get("id")] = box(x, y, x + float(r.get("width")), y + float(r.get("height")))
    shapes = []

    def walk(el, clip):
        cpa = el.get("clip-path")
        if cpa:
            m = re.search(r"#([^)]+)", cpa)
            c = clips.get(m.group(1)) if m else None
            if c is not None:
                clip = c if clip is None else clip.intersection(c)
        if el.tag.endswith("}path") and el.get("d"):
            path = parse_path(el.get("d"))
            g = nonzero_fill([sample_subpath(sp) for sp in path.continuous_subpaths() if len(sp)])
            if clip is not None:
                g = g.intersection(clip)
            shapes.append(g)
            seen[0] += 1
            if progress:
                progress(seen[0] / total)
        for ch in el:
            walk(ch, clip)

    walk(root, None)
    if not shapes:
        raise ValueError("No outlined shapes found. Make sure the text is converted to outlines in Illustrator.")
    return make_valid(unary_union(shapes))


# ---------------------------------------------------------------- weed-line logic

def as_list(g):
    if g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, "geoms") else [g]


def candidates(W, spacing, lmin, lmax):
    """Possible cuts: shortest straight bridges across the waste, from a Delaunay mesh of its edges."""
    pts, ring_id, arc, ring_len = [], [], [], []
    rid = 0
    for poly in as_list(W):
        for ring in [poly.exterior] + list(poly.interiors):
            L = ring.length
            for d in np.linspace(0, L, max(8, int(L / spacing)), endpoint=False):
                p = ring.interpolate(d)
                pts.append((p.x, p.y)); ring_id.append(rid); arc.append(d); ring_len.append(L)
            rid += 1
    pts, ring_id, arc, ring_len = map(np.array, (pts, ring_id, arc, ring_len))
    tri = Delaunay(pts)
    e = np.vstack([tri.simplices[:, [0, 1]], tri.simplices[:, [1, 2]], tri.simplices[:, [0, 2]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    a, b = e[:, 0], e[:, 1]
    length = np.linalg.norm(pts[a] - pts[b], axis=1)
    keep = (length >= lmin) & (length <= lmax)
    same = ring_id[a] == ring_id[b]
    dar = np.abs(arc[a] - arc[b])
    dar = np.minimum(dar, ring_len[a] - dar)
    keep &= (~same) | ((dar > 3.5 * length) & (dar > 12))   # same outline only across a bay
    a, b, length = a[keep], b[keep], length[keep]
    p, q = pts[a], pts[b]
    d = q - p
    lines = shapely.linestrings(np.stack([p + 0.02 * d, q - 0.02 * d], axis=1))
    shapely.prepare(W)
    inside = shapely.within(lines, W)
    a, b, length = a[inside], b[inside], length[inside]
    acc, mids = [], []
    for i in np.argsort(length):
        m = (pts[a[i]] + pts[b[i]]) / 2
        if mids and np.linalg.norm(np.array(mids) - m, axis=1).min() < 3.0:
            continue
        mids.append(m)
        acc.append(LineString([pts[a[i]], pts[b[i]]]))
    return acc


def extend(line, amt=0.3):
    (x1, y1), (x2, y2) = line.coords
    v = np.array([x2 - x1, y2 - y1])
    v /= np.linalg.norm(v)
    return LineString([(x1 - v[0] * amt, y1 - v[1] * amt), (x2 + v[0] * amt, y2 + v[1] * amt)])


def split_with(P, c, gap=0.002):
    return [q for q in as_list(P.difference(extend(c).buffer(gap, cap_style="flat"))) if q.area > 1.0]


def needs_split(P, amax, emax):
    x0, y0, x1, y1 = P.bounds
    return P.area > amax or max(x1 - x0, y1 - y0) > emax


def weed(letters, margin_in=0.25, amax_in2=1.5, emax_in=2.0, amin_in2=0.12, lmax_in=0.6,
         lmax_fallback_in=1.25, neck_in=0.06, progress=None):
    """progress(fraction, status) is called as work moves along, if given."""
    report = progress or (lambda f, msg: None)
    m = margin_in * PT
    x0, y0, x1, y1 = letters.bounds
    rect = box(x0 - m, y0 - m, x1 + m, y1 + m)
    W = rect.difference(letters)
    amax, emax, amin = amax_in2 * PT ** 2, emax_in * PT, amin_in2 * PT ** 2
    report(0.0, "Finding the narrow gaps between letters")
    cands = candidates(W, spacing=1.0, lmin=0.3, lmax=lmax_fallback_in * PT)
    tree = STRtree(cands)
    report(0.07, "Closing off letter counters")
    pieces = [g for g in as_list(W) if g.area > 1.0]
    done, cuts = [], []

    # Pass 1: close pinch points (hairline openings into counters).
    # The pocket behind the neck must be a real bulb, not the sharp tip of a wedge.
    for c in sorted((k for k in cands if k.length <= neck_in * PT), key=lambda k: k.length):
        for i, P in enumerate(pieces):
            if not c.within(P.buffer(0.01)):
                continue
            parts = split_with(P, c)
            if len(parts) >= 2 and min(q.area for q in parts) >= max(25.0, 8 * c.length ** 2):
                pieces[i:i + 1] = parts
                cuts.append(c)
            break

    # Pass 2: split oversized pieces, preferring short cuts that leave balanced pieces.
    # Progress = how much oversized waste is left to split.
    # Progress bookkeeping. Time goes into testing cuts, and each test costs about the
    # size of the piece's outline, so "work" = outline size summed over the tests done.
    # Work left is estimated from the pieces still too big, using a formula fitted
    # by timing real designs: PACE x (cuts inside x outline size)^1.5 x (area/max)^0.25.
    stats = {"done": 0.0}

    def size(P):
        return len(P.exterior.coords) + sum(len(r.coords) for r in P.interiors)

    est_cache = {}

    def estimate(P):
        k = id(P)
        if k not in est_cache:                 # keep P in the cache so its id stays unique
            est_cache[k] = (P, (len(tree.query(P)) * size(P)) ** 1.5 * (P.area / amax) ** 0.25
                            if needs_split(P, amax, emax) else 0.0)
        return est_cache[k][1]

    def fraction():
        left = PACE * sum(estimate(P) for P in pieces)
        return stats["done"] / max(stats["done"] + left, 1.0)
    report(0.08, "Placing weed lines")
    shown = 0.0
    while pieces:
        shown = max(shown, fraction())     # never let the bar slide backwards
        report(0.08 + 0.92 * shown, f"Placing weed lines ({len(cuts)} so far)")
        pieces.sort(key=lambda g: g.area, reverse=True)
        P = pieces.pop(0)
        if not needs_split(P, amax, emax):
            done.append(P)
            continue
        sz = size(P)
        Pb = P.buffer(0.01)
        inside = sorted((cands[i] for i in tree.query(P, predicate="intersects") if cands[i].within(Pb)),
                        key=lambda c: c.length)
        best = best_score = best_parts = hole_best = hole_parts = None
        nh = len(P.interiors)
        bound = np.sqrt(P.area / 2)     # no split can leave a smaller piece bigger than half
        # A cut whose two ends sit on different outlines (say the outer edge and a letter
        # inside the piece) can't split the piece in two, only open up a hole. Sort those
        # out cheaply here instead of testing each one with full shape math.
        same_ring = np.ones(len(inside), bool)
        if nh and inside:
            rings = np.array([P.exterior] + list(P.interiors), dtype=object)
            e0 = shapely.points([c.coords[0] for c in inside])
            e1 = shapely.points([c.coords[-1] for c in inside])
            r0 = shapely.distance(rings[:, None], e0[None, :]).argmin(axis=0)
            r1 = shapely.distance(rings[:, None], e1[None, :]).argmin(axis=0)
            same_ring = r0 == r1
        hole_cands = []
        tried = 0.0
        for lim in (lmax_in * PT, lmax_fallback_in * PT):
            for k, c in enumerate(inside):
                if c.length <= tried:
                    continue                # already tested on the first pass
                if c.length > lim:
                    break
                if not same_ring[k]:
                    hole_cands.append(c)
                    continue
                if best_score is not None and c.length / bound >= best_score:
                    break                   # every longer cut scores worse than the best found
                parts = split_with(P, c)
                stats["done"] += sz
                if len(parts) >= 2:
                    amin_part = min(q.area for q in parts)
                    if amin_part < amin:
                        continue
                    score = c.length / np.sqrt(amin_part)
                    if best_score is None or score < best_score:
                        best, best_score, best_parts = c, score, parts
            if best is not None:
                break
            tried = lim
        if best is None:                    # no good split: open up the nearest hole instead
            for c in hole_cands:
                parts = split_with(P, c)
                if len(parts) == 1 and len(parts[0].interiors) < nh:
                    hole_best, hole_parts = c, parts
                    break
        if best is not None:
            cuts.append(best); pieces.extend(best_parts)
        elif hole_best is not None:
            cuts.append(hole_best); pieces.extend(hole_parts)
        else:
            done.append(P)
    return rect, done, cuts


# ---------------------------------------------------------------- output

def write_svg(path, pieces, rect, tol=0.05):
    x0, y0, x1, y1 = rect.bounds
    w, h = x1 - x0, y1 - y0
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}" height="{h:.2f}" viewBox="0 0 {w:.2f} {h:.2f}">',
           '<g id="weed_pieces">']
    for P in pieces:
        P = P.simplify(tol, preserve_topology=True)
        d = []
        for ring in [P.exterior] + list(P.interiors):
            c = np.asarray(ring.coords)[:-1] - [x0, y0]
            d.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in c) + " Z")
        out.append(f'<path d="{" ".join(d)}" fill="none" stroke="#000" stroke-width="0.5"/>')
    out.append("</g></svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def preview(path, letters, rect, pieces, cuts, title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path

    def patch(p, **kw):
        verts, codes = [], []
        for ring in [p.exterior] + list(p.interiors):
            c = np.asarray(ring.coords)
            verts.extend(c)
            codes.extend([Path.MOVETO] + [Path.LINETO] * (len(c) - 2) + [Path.CLOSEPOLY])
        return PathPatch(Path(verts, codes), **kw)

    x0, y0, x1, y1 = rect.bounds
    fig, ax = plt.subplots(figsize=(8, 8 * (y1 - y0) / (x1 - x0) + 0.5))
    rng = np.random.default_rng(3)
    for P in pieces:
        ax.add_patch(patch(P, fc=0.80 + 0.17 * rng.random(3), ec="none"))
    for g in as_list(letters):
        ax.add_patch(patch(g, fc="#c9a227", ec="#6b5410", lw=0.4))
    ax.add_patch(patch(rect, fc="none", ec="k", lw=1))
    for c in cuts:
        xs, ys = c.xy
        ax.plot(xs, ys, color="#d0021b", lw=1.6, solid_capstyle="round")
    ax.set_xlim(x0 - 5, x1 + 5)
    ax.set_ylim(y1 + 5, y0 - 5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=11)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- running it

HAS_CONSOLE = sys.stdin is not None and sys.stdout is not None   # False in a --noconsole build
START_DIR = r"D:\Downloads"


def outputs_for(src):
    base = os.path.splitext(os.path.abspath(src))[0]
    return base + "_weed_cut.svg", base + "_weed_preview.png"


def numbered_pair(out_svg, out_png):
    """randy_weed_cut.svg -> randy_weed_cut (2).svg (and the matching preview), first free number."""
    s_stem, s_ext = os.path.splitext(out_svg)
    p_stem, p_ext = os.path.splitext(out_png)
    n = 2
    while os.path.exists(f"{s_stem} ({n}){s_ext}") or os.path.exists(f"{p_stem} ({n}){p_ext}"):
        n += 1
    return f"{s_stem} ({n}){s_ext}", f"{p_stem} ({n}){p_ext}"


def already_there(out_svg, out_png, a):
    return os.path.exists(out_svg) or (not a.no_preview and os.path.exists(out_png))


def process(src, out_svg, out_png, a, progress=lambda f, m: None):
    """Do one file. progress(fraction 0..1, status text). Returns a summary dict."""
    progress(0.0, "Reading the lettering")
    letters = load_letters(src, lambda f: progress(0.03 * f, "Reading the lettering"))
    rect, pieces, cuts = weed(letters, a.margin, a.amax, a.emax, a.amin, a.lmax,
                              progress=lambda f, m: progress(0.03 + 0.89 * f, m))
    progress(0.92, "Writing the cut file")
    write_svg(out_svg, pieces, rect)
    if not a.no_preview:
        progress(0.93, "Drawing the preview")
        preview(out_png, letters, rect, pieces, cuts, f"{len(cuts)} weed cuts, {len(pieces)} pieces")
    progress(1.0, "Done")
    w, h = (rect.bounds[2] - rect.bounds[0]) / PT, (rect.bounds[3] - rect.bounds[1]) / PT
    return {"name": os.path.basename(src), "cuts": len(cuts), "pieces": len(pieces), "w": w, "h": h,
            "svg": out_svg, "png": None if a.no_preview else out_png}


# ---- console (command prompt) version

def run_console(files, a):
    for f in files:
        out_svg, out_png = outputs_for(f)
        print(f"\n{os.path.basename(f)}")
        if already_there(out_svg, out_png, a) and not a.overwrite:
            ans = input(f"  {os.path.basename(out_svg)} already exists. "
                        "[o]verwrite, [n]ew name, or [s]kip? (n) ").strip().lower()[:1]
            if ans == "s":
                print("  Skipped.")
                continue
            if ans != "o":
                out_svg, out_png = numbered_pair(out_svg, out_png)
        last = [-1]

        def prog(frac, msg):
            pct = int(frac * 100)
            if pct != last[0]:
                last[0] = pct
                print(f"\r  [{'#' * (pct // 4):<25}] {pct:3d}%  {msg[:40]:<40}", end="", flush=True)
        try:
            r = process(f, out_svg, out_png, a, prog)
            print(f"\n  {r['cuts']} weed cuts, {r['pieces']} pieces, size {r['w']:.2f} x {r['h']:.2f} in")
            print(f"  {r['svg']}")
            if r["png"]:
                print(f"  {r['png']}")
        except Exception as e:
            print(f"\n  Problem: {e}")


# ---- window version (double-click, drag-and-drop, or --noconsole build)

def find_icon():
    here = [getattr(sys, "_MEIPASS", ""), os.path.dirname(os.path.abspath(sys.argv[0]))]
    for d in here:
        p = os.path.join(d, "weedlines.ico")
        if d and os.path.exists(p):
            return p
    return sys.executable if getattr(sys, "frozen", False) else None   # Tk can read an exe's own icon


def open_file(path):
    if hasattr(os, "startfile"):
        os.startfile(path)
    else:
        import webbrowser
        webbrowser.open("file://" + path)


def show_in_folder(path):
    if sys.platform == "win32":
        import subprocess
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        open_file(os.path.dirname(path))


def run_window(files, a):
    import queue
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    if sys.platform == "win32":
        try:                                    # crisp text on scaled displays
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    root.withdraw()
    root.title("Weed Lines")
    ico = find_icon()
    if ico:
        try:
            root.iconbitmap(default=ico)
        except Exception:
            pass

    # 1. choose files
    if not files:
        start = START_DIR if os.path.isdir(START_DIR) else os.path.expanduser("~")
        files = list(filedialog.askopenfilenames(
            parent=root, title="Choose cake topper SVG file(s)", initialdir=start,
            filetypes=[("SVG files", "*.svg"), ("All files", "*.*")]))
        if not files:
            root.destroy()
            return

    # 2. check for earlier results before starting
    jobs = []
    for f in files:
        out_svg, out_png = outputs_for(f)
        if already_there(out_svg, out_png, a) and not a.overwrite:
            new_svg, new_png = numbered_pair(out_svg, out_png)
            ans = messagebox.askyesnocancel(
                "Weed Lines - file already exists",
                f"{os.path.basename(out_svg)} is already in this folder.\n\n"
                f"Yes:  replace it\n"
                f"No:  save as {os.path.basename(new_svg)}\n"
                f"Cancel:  skip {os.path.basename(f)}",
                icon="warning", parent=root)
            if ans is None:
                continue
            if ans is False:
                out_svg, out_png = new_svg, new_png
        jobs.append((f, out_svg, out_png))
    if not jobs:
        root.destroy()
        return

    # 3. progress window
    root.resizable(False, False)
    pad = {"padx": 18}
    frm = ttk.Frame(root, padding=(0, 16, 0, 16))
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="Weed Lines", font=("Segoe UI", 15, "bold")).pack(anchor="w", **pad)
    file_lbl = ttk.Label(frm, text="", font=("Segoe UI", 10))
    file_lbl.pack(anchor="w", pady=(2, 10), **pad)
    bar = ttk.Progressbar(frm, length=440, maximum=100, mode="determinate")
    bar.pack(**pad)
    status_lbl = ttk.Label(frm, text="Starting", foreground="#555")
    status_lbl.pack(anchor="w", pady=(6, 0), **pad)
    result_lbl = ttk.Label(frm, text="", justify="left", wraplength=440)
    result_lbl.pack(anchor="w", pady=(10, 0), **pad)
    btns = ttk.Frame(frm)
    btns.pack(anchor="e", pady=(14, 0), **pad)
    b_prev = ttk.Button(btns, text="Open preview", state="disabled")
    b_fold = ttk.Button(btns, text="Show in folder", state="disabled")
    b_close = ttk.Button(btns, text="Close", command=root.destroy)
    for b in (b_prev, b_fold, b_close):
        b.pack(side="left", padx=(8, 0))
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
    y = (root.winfo_screenheight() - root.winfo_reqheight()) // 3
    root.geometry(f"+{x}+{y}")
    root.deiconify()
    root.lift()

    q = queue.Queue()
    results, problems = [], []

    def worker():
        for i, (f, out_svg, out_png) in enumerate(jobs, 1):
            q.put(("file", f"File {i} of {len(jobs)}:  {os.path.basename(f)}" if len(jobs) > 1
                   else os.path.basename(f)))
            try:
                r = process(f, out_svg, out_png, a, lambda fr, m: q.put(("prog", fr, m)))
                q.put(("result", r))
            except Exception as e:
                q.put(("problem", f"{os.path.basename(f)}: {e}"))
        q.put(("done",))

    def finish():
        bar["value"] = 100
        lines = [f"{r['name']}:  {r['cuts']} weed cuts, {r['pieces']} pieces, "
                 f"{r['w']:.2f} x {r['h']:.2f} in" for r in results]
        lines += [f"Problem with {p}" for p in problems]
        if results:
            lines.append(f"\nSaved next to the original as {os.path.basename(results[-1]['svg'])}"
                         + (" and its preview." if results[-1]["png"] else "."))
        status_lbl.config(text="Finished" if not problems else "Finished, with problems")
        result_lbl.config(text="\n".join(lines))
        pngs = [r["png"] for r in results if r["png"]]
        if pngs:
            b_prev.config(state="normal", command=lambda: [open_file(p) for p in pngs])
        if results:
            b_fold.config(state="normal", command=lambda: show_in_folder(results[-1]["svg"]))
        b_close.focus_set()
        root.bind("<Return>", lambda e: root.destroy())
        root.bind("<Escape>", lambda e: root.destroy())

    def poll():
        try:
            while True:
                msg = q.get_nowait()
                kind = msg[0]
                if kind == "file":
                    file_lbl.config(text=msg[1])
                elif kind == "prog":
                    bar["value"] = msg[1] * 100
                    status_lbl.config(text=msg[2])
                elif kind == "result":
                    results.append(msg[1])
                elif kind == "problem":
                    problems.append(msg[1])
                elif kind == "done":
                    finish()
                    return
        except queue.Empty:
            pass
        root.after(80, poll)

    threading.Thread(target=worker, daemon=True).start()
    root.after(80, poll)
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Smart weeding lines for outlined vinyl lettering.")
    ap.add_argument("svg", nargs="*", help="Illustrator SVG(s) with outlined text; leave out to pick from a window")
    ap.add_argument("--margin", type=float, default=0.25, help="margin around the design, inches (0.25)")
    ap.add_argument("--amax", type=float, default=1.5, help="largest waste piece, square inches (1.5)")
    ap.add_argument("--emax", type=float, default=2.0, help="longest side of a waste piece, inches (2.0)")
    ap.add_argument("--amin", type=float, default=0.12, help="smallest piece a cut may create, sq in (0.12)")
    ap.add_argument("--lmax", type=float, default=0.6, help="preferred longest cut, inches (0.6)")
    ap.add_argument("--no-preview", action="store_true", help="skip the PNG preview")
    ap.add_argument("--overwrite", action="store_true", help="replace earlier results without asking")
    ap.add_argument("--console", action="store_true", help="use text output even when no file is given")
    a = ap.parse_args()
    if pyi_splash:
        pyi_splash.close()     # libraries are loaded; get the splash out of the way

    # A file named on the command line from a command prompt -> text output.
    # Double-click, drag-and-drop onto a --noconsole exe, or no file given -> window.
    if HAS_CONSOLE and (a.svg or a.console):
        files = a.svg
        if not files:
            sys.exit("No file given.")
        run_console(files, a)
    else:
        run_window(a.svg, a)


if __name__ == "__main__":
    main()
