import argparse
import os
import sys
import tempfile
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


# ----------------------------
#  Clean / defringe (white bg)
# ----------------------------
def defringe_white_v2(
    png_in: str,
    png_out: str,
    bg: float = 255.0,
    a_low: float = 0.05,
    a_high: float = 0.95,
    strength: float = 1.0,
    erode_alpha_px: int = 0,
):
    im = Image.open(png_in).convert("RGBA")
    arr = np.array(im).astype(np.float32)

    rgb = arr[..., :3]
    a = arr[..., 3] / 255.0
    a_orig = a.copy()

    edge = (a > a_low) & (a < a_high)

    safe_a = np.clip(a, 1e-6, 1.0)
    fg = (rgb - bg * (1.0 - safe_a)[..., None]) / safe_a[..., None]
    fg = np.clip(fg, 0, 255)

    rgb_new = rgb.copy()
    rgb_new[edge] = (1.0 - strength) * rgb[edge] + strength * fg[edge]

    a_new = a_orig
    if erode_alpha_px > 0:
        a_new = a_new.copy()
        a_new[edge] = np.clip(a_new[edge] - (0.08 * erode_alpha_px), 0, 1)

    out = np.dstack([rgb_new, (a_new * 255.0)])
    Image.fromarray(out.astype(np.uint8), "RGBA").save(png_out)


# ----------------------------
#  GIMP discovery
# ----------------------------
def find_gimp_executable(user_path: str | None) -> str | None:
    if user_path:
        p = Path(user_path)
        if p.exists():
            return str(p)

    env_path = os.environ.get("GIMP_EXECUTABLE")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return str(p)

    for exe in ["gimp-console-3.0.exe", "gimp-console-2.10.exe", "gimp-console.exe", "gimp-3.exe", "gimp.exe"]:
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True)
            if r.returncode == 0:
                return exe
        except Exception:
            pass

    return None


def is_store_gimp(gimp_exec: str) -> bool:
    """
    GIMP installed from the Store (WindowsApps / gimp-3.exe)
    is NOT reliable for headless batch processing.
    """
    p = gimp_exec.lower()
    return "windowsapps" in p or p.endswith("gimp-3.exe")


def xcf_to_png(gimp_exec: str, xcf_path: Path, out_png: Path) -> None:
    # GIMP 3: uses gimp-file-save (save2 is not available in script-fu)
    # Note: the parameters of gimp-file-save can vary, but this form works in standard builds
    script = (
        f'(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "{xcf_path.as_posix()}" "{xcf_path.as_posix()}"))) '
        f'(drawable (car (gimp-image-merge-visible-layers image CLIP-TO-IMAGE)))) '
        f'(gimp-file-save RUN-NONINTERACTIVE image "{out_png.as_posix()}") '
        f'(gimp-image-delete image))'
    )

    cmd = [
        gimp_exec,
        "-i",
        "--batch-interpreter=plug-in-script-fu-eval",
        "-b",
        script,
        "--quit",
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise RuntimeError("GIMP export timeout (180s).")

    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)



SUPPORTED_RASTER = {".png", ".jpg", ".jpeg"}
SUPPORTED_ALL = SUPPORTED_RASTER | {".xcf"}


