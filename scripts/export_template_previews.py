"""Export authentic starter DOCX first pages for the template gallery.

Development utility only: requires Pillow, a DOCX renderer and LibreOffice.
Reads the local library API; never installs templates or modifies workspace data.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from PIL import Image, PngImagePlugin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--renderer", required=True)
    parser.add_argument("--output", default="frontend/public/template-previews")
    parser.add_argument("--embed-tool", help="Optional Impeccable launcher for embedded asset provenance")
    args = parser.parse_args()
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    with urlopen(base + "/api/template-library", timeout=20) as response:
        templates = json.load(response)["templates"]
    manifest = []
    with tempfile.TemporaryDirectory(prefix="docugen-preview-") as temporary:
        work = Path(temporary)
        for template in templates:
            key = template["id"]
            if not re.fullmatch(r"[a-z0-9-]+", key):
                raise ValueError("Unexpected template identifier")
            route = "/api/template-library/" + quote(key) + "/download"
            with urlopen(base + route, timeout=20) as response:
                content = response.read()
            source = work / (key + ".docx")
            source.write_bytes(content)
            output = work / key
            subprocess.run(
                [
                    sys.executable,
                    args.renderer,
                    str(source),
                    "--output_dir",
                    str(output),
                    "--width",
                    "420",
                    "--height",
                    "594",
                ],
                check=True,
                capture_output=True,
            )
            origin = (
                "First page rendered from the original Otterview DocuGen starter template "
                f"{key} ({template['name']}); source definition: quill/template_library.py; "
                f"download route: {route}; rendered with LibreOffice. No customer data or AI imagery."
            )
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("Source", origin)
            metadata.add_text("Description", origin)
            metadata.add_text("parameters", origin)
            with Image.open(output / "page-1.png") as image:
                image.convert("RGB").save(root / (key + ".png"), pnginfo=metadata, optimize=True)
            if args.embed_tool:
                subprocess.run(
                    [args.embed_tool, "embed-prompt", str(root / (key + ".png")), "--prompt", origin],
                    check=True,
                    capture_output=True,
                )
            manifest.append(
                {
                    "id": key,
                    "name": template["name"],
                    "origin": origin,
                    "docx_sha256": hashlib.sha256(content).hexdigest(),
                    "definition": template,
                }
            )
            print(key)
    (root / "provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
