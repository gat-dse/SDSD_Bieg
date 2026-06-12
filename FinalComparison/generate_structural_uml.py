"""Generate the structural UML without requiring Graphviz."""

from pathlib import Path
import subprocess


OUTPUT_DIR = Path("diagrams")
PUML_FILE = OUTPUT_DIR / "classes_SDSD_structural.puml"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    subprocess.run(
        [
            "pyreverse",
            "-o", "puml",
            "-p", "SDSD_structural",
            "-d", str(OUTPUT_DIR),
            "--colorized",
            "struct_analysis.py",
        ],
        check=True,
    )
    text = PUML_FILE.read_text(encoding="utf-8")
    first_line, remainder = text.split("\n", 1)
    PUML_FILE.write_text(
        f"{first_line}\n!pragma layout smetana\n{remainder}",
        encoding="utf-8",
    )
    print(f"Created {PUML_FILE}")


if __name__ == "__main__":
    main()
