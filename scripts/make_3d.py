"""Render a rotating 3D view of the density volume -> assets/dabic_3d.gif.

The density model is a 3D grid (x, y, depth), so show it as an actual 3D plot:
TRUE salt-dome bodies vs the SimPEG-RECOVERED density, as voxel-ish point clouds
in space, rotating. Reads outputs/viz/viz.npz.
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default="outputs/viz/viz.npz")
    ap.add_argument("--out", default="assets/dabic_3d.gif")
    a = ap.parse_args()

    d = np.load(a.npz)
    cc = d["cc"]                      # (nCells, 3): x, y, depth(z<0)
    mt, mr = d["m_true"], d["m_rec"]
    x, y, z = cc[:, 0], cc[:, 1], cc[:, 2]

    t_mask = mt > 0.5
    r_thresh = 0.18
    r_mask = mr > r_thresh

    plt.rcParams.update({"font.size": 10, "figure.dpi": 88})
    fig = plt.figure(figsize=(10, 4.4))
    axT = fig.add_subplot(1, 2, 1, projection="3d")
    axR = fig.add_subplot(1, 2, 2, projection="3d")
    fig.suptitle("3D gravity inversion — salt-dome density volume (EdgeBench dabic)", fontsize=12)

    def style(ax, title):
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_zlabel("depth (m)")
        ax.set_xlim(0, 4000); ax.set_ylim(0, 3000); ax.set_zlim(z.min(), 0)
        ax.set_box_aspect((4, 3, 2))

    axT.scatter(x[t_mask], y[t_mask], z[t_mask], c="#e74c3c", marker="s", s=26,
                alpha=0.85, edgecolors="none")
    style(axT, f"TRUE bodies  (n={t_mask.sum()})")
    sc = axR.scatter(x[r_mask], y[r_mask], z[r_mask], c=mr[r_mask], cmap="magma",
                     marker="s", s=26, alpha=0.7, edgecolors="none")
    style(axR, f"RECOVERED  (density > {r_thresh})")
    fig.colorbar(sc, ax=axR, fraction=0.03, pad=0.08, label="recovered density")

    def update(k):
        az = (k * 12) % 360
        axT.view_init(elev=18, azim=az)
        axR.view_init(elev=18, azim=az)
        return ()

    anim = FuncAnimation(fig, update, frames=30, interval=140, blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    anim.save(a.out, writer=PillowWriter(fps=10))
    print(f"wrote {a.out}  (true n={t_mask.sum()}, recovered n={r_mask.sum()})")


if __name__ == "__main__":
    main()
