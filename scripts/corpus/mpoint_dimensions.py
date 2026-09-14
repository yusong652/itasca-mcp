"""What differs between MPoint3D and MPoint2D, measured on both binaries.

Batch 7 of the MPoint verification campaign. Everything the corpus recorded
before this was probed on ``mpoint3d9_gui.exe`` only, so every "absent" verdict
in it was really "absent in 3D" -- a distinction that first surfaced when
``zone create2d`` was recorded as missing. It is not missing: MPoint2D
enumerates ``create2D``, and the verdict was a statement about the binary rather
than about the product.

This module is the single source for the differences. The category generators
import it rather than each carrying their own copy, so a correction lands
everywhere at once.

Probed on MPoint2D 9.7 (2026-09-14) against the MPoint3D results already in the
corpus. The headline: the ``mpoint`` command family itself is *identical* --
same 28 subcommands -- so the command docs need no dimension gating. What
differs is the geometry vocabulary around it.
"""

# MPoint2D works in the x-y plane, not FLAC2D's x-z. Anything with a per-axis
# component drops its z variant rather than renaming it.
PLANE = {
    "mpoint2d": "x-y",
    "note": (
        "MPoint2D models the x-y plane: 'model domain extent' takes two pairs, and per-axis keywords "
        "are velocity-x / velocity-y with no z variant. This is not FLAC2D's x-z convention."
    ),
    "verified": "state -- 'mpoint fix ?' and 'mpoint node fix ?' on MPoint2D 9.7 list x and y only",
}

# Constitutive models: 2D exposes 39 of the 43.
CMODELS_3D_ONLY = ["columnar-basalt", "imass", "mohr-coulomb-tension", "orthotropic"]

# cavehoek is the awkward one: MPoint2D lists it, but assigning it demands
# 'model configure imass', and MPoint2D's configure has no imass option.
CMODELS_LISTED_BUT_UNREACHABLE_2D = {
    "cavehoek": (
        "Enumerated by 'mpoint cmodel assign' on MPoint2D and rejected when you try it: "
        "'Not configured for model cavehoek. See the MODEL CONFIG command.' But MPoint2D's "
        "'model configure' offers no 'imass' option, so there is no way to satisfy it. A dead entry in "
        "the 2D keyword table -- and a reminder that appearing in an enumeration is not the same as "
        "being usable."
    )
}

# model configure option lists differ substantially.
CONFIGURE_3D_ONLY = ["array", "cfd", "energy", "feblock", "highorder", "hotetra", "imass", "matrixflow"]
CONFIGURE_2D_ONLY = ["axisymmetry"]
CONFIGURE_2D_OPTIONS = [
    "axisymmetry",
    "cluster",
    "creep",
    "dynamic",
    "fluid-explicit",
    "fluid-flow",
    "fluid-implicit",
    "mechanical",
    "thermal",
]

# Range elements, restricted to the 22 this corpus documents.
RANGE_3D_ONLY = ["sphere", "cylinder", "position-z"]
RANGE_2D_ONLY = {
    "circle": {
        "syntax": "circle center <v> radius <f>",
        "description": "The 2D counterpart of 'sphere'. MPoint2D has no 'sphere' or 'cylinder'.",
        "verified": (
            "state -- 'range circle center (0,0) radius 0.5' selected 4 of 36 points on a 0.4-spaced "
            "lattice, exactly the four at distance 0.283 from the origin"
        ),
    }
}

# Plot items: the same six types exist in both, with a systematic keyword split.
PLOT_KEYWORDS_3D_ONLY = ["clip", "cut", "quality", "transparency"]
PLOT_KEYWORDS_2D_ONLY = ["spheres"]
PLOT_2D_ONLY_APPLIES_TO = ["mpoint", "mpoint-hybrid", "meshpoint"]
PLOT_KEYWORD_NOTE = (
    "The split is systematic rather than per-item: 'clip', 'cut', 'quality' and 'transparency' are 3D "
    "rendering concepts and are absent from every MPoint item type in 2D, while 'spheres' is how 2D "
    "draws point entities and appears only on the point items ('mpoint', 'mpoint-hybrid', 'meshpoint'), "
    "not the vector ones. 'mpoint-tensor' has an identical keyword set in both."
)

# FISH intrinsics: 100 in 3D, 92 in 2D, and the difference is exactly the
# z-component accessors of the VECTOR quantities. The tensor accessors keep all
# six components in 2D, because stress and strain stay full 3D tensors even in a
# two-dimensional model -- mpoint.stress.zz is meaningful there.
FISH_3D_ONLY = [
    "mpoint.disp.z",
    "mpoint.force.app.z",
    "mpoint.node.disp.z",
    "mpoint.node.force.unbal.z",
    "mpoint.node.pos.z",
    "mpoint.node.vel.z",
    "mpoint.pos.z",
    "mpoint.vel.z",
]
FISH_NOTE = (
    "MPoint2D exposes 92 of the 100 'mpoint.*' intrinsics; nothing is 2D-only. The eight that go are "
    "the z components of the vector accessors (position, displacement, velocity, applied force, "
    "unbalanced force). The TENSOR accessors are unchanged -- 'mpoint.stress.zz' and "
    "'mpoint.strain.xz' exist in 2D, because stress and strain remain full 3D tensors there."
)

# Demo-mode ceilings differ, and the pattern explains itself.
DEMO_LIMITS_BY_DIMENSION = {
    "zones": {"mpoint3d": 1000, "mpoint2d": 1000},
    "material_points": {"mpoint3d": 8000, "mpoint2d": 4000},
    "explanation": (
        "The material-point allowance is the zone allowance times the points one zone converts to: a 3D "
        "hexahedron yields 8, a 2D quadrilateral yields 4. Both ceilings therefore sit exactly where a "
        "full 1000-zone model lands after 'mpoint import from-zones' -- 1000 3D zones gave 8000 points "
        "and 1000 2D zones gave 4000, each assigning a constitutive model without complaint. The demo "
        "appears to be sized so the whole zone-import workflow runs."
    ),
    "evidence_2d": "3969 points assigned fine; 4096 failed. Zones: 1000 fine, 1040 failed.",
    "evidence_3d": "8000 assigned fine (4/4) and ran 30000 cycles; 8400 failed. Zones: 1000 fine, 1100 failed.",
}

DIMENSION_VERIFICATION = {
    "grade": "state",
    "engines": ["MPoint3D 9.7", "MPoint2D 9.7"],
    "date": "2026-09-14",
    "method": (
        "Re-ran the enumeration probes from Batches 2-6 against the 2D binary and executed the "
        "differences in both directions -- confirming that each 2D-only keyword works in 2D and each "
        "3D-only keyword is rejected there."
    ),
    "identical": (
        "The 'mpoint' command family is the same in both: 28 subcommands, letter for letter. So are "
        "the 'mpoint initialize' field list (25 entries) and the six plot item type names. The command "
        "docs need no dimension gating; only the geometry vocabulary around them differs."
    ),
    "resolved": (
        "'zone create2d' was recorded in Batch 1 as absent from MPoint. It is present on MPoint2D "
        "(spelled 'create2D' in the keyword table). The original verdict described the 3D binary, not "
        "the product -- which is what prompted this pass."
    ),
    "traps": [
        "Probing with '?' is NOT side-effect free. 'mpoint generate ?' generated 144 material points "
        "and then printed the keyword list. Any command that can run with no arguments will run before "
        "it answers. Probe on a model you are willing to lose.",
        "An entry in an enumeration is not a usable feature: MPoint2D lists 'cavehoek' among its "
        "constitutive models but offers no way to configure for it.",
    ],
}
