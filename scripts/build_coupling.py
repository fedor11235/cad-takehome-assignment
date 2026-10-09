#!/usr/bin/env freecadcmd
# -*- coding: utf-8 -*-
"""
Parametric rigid flange-coupling generator for FreeCAD 1.1.x.

Run headless:
    freecadcmd build_coupling.py -- <bolt_count> <out_dir> <tag>

Example:
    freecadcmd build_coupling.py -- 4 ../takehome/Before  input
    freecadcmd build_coupling.py -- 6 ../takehome/After   solution

It produces, in <out_dir>:
    flange_half.FCStd  bolt_m10.FCStd  nut_m10.FCStd   (parametric parts)
    <tag>.FCStd                                         (assembly, links the parts)
    <tag>.step                                          (portable AP214 export)
    <tag>.obj                                           (mesh, for PNG rendering)
    flange_half.step / bolt_m10.step / nut_m10.step     (portable parts)

The number of bolts is driven by the "bolt_count" alias in the parameter
spreadsheet of both the flange part and the assembly, so the model rebuilds
parametrically when that single value is changed.
"""
import os
import sys
import math

import FreeCAD as App
import Part
import Draft

# ----------------------------------------------------------------------------
# arguments
# ----------------------------------------------------------------------------
argv = App.ParamGet  # noqa  (ensure App imported)
raw = sys.argv
# freecadcmd passes script args after "--"
if "--" in raw:
    args = raw[raw.index("--") + 1:]
else:
    # fall back: last 3 tokens
    args = raw[-3:]

BOLT_COUNT = int(args[0])
OUT_DIR = os.path.abspath(args[1])
TAG = args[2]
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# master dimensions (mm) — the fixed design envelope
# ----------------------------------------------------------------------------
P = dict(
    bolt_count=BOLT_COUNT,
    flange_dia=140.0,
    flange_thk=18.0,
    hub_dia=80.0,
    hub_len=45.0,
    bore_dia=40.0,
    pcd=90.0,
    bolt_hole_dia=11.0,     # clearance hole for M10
    bolt_shank_dia=10.0,
    key_w=12.0,
    key_depth=3.3,          # depth into the bore wall (ISO key for d=40)
    head_af=17.0,           # M10 hex head across-flats
    head_h=6.4,             # M10 head height
    nut_af=17.0,
    nut_h=8.0,
)


def log(msg):
    App.Console.PrintMessage("[build] %s\n" % msg)


def hex_prism(across_flats, height):
    """A hexagonal prism solid, axis +Z, base on z=0, centred on origin."""
    r = across_flats / math.sqrt(3.0)      # circumradius from across-flats
    pts = []
    for i in range(6):
        a = math.radians(60 * i + 30)      # flat-to-flat oriented
        pts.append(App.Vector(r * math.cos(a), r * math.sin(a), 0))
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    return face.extrude(App.Vector(0, 0, height))


