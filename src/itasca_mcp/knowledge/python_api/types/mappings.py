"""Type system mappings for Itasca SDK.

This module defines mappings between PFC object classes and their
parent modules, used for generating official API paths.
"""

# Object class to module mapping
# Maps class names to their parent module names in Itasca Python SDK
# Format: "ClassName" -> "module_name" or "module.submodule"
# Official API path structure: itasca.{module}.{Class}.{method}
#
# Examples:
#   Ball -> ball module -> itasca.ball.Ball.vel()
#   Facet -> wall.facet module -> itasca.wall.facet.Facet.pos()
#   Vertex -> wall.vertex module -> itasca.wall.vertex.Vertex.pos()
#   Pebble -> clump.pebble module -> itasca.clump.pebble.Pebble.vel()
#   RBlock -> rblock module -> itasca.rblock.RBlock.vel()
#   RBlockTemplate -> rblock.template module -> itasca.rblock.template.RBlockTemplate.vol()
#
# Paths must exist on the live engine: itasca.wall has no Facet and itasca.clump
# no Pebble (both live one level down), so the shorter forms raise AttributeError.
#
# Note: Contact is NOT included here because it uses abstract path representation:
# keywords.json: itasca.contact.Contact.* (abstract)
# loader expands to: itasca.BallBallContact.*, itasca.BallFacetContact.*, etc. (concrete)
CLASS_TO_MODULE = {
    "Ball": "ball",
    "Clump": "clump",
    "Measure": "measure",
    "Wall": "wall",
    "Facet": "wall.facet",  # Facet is under wall.facet submodule
    "Vertex": "wall.vertex",  # Vertex is under wall.vertex submodule
    "Pebble": "clump.pebble",  # Pebble is under clump.pebble submodule
    "Template": "clump.template",  # Template is under clump.template submodule
    "RBlock": "rblock",  # RBlock is under rblock module
    "RBlockTemplate": "rblock.template",  # RBlock template object is under rblock.template submodule
}
