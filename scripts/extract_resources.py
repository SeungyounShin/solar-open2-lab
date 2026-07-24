"""Stage the reference files Solar reads, straight from the public EdgeBench images.

Pulls nothing new — assumes the images are already `docker pull`ed. Extracts the
task README, starter.py, both papers (converted PDF->txt), and the judge source
into resources/ (gitignored — copyrighted / ByteDance-owned, not ours to commit).

Run:  python scripts/extract_resources.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RES = REPO / "resources"
WORK = "seededge/edgebench.work.dabic_gravity_inversion:85db0aba8a5f"
JUDGE = "seededge/edgebench.judge.dabic_gravity_inversion:517eb738b87b"
TASK = "/home/workspace/dabic_gravity_vinton"


def extract(image: str, container_path: str, dest: Path):
    """Copy a file out of an image via an in-container root `tar`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    parent, name = container_path.rsplit("/", 1)
    p = subprocess.run(
        ["docker", "run", "--rm", "--user", "0", "--entrypoint", "tar", "--platform", "linux/amd64",
         image, "-C", parent, "-cf", "-", name],
        capture_output=True, timeout=300)
    if p.returncode != 0:
        print(f"  ! failed {container_path}: {p.stderr.decode()[:200]}"); return
    import tarfile, io
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
        member = tf.getmember(name)
        with tf.extractfile(member) as f:
            dest.write_bytes(f.read())
    print(f"  ✓ {dest.name}")


def pdf_to_txt(pdf: Path, txt: Path):
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pip install pypdf first")
    r = PdfReader(str(pdf))
    txt.write_text("\n".join((pg.extract_text() or "") for pg in r.pages))
    print(f"  ✓ {txt.name} ({len(r.pages)} pages)")


def main():
    RES.mkdir(exist_ok=True)
    print("Extracting task refs from work image...")
    extract(WORK, f"{TASK}/starter/README.md", RES / "task_README.md")
    extract(WORK, f"{TASK}/starter/starter.py", RES / "starter.py")
    for pdf in ("geo20250233", "Xu2025_HMC"):
        extract(WORK, f"{TASK}/docs/{pdf}.pdf", RES / f"{pdf}.pdf")
        pdf_to_txt(RES / f"{pdf}.pdf", RES / f"paper_{pdf}.txt")
    print("Extracting judge source from judge image...")
    extract(JUDGE, "/opt/evaluator/eval_dabic_v2.py", RES / "JUDGE_eval_dabic_v2.py")
    print(f"\nDone -> {RES}")


if __name__ == "__main__":
    main()
