"""Render the gravity-inversion GIF -> assets/dabic_inversion.gif.

Depth sweep through the 3D density model: TRUE salt-dome bodies vs the RECOVERED
model, next to the surface gravity anomaly that is the ONLY thing the inversion
sees. Reads outputs/viz/viz.npz (produced by a SimPEG inversion in the work
container — see scripts/_invert_for_viz.py).
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
    ap.add_argument("--out", default="assets/dabic_inversion.gif")
    a = ap.parse_args()

    d = np.load(a.npz)
    nx, ny, nz = [int(v) for v in d["shp"]]
    mt = d["m_true"].reshape((nx, ny, nz), order="F")
    mr = d["m_rec"].reshape((nx, ny, nz), order="F")
    zc = d["cc"][:, 2].reshape((nx, ny, nz), order="F")[0, 0, :]   # layer depths
    dobs = d["d_obs"].reshape((31, 41))                            # 31 x 41 station grid

    ext = [0, 4000, 0, 3000]
    order = np.argsort(zc)[::-1]         # shallow (z~0) -> deep
    frames = list(order) + list(order[::-1])   # ping-pong for a smooth loop

    plt.rcParams.update({"font.size": 10})
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.6))
    fig.suptitle("3D gravity inversion — synthetic salt-dome (EdgeBench dabic)", fontsize=12)

    im0 = ax[0].imshow(mt[:, :, 0].T, origin="lower", extent=ext, vmin=0, vmax=1,
                       cmap="magma", aspect="auto")
    im1 = ax[1].imshow(mr[:, :, 0].T, origin="lower", extent=ext, vmin=0, vmax=max(0.35, mr.max()),
                       cmap="magma", aspect="auto")
    ax[2].imshow(dobs, origin="lower", extent=ext, cmap="viridis", aspect="auto")
    ax[0].set_title("TRUE density"); ax[1].set_title("RECOVERED (from data →)")
    ax[2].set_title("surface gravity anomaly (input)")
    for k in (0, 1, 2):
        ax[k].set_xlabel("x (m)")
    ax[0].set_ylabel("y (m)")
    fig.colorbar(im0, ax=ax[0], fraction=0.046, pad=0.04)
    fig.colorbar(im1, ax=ax[1], fraction=0.046, pad=0.04)
    depth_txt = ax[1].text(0.5, 1.18, "", transform=ax[1].transAxes, ha="center",
                           fontsize=11, color="#c0392b", fontweight="bold")

    def update(k):
        im0.set_data(mt[:, :, k].T)
        im1.set_data(mr[:, :, k].T)
        depth_txt.set_text(f"depth ≈ {zc[k]:.0f} m")
        return im0, im1, depth_txt

    anim = FuncAnimation(fig, update, frames=frames, interval=350, blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    anim.save(a.out, writer=PillowWriter(fps=3))
    print(f"wrote {a.out} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