# ----------------------------------------------------------------------------
# PART 1 — flange half  (parametric, driven by its own spreadsheet)
# ----------------------------------------------------------------------------
def build_flange_doc():
    doc = App.newDocument("flange_half")

    sh = doc.addObject("Spreadsheet::Sheet", "params")
    rows = [
        ("bolt_count", P["bolt_count"]),
        ("flange_dia", P["flange_dia"]),
        ("flange_thk", P["flange_thk"]),
        ("hub_dia", P["hub_dia"]),
        ("hub_len", P["hub_len"]),
        ("bore_dia", P["bore_dia"]),
        ("pcd", P["pcd"]),
        ("bolt_hole_dia", P["bolt_hole_dia"]),
        ("key_w", P["key_w"]),
        ("key_depth", P["key_depth"]),
    ]
    for i, (name, val) in enumerate(rows, start=1):
        sh.set("A%d" % i, name)
        sh.set("B%d" % i, str(val))
        sh.setAlias("B%d" % i, name)
    doc.recompute()

    # flange plate (mating face on z=0, outer face on z=flange_thk)
    disc = doc.addObject("Part::Cylinder", "flange_plate")
    disc.setExpression("Radius", "params.flange_dia / 2")
    disc.setExpression("Height", "params.flange_thk")

    # hub behind the plate
    hub = doc.addObject("Part::Cylinder", "hub")
    hub.setExpression("Radius", "params.hub_dia / 2")
    hub.setExpression("Height", "params.hub_len")
    hub.setExpression(".Placement.Base.z", "params.flange_thk")

    body = doc.addObject("Part::MultiFuse", "body")
    body.Shapes = [disc, hub]

    # central bore (through plate + hub)
    bore = doc.addObject("Part::Cylinder", "bore")
    bore.setExpression("Radius", "params.bore_dia / 2")
    bore.setExpression("Height", "params.flange_thk + params.hub_len + 2")
    bore.Placement.Base.z = -1

    cut1 = doc.addObject("Part::Cut", "body_bored")
    cut1.Base = body
    cut1.Tool = bore

    # keyway slot at +Y, cut into the bore wall
    key = doc.addObject("Part::Box", "keyway")
    key.setExpression("Length", "params.key_w")
    key.setExpression("Width", "params.bore_dia / 2 + params.key_depth")
    key.setExpression("Height", "params.flange_thk + params.hub_len + 2")
    # centre the width (X) on 0, start at bore centre and go +Y
    key.setExpression(".Placement.Base.x", "-params.key_w / 2")
    key.Placement.Base.y = 0
    key.Placement.Base.z = -1

    cut2 = doc.addObject("Part::Cut", "body_keyed")
    cut2.Base = cut1
    cut2.Tool = key

    # one bolt hole on the PCD, at angle 0 (+X)
    hole0 = doc.addObject("Part::Cylinder", "bolt_hole")
    hole0.setExpression("Radius", "params.bolt_hole_dia / 2")
    hole0.setExpression("Height", "params.flange_thk + 2")
    hole0.setExpression(".Placement.Base.x", "params.pcd / 2")
    hole0.Placement.Base.z = -1
    doc.recompute()

    # polar array of the hole, count driven by params.bolt_count
    holes = Draft.make_polar_array(hole0, number=int(P["bolt_count"]),
                                   angle=360.0,
                                   center=App.Vector(0, 0, 0))
    holes.Label = "bolt_holes"
    # drive the count parametrically from the spreadsheet
    try:
        holes.setExpression("NumberPolar", "params.bolt_count")
    except Exception as exc:  # noqa
        log("could not bind NumberPolar expression: %s" % exc)
    # array about the Z axis
    try:
        holes.Axis = App.Vector(0, 0, 1)
    except Exception:
        pass
    doc.recompute()

    flange = doc.addObject("Part::Cut", "flange_half")
    flange.Base = cut2
    flange.Tool = holes
    doc.recompute()

    # tidy: keep only the final feature visible
    flange.Label = "flange_half"
    return doc, flange


# ----------------------------------------------------------------------------
# PART 2 — M10 bolt  (standard part; generic +Z pose, head on z=0)
# ----------------------------------------------------------------------------
def build_bolt_doc():
    doc = App.newDocument("bolt_m10")
    shank_len = 2 * P["flange_thk"] + P["nut_h"] + 6  # through both plates + nut + stick-out
    head = hex_prism(P["head_af"], P["head_h"])
    shank = Part.makeCylinder(P["bolt_shank_dia"] / 2.0, shank_len,
                              App.Vector(0, 0, P["head_h"]))
    bolt = head.fuse(shank)
    obj = doc.addObject("Part::Feature", "bolt_m10")
    obj.Shape = bolt
    obj.Label = "bolt_m10"
    doc.recompute()
    return doc, obj, shank_len


# ----------------------------------------------------------------------------
# PART 3 — M10 nut
# ----------------------------------------------------------------------------
def build_nut_doc():
    doc = App.newDocument("nut_m10")
    body = hex_prism(P["nut_af"], P["nut_h"])
    hole = Part.makeCylinder(P["bolt_shank_dia"] / 2.0, P["nut_h"] + 2,
                             App.Vector(0, 0, -1))
    nut = body.cut(hole)
    obj = doc.addObject("Part::Feature", "nut_m10")
    obj.Shape = nut
    obj.Label = "nut_m10"
    doc.recompute()
    return doc, obj