# ----------------------------
#  Main
# ----------------------------
def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(
        prog="rembg-clean",
        description="Batch background removal (rembg) + edge cleanup. PNG/JPG/JPEG + optional XCF via GIMP.",
    )
    ap.add_argument("folder", help="Input folder (recursive scan)")
    ap.add_argument("--out", default=None, help="Output folder (default: input)")
    ap.add_argument("--gimp", default=None, help="Override GIMP executable path")
    ap.add_argument("--model", default="isnet-general-use", help="rembg model")
    ap.add_argument("--strength", type=float, default=1.0, help="Clean strength 0..1")
    ap.add_argument("--erode", type=int, default=0, help="Alpha micro-erosion (0/1)")
    ap.add_argument("--a-low", type=float, default=0.05)
    ap.add_argument("--a-high", type=float, default=0.95)
    ap.add_argument("--skip-existing", action="store_true")

    args = ap.parse_args(argv)

    in_dir = Path(args.folder).resolve()
    if not in_dir.is_dir():
        print(f"[ERR] Invalid folder: {in_dir}")
        return 1

    out_dir = Path(args.out).resolve() if args.out else in_dir

    gimp_exec = find_gimp_executable(args.gimp)
    allow_xcf = False

    if gimp_exec:
        if is_store_gimp(gimp_exec):
            print("[WARN] Store GIMP detected (not headless-safe). .xcf files will be SKIPPED.")
        else:
            print(f"[INFO] Headless GIMP OK: {gimp_exec}")
            allow_xcf = True
    else:
        print("[INFO] GIMP not found: .xcf files will be SKIPPED.")

    print("[INFO] Starting rembg. On FIRST run it may seem frozen for a few minutes (numba compilation).")
    print("[INFO] To avoid the wait, you can set:  setx NUMBA_DISABLE_JIT 1")

    # LAZY IMPORT (freeze happens here the first time)
    from rembg import remove, new_session

    import time
    t0 = time.time()
    print("[INFO] Creating rembg model session (might download model if first time)...")
    session = new_session(args.model)
    print(f"[INFO] Session ready in {time.time()-t0:.1f}s")

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)

        files = [p for p in in_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_ALL]
        print(f"[INFO] Found {len(files)} files to process.")
        if not files:
            print("[INFO] No supported files found.")
            return 0

        for p in files:
            if p.suffix.lower() == ".xcf" and not allow_xcf:
                print(f"[SKIP] {p.name} (.xcf not supported in this configuration)")
                continue

            rel = p.relative_to(in_dir)
            out_name = p.stem + "_clean.png"
            out_path = out_dir / rel.parent / out_name

            if args.skip_existing and out_path.exists():
                print(f"[SKIP] {p.name} (already exists)")
                continue

            try:
                t0 = time.time()
                print(f"[INFO] Start file: {p.name}", flush=True)

                actual_input = p
                if p.suffix.lower() == ".xcf":
                    t = time.time()
                    exported = tmp_dir / (p.stem + "__xcf.png")
                    print(f"[INFO] Export XCF -> PNG: {p.name}", flush=True)
                    xcf_to_png(gimp_exec, p, exported)
                    print(f"[TIME] Export XCF: {time.time()-t:.2f}s", flush=True)
                    actual_input = exported

                t = time.time()
                print(f"[INFO] Reading input: {actual_input.name}", flush=True)
                with open(actual_input, "rb") as f:
                    data = f.read()
                print(f"[TIME] Read: {time.time()-t:.2f}s  (bytes={len(data)})", flush=True)

                t = time.time()
                print(f"[INFO] rembg remove(): {actual_input.name}", flush=True)
                out_bytes = remove(data, session=session)
                print(f"[TIME] rembg: {time.time()-t:.2f}s  (out={len(out_bytes)})", flush=True)

                t = time.time()
                tmp_cut = tmp_dir / (actual_input.stem + "__cut.png")
                with open(tmp_cut, "wb") as f:
                    f.write(out_bytes)
                print(f"[TIME] Write tmp: {time.time()-t:.2f}s", flush=True)

                t = time.time()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                defringe_white_v2(
                    png_in=str(tmp_cut),
                    png_out=str(out_path),
                    strength=args.strength,
                    erode_alpha_px=args.erode,
                    a_low=args.a_low,
                    a_high=args.a_high,
                )
                print(f"[TIME] Clean: {time.time()-t:.2f}s", flush=True)

                print(f"[OK] {p.name} -> {out_path.name}  (tot={time.time()-t0:.2f}s)", flush=True)

            except Exception as e:
                print(f"[ERR] {p.name}: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
