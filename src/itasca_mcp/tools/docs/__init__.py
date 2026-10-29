"""Per-source implementations behind itasca_browse_doc / itasca_query_doc.

One module per documentation tree (``commands``, ``python_api``, ``fish``,
``reference``), each exposing ``browse()`` and ``search()``; the two registered
tools in the parent package only dispatch on ``source``.
"""
