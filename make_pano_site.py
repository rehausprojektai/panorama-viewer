import os
import shutil
from pathlib import Path

# Base folder - where this script and your original images live
BASE_DIR = Path(__file__).resolve().parent

# All generated HTML + copied images will go into this folder
OUTPUT_DIR = BASE_DIR / "docs"  # changed from "site" to "docs"

# Image extensions to treat as panoramas
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Special filenames for the plan image (case insensitive)
PLAN_NAMES = {"plan.jpg", "plan.jpeg", "plan.png", "plan.webp"}


VIEWER_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.css">
  <script src="https://cdn.jsdelivr.net/npm/pannellum@2.5.6/build/pannellum.js"></script>
  <style>
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      background: #000;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #panorama {{
      width: 100%;
      height: 100%;
    }}
    #back-btn {{
      position: absolute;
      top: 15px;
      left: 15px;
      padding: 8px 14px;
      background: rgba(0,0,0,0.6);
      color: white;
      text-decoration: none;
      border-radius: 6px;
      font-size: 14px;
      z-index: 9999;
      backdrop-filter: blur(6px);
    }}
    #back-btn:hover {{
      background: rgba(0,0,0,0.85);
    }}
  </style>
</head>
<body>

  <a id="back-btn" href="index.html">Back</a>
  <div id="panorama"></div>

  <script>
    pannellum.viewer('panorama', {{
      type: 'equirectangular',
      panorama: '{image_filename}',
      autoLoad: true,
      showControls: true
    }});
  </script>

</body>
</html>
"""


INDEX_HEADER = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Panorama index</title>
  <style>
    :root {
      color-scheme: light;
    }
    body {
      margin: 0;
      padding: 40px 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f5f4;
      color: #1f1f1f;
    }
    .container {
      max-width: 900px;
      margin: 0 auto;
      padding: 32px 28px 36px;
      background: #ffffff;
      border-radius: 12px;
      box-shadow:
        0 0 0 1px rgba(15, 15, 15, 0.06),
        0 18px 45px rgba(15, 15, 15, 0.08);
    }
    h1 {
      font-size: 1.6rem;
      margin: 0 0 8px;
    }
    h2 {
      font-size: 1.1rem;
      margin: 24px 0 8px;
    }
    p {
      margin: 0 0 12px;
      line-height: 1.5;
    }
    .hint {
      font-size: 0.95rem;
      color: #6b6b6b;
      margin-bottom: 18px;
    }
    ol.pano-list {
      margin: 0 0 8px;
      padding-left: 20px;
    }
    ol.pano-list li {
      margin: 4px 0;
    }
    a {
      text-decoration: none;
      color: #2563eb;
    }
    a:hover {
      text-decoration: underline;
    }
    .plan-section {
      margin-top: 28px;
    }
    img.plan {
      max-width: 100%;
      max-height: 70vh;
      height: auto;
      display: block;
      margin: 10px auto 0;
      border-radius: 8px;
      border: 1px solid #e0e0e0;
      box-shadow:
        0 0 0 1px rgba(15, 15, 15, 0.03),
        0 8px 24px rgba(15, 15, 15, 0.06);
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Panorama index</h1>
"""


INDEX_FOOTER = """  </div>
</body>
</html>
"""


def safe_name(stem: str) -> str:
    """Convert a filename stem to something safe for an HTML file name."""
    safe = []
    for ch in stem:
        if ch.isalnum() or ch in ("-", "_"):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe)


def clean_output_dir(path: Path) -> None:
    """Remove everything inside OUTPUT_DIR and recreate it."""
    if path.exists():
        for item in path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        path.mkdir(parents=True, exist_ok=True)


def main():
    # Clean and recreate docs/ so it only contains fresh files
    clean_output_dir(OUTPUT_DIR)

    plan_image_src = None
    plan_image_dst_name = None
    images_src = []

    # Scan for images and separate plan image from panoramas
    for entry in BASE_DIR.iterdir():
        if entry.is_file() and entry.suffix.lower() in IMAGE_EXTS:
            lower_name = entry.name.lower()
            if lower_name in PLAN_NAMES:
                plan_image_src = entry
            else:
                images_src.append(entry)

    images_src.sort(key=lambda p: p.name.lower())

    if not images_src and not plan_image_src:
        print("No panorama or plan images found.")
        return

    index_items = []

    # Copy plan image into docs/ if present
    if plan_image_src:
        plan_image_dst_name = plan_image_src.name
        shutil.copy2(plan_image_src, OUTPUT_DIR / plan_image_dst_name)

    # Copy panorama images into docs/ and create viewer pages
    for img_src in images_src:
        stem = img_src.stem
        safe_stem = safe_name(stem)
        viewer_filename = f"view_{safe_stem}.html"

        # Destination image name (keep original name)
        img_dst_name = img_src.name
        shutil.copy2(img_src, OUTPUT_DIR / img_dst_name)

        html = VIEWER_TEMPLATE.format(
            title=stem,
            image_filename=img_dst_name,
        )

        viewer_path = OUTPUT_DIR / viewer_filename
        viewer_path.write_text(html, encoding="utf-8")

        index_items.append((stem, viewer_filename))

    # Build index.html inside docs/
    index_html_parts = [INDEX_HEADER]

    # Panorama list first, with Lithuanian hint text
    if index_items:
        index_html_parts.append(
            "<p class=\"hint\">Kad atidaryti vizualizacija paspauskite ant patalpos numerio is sio saraso.</p>\n"
        )
        index_html_parts.append("<h2>Panoramos</h2>\n")
        index_html_parts.append("<ol class=\"pano-list\">\n")
        for title, viewer_file in index_items:
            index_html_parts.append(
                f"  <li><a href=\"{viewer_file}\">{title}</a></li>\n"
            )
        index_html_parts.append("</ol>\n")

    # Plan image below the list
    if plan_image_dst_name:
        index_html_parts.append("<div class=\"plan-section\">\n")
        index_html_parts.append("<h2>Planas</h2>\n")
        index_html_parts.append(
            f"<img class=\"plan\" src=\"{plan_image_dst_name}\" alt=\"Plan\">\n"
        )
        index_html_parts.append("</div>\n")

    index_html_parts.append(INDEX_FOOTER)

    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text("".join(index_html_parts), encoding="utf-8")

    print("Generated site in:", OUTPUT_DIR)
    print()
    print("To view locally:")
    print(f"1. cd {BASE_DIR}")
    print("2. python -m http.server 8000")
    print("3. Open http://localhost:8000/docs/index.html in your browser")
    print()
    print("On GitHub Pages, set Source = main branch, Folder = /docs.")


if __name__ == "__main__":
    main()