# ----------------------------------------------------------------------------
# ASSEMBLY — links the three part docs, bolts/nuts in a parametric polar array
# ----------------------------------------------------------------------------
def build_assembly(flange_obj, bolt_obj, nut_obj, shank_len):
    doc = App.newDocument(TAG)

    sh = doc.addObject("Spreadsheet::Sheet", "params")
    sh.set("A1", "bolt_count")
    sh.set("B1", str(P["bolt_count"]))
    sh.setAlias("B1", "bolt_count")
    sh.set("A2", "pcd")
    sh.set("B2", str(P["pcd"]))
    sh.setAlias("B2", "pcd")
    doc.recompute()

    # App::Link to external documents requires the owning document to be saved
    # first (so a relative path to the part files can be stored).
    doc.saveAs(os.path.join(OUT_DIR, "%s.FCStd" % TAG))

    ft = P["flange_thk"]

    # flange A — mating face on z=0, hub pointing +Z
    fa = doc.addObject("App::Link", "flange_A")
    fa.setLink(flange_obj)
    fa.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation())

    # flange B — mirror about the mating plane: rotate 180 deg about Y
    fb = doc.addObject("App::Link", "flange_B")
    fb.setLink(flange_obj)
    fb.Placement = App.Placement(App.Vector(0, 0, 0),
                                 App.Rotation(App.Vector(0, 1, 0), 180))

    # first bolt: head sits ON the +Z outer face (z = ft) and protrudes up,
    # shank goes -Z through both plates. Generic bolt is head@z0 + shank@+Z;
    # rotating 180 about X maps local z -> (base_z - z), so putting the base at
    # z = ft + head_h puts the head underside exactly on the face (z = ft).
    bolt_rot = App.Rotation(App.Vector(1, 0, 0), 180)
    bolt_pos = App.Vector(P["pcd"] / 2.0, 0, ft + P["head_h"])
    b0 = doc.addObject("App::Link", "bolt")
    b0.setLink(bolt_obj)
    b0.Placement = App.Placement(bolt_pos, bolt_rot)

    bolts = Draft.make_polar_array(b0, number=int(P["bolt_count"]),
                                   angle=360.0, center=App.Vector(0, 0, 0))
    bolts.Label = "bolts"
    try:
        bolts.setExpression("NumberPolar", "params.bolt_count")
    except Exception as exc:  # noqa
        log("assembly bolts NumberPolar expr failed: %s" % exc)
    try:
        bolts.Axis = App.Vector(0, 0, 1)
    except Exception:
        pass

    # first nut: on the -Z outer face (z = -ft), seated against it
    nut_pos = App.Vector(P["pcd"] / 2.0, 0, -ft - P["nut_h"])
    n0 = doc.addObject("App::Link", "nut")
    n0.setLink(nut_obj)
    n0.Placement = App.Placement(nut_pos, App.Rotation())

    nuts = Draft.make_polar_array(n0, number=int(P["bolt_count"]),
                                  angle=360.0, center=App.Vector(0, 0, 0))
    nuts.Label = "nuts"
    try:
        nuts.setExpression("NumberPolar", "params.bolt_count")
    except Exception as exc:  # noqa
        log("assembly nuts NumberPolar expr failed: %s" % exc)
    try:
        nuts.Axis = App.Vector(0, 0, 1)
    except Exception:
        pass

    doc.recompute()
    return doc, [fa, fb, bolts, nuts]


# ----------------------------------------------------------------------------
# export helpers
# ----------------------------------------------------------------------------
def collect_shapes(objs):
    shapes = []
    for o in objs:
        try:
            s = o.Shape
            if s and not s.isNull():
                shapes.append(s)
        except Exception as exc:  # noqa
            log("no shape for %s: %s" % (getattr(o, "Name", "?"), exc))
    return shapes


def export_step(shapes, path):
    comp = Part.makeCompound(shapes)
    comp.exportStep(path)
    log("wrote %s" % path)


def export_obj(shapes, path, deflection=0.5):
    """Write a simple OBJ from tessellated shapes (no materials)."""
    comp = Part.makeCompound(shapes)
    verts, faces = comp.tessellate(deflection)
    with open(path, "w") as f:
        f.write("# flange coupling %s\n" % TAG)
        for v in verts:
            f.write("v %.4f %.4f %.4f\n" % (v.x, v.y, v.z))
        for tri in faces:
            f.write("f %d %d %d\n" % (tri[0] + 1, tri[1] + 1, tri[2] + 1))
    log("wrote %s (%d verts, %d tris)" % (path, len(verts), len(faces)))


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    log("bolt_count=%d  out=%s  tag=%s" % (P["bolt_count"], OUT_DIR, TAG))

    fdoc, flange = build_flange_doc()
    bdoc, bolt, shank_len = build_bolt_doc()
    ndoc, nut = build_nut_doc()

    # save parts first so the assembly can reference them by file
    fpath = os.path.join(OUT_DIR, "flange_half.FCStd")
    bpath = os.path.join(OUT_DIR, "bolt_m10.FCStd")
    npath = os.path.join(OUT_DIR, "nut_m10.FCStd")
    fdoc.saveAs(fpath)
    bdoc.saveAs(bpath)
    ndoc.saveAs(npath)
    log("saved part files")

    # portable part STEPs
    flange.Shape.exportStep(os.path.join(OUT_DIR, "flange_half.step"))
    bolt.Shape.exportStep(os.path.join(OUT_DIR, "bolt_m10.step"))
    nut.Shape.exportStep(os.path.join(OUT_DIR, "nut_m10.step"))

    adoc, top_objs = build_assembly(flange, bolt, nut, shank_len)
    apath = os.path.join(OUT_DIR, "%s.FCStd" % TAG)
    adoc.saveAs(apath)
    log("saved assembly %s" % apath)

    shapes = collect_shapes(top_objs)
    if not shapes:
        log("WARNING: no shapes collected for export!")
    export_step(shapes, os.path.join(OUT_DIR, "%s.step" % TAG))
    export_obj(shapes, os.path.join(OUT_DIR, "%s.obj" % TAG))

    log("DONE")


main()
