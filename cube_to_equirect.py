import argparse
import os
import re
import html

import cv2
import py360convert


def find_cube_sets(base_dir):
    """
    Find all complete cube-face sets in base_dir.

    Expected JPG names look like:
      Scene431.jpg .. Scene436.jpg   -> base 'Scene43'
      Scene321.jpg .. Scene326.jpg   -> base 'Scene32'
      Scene211.jpg .. Scene216.jpg   -> base 'Scene21'
      Edit01.jpg  .. Edit06.jpg      -> base 'Edit0'
      pano131.jpg .. pano136.jpg     -> base 'pano13'
      pano91.jpg  .. pano96.jpg      -> base 'pano9'

    Rule:
      stem = filename without extension
      last character 1..6 = face index
      base = stem without last character
    """

    sets = {}

    for fname in os.listdir(base_dir):
        if not fname.lower().endswith(".jpg"):
            continue

        stem, _ = os.path.splitext(fname)
        if not stem:
            continue

        last = stem[-1]
        if last not in "123456":
            continue

        face_idx = int(last)
        base = stem[:-1]
        if not base:
            continue

        sets.setdefault(base, {})[face_idx] = fname

    complete_sets = {b: f for b, f in sets.items() if len(f) == 6}
    return complete_sets


def maybe_downscale_cube_faces(cube, max_dim=30000):
    """
    OpenCV remap has limits around 32767 for width/height.
    If any cube face is larger than max_dim in either dimension,
    uniformly downscale all faces so that the largest dimension is <= max_dim.
    """

    # compute maximum dimension among all faces
    max_side = 0
    for img in cube.values():
        h, w = img.shape[:2]
        max_side = max(max_side, h, w)

    if max_side <= max_dim:
        return cube  # nothing to do

    scale = float(max_dim) / float(max_side)
    print(f"  Cube faces too large (max side {max_side}), downscaling by factor {scale:.4f}")

    for key, img in cube.items():
        h, w = img.shape[:2]
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        cube[key] = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    return cube


def load_cube_faces(base_dir, faces_dict):
    """
    faces_dict is {1: 'Base1.jpg', ..., 6: 'Base6.jpg'}

    Orientation mapping (to match your SketchUp/Three.js setup):

      index 3 -> right  (+X) -> "R"
      index 1 -> left   (-X) -> "L"
      index 5 -> top    (+Y) -> "U"
      index 6 -> bottom (-Y) -> "D"
      index 4 -> +Z (was 'back' in three.js)  -> "F"
      index 2 -> -Z (was 'front' in three.js) -> "B"
    """

    def read(fname):
        path = os.path.join(base_dir, fname)
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {path}")
        return img

    cube = {
        "R": read(faces_dict[3]),
        "L": read(faces_dict[1]),
        "U": read(faces_dict[5]),
        "D": read(faces_dict[6]),
        "F": read(faces_dict[4]),
        "B": read(faces_dict[2]),
    }

    cube = maybe_downscale_cube_faces(cube)
    return cube


def extract_title_from_content(content):
    """
    Look for <h1>Title</h1> in HTML or JS content and return the inner text.
    """
    m = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    title = m.group(1)
    title = html.unescape(title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or None


def get_scene_title(base_dir, base):
    """
    Try to get the human-readable scene title from base.html or base.js.
    Fallback heuristics if nothing is found.
    """

    # 1. Look into HTML and JS for <h1>...</h1>
    for ext in (".html", ".js"):
        path = os.path.join(base_dir, base + ext)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                title = extract_title_from_content(content)
                if title:
                    return title
            except Exception:
                pass

    # 2. Fallback heuristics based on base name
    lower = base.lower()

    if lower.startswith("scene") and base[-1].isdigit():
        return f"Scene {base[-1]}"

    if lower.startswith("edit"):
        return "Edit"

    return base


def sanitize_title_for_filename(title):
    """
    Make a safe Windows filename from the scene title.
    Remove or replace characters not allowed in filenames.
    """

    disallowed = '<>:"/\\|?*'
    safe = "".join("_" if c in disallowed else c for c in title)
    safe = safe.strip().rstrip(". ")

    if not safe:
        safe = "panorama"

    return safe


def final_cleanup(base_dir, keep_files):
    """
    Delete everything in base_dir except:
      - files listed in keep_files
      - .py files
      - .bat files
    """

    print("\nPerforming final cleanup...")

    for fname in os.listdir(base_dir):
        path = os.path.join(base_dir, fname)

        if not os.path.isfile(path):
            continue

        if fname in keep_files:
            continue

        lower = fname.lower()
        if lower.endswith(".py") or lower.endswith(".bat"):
            continue

        try:
            os.remove(path)
            print(f"  Deleted: {fname}")
        except Exception as e:
            print(f"  Could not delete {fname}: {e}")

    print("Cleanup complete.\n")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Convert all SketchUp panorama cube-face sets "
            "(<Base>1.jpg .. <Base>6.jpg) into equirectangular panoramas "
            "with filenames based on the scene title, then clean the folder."
        )
    )
    parser.add_argument(
        "--width",
        type=int,
        default=4096,
        help="Output panorama width (height = width/2). Default 4096.",
    )
    parser.add_argument(
        "--indir",
        type=str,
        default=".",
        help="Directory containing exported JPGs. Default current directory.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Optional prefix for output filenames. Default empty (no prefix).",
    )

    args = parser.parse_args()

    base_dir = args.indir
    w = args.width
    if w >= 32000:
        print(f"Requested width {w} too large, clamping to 32000.")
        w = 32000
    h = w // 2
    prefix = args.prefix

    cube_sets = find_cube_sets(base_dir)
    if not cube_sets:
        print("No complete <Base>1..6.jpg cube sets found.")
        return

    print("Found cube sets for bases:")
    for b in sorted(cube_sets.keys()):
        print(f"  {b}")

    keep_files = set()

    for base, faces_dict in sorted(cube_sets.items(), key=lambda x: x[0]):
        print(f"\nProcessing base '{base}'...")

        # collect files that belong to this base, so we can protect them if processing fails
        base_related_files = set(faces_dict.values())
        for ext in (".html", ".js"):
            name = base + ext
            path = os.path.join(base_dir, name)
            if os.path.isfile(path):
                base_related_files.add(name)

        try:
            scene_title = get_scene_title(base_dir, base)
            safe_title = sanitize_title_for_filename(scene_title)
            out_name = f"{prefix}{safe_title}.jpg"
            out_path = os.path.join(base_dir, out_name)

            print(f"  Scene title: '{scene_title}' -> filename: '{out_name}'")

            cube = load_cube_faces(base_dir, faces_dict)

            equi = py360convert.c2e(cubemap=cube, h=h, w=w, cube_format="dict")
            ok = cv2.imwrite(out_path, equi)
            if not ok:
                raise RuntimeError(f"Failed to write output file: {out_path}")

            keep_files.add(out_name)
            print(f"  Saved equirectangular panorama: {out_name} ({w} x {h})")

        except Exception as e:
            print(f"  ERROR processing base '{base}': {e}")
            # protect all files for this base so cleanup will not delete them
            print("  Keeping original files for this base due to error.")
            keep_files.update(base_related_files)

    final_cleanup(base_dir, keep_files)

    print("\nAll done.")


if __name__ == "__main__":
    main()
