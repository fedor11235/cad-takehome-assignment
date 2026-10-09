#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render an isometric shaded PNG from a tessellated OBJ (vertices + triangles).

Usage:
    python3 render_png.py <input.obj> <output.png> ["Title text"]

Headless (no display needed): uses the matplotlib "Agg" backend.
"""
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def load_obj(path):
    verts = []
    faces = []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                _, x, y, z = line.split()[:4]
                verts.append((float(x), float(y), float(z)))
            elif line.startswith("f "):
                idx = [int(p.split("/")[0]) - 1 for p in line.split()[1:]]
                if len(idx) >= 3:
                    faces.append(idx[:3])
    return np.array(verts), np.array(faces)


def main():
    obj_path = sys.argv[1]
    png_path = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else ""

    verts, faces = load_obj(obj_path)
    tris = verts[faces]  # (n, 3, 3)

    # simple lambert shading from a fixed light direction
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    normals = np.cross(v1 - v0, v2 - v0)
    lens = np.linalg.norm(normals, axis=1)
    lens[lens == 0] = 1.0
    normals = normals / lens[:, None]
    light = np.array([0.4, -0.5, 0.8])
    light = light / np.linalg.norm(light)
    shade = np.clip(np.abs(normals @ light), 0.25, 1.0)

    base = np.array([0.45, 0.55, 0.72])  # steel-blue
    colors = np.clip(base[None, :] * shade[:, None], 0, 1)
    colors = np.hstack([colors, np.ones((len(colors), 1))])

    fig = plt.figure(figsize=(9, 7), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    coll = Poly3DCollection(tris, facecolors=colors, edgecolors=(0, 0, 0, 0.08),
                            linewidths=0.2)
    ax.add_collection3d(coll)

    mins = verts.min(axis=0)
    maxs = verts.max(axis=0)
    ctr = (mins + maxs) / 2.0
    span = (maxs - mins).max() / 2.0 * 1.05
    ax.set_xlim(ctr[0] - span, ctr[0] + span)
    ax.set_ylim(ctr[1] - span, ctr[1] + span)
    ax.set_zlim(ctr[2] - span, ctr[2] + span)
    try:
        ax.set_box_aspect((1, 1, 1))
    except Exception:
        pass

    ax.view_init(elev=22, azim=-55)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=13)

    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight", facecolor="white")
    print("wrote %s" % png_path)


if __name__ == "__main__":
    main()
