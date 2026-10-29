"""Reference document adapter: reference items (models, range elements, plot items) as search documents."""

from __future__ import annotations

from typing import Any

from itasca_mcp.knowledge.models.document import DocumentType, SearchDocument
from itasca_mcp.knowledge.references.loader import ReferenceLoader


def _words(value: Any) -> list[str]:
    if isinstance(value, str):
        return [w for w in value.replace("-", " ").replace("_", " ").split() if w]
    if isinstance(value, list):
        return [w for v in value for w in _words(v)]
    return []


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_text(v) for v in value)
    return ""


class ReferenceDocumentAdapter:
    """One document per reference item, plus one per sub-item of directory items (plot-items)."""

    @staticmethod
    def load_all(*, software: str, version: str | None = None) -> list[SearchDocument]:
        documents: list[SearchDocument] = []
        index = ReferenceLoader.load_index(software=software)
        for category, cat_meta in index.get("categories", {}).items():
            cat_desc = cat_meta.get("description", "") if isinstance(cat_meta, dict) else ""
            for item in ReferenceLoader.get_item_list(category, version, software=software):
                name = item.get("name")
                if not name:
                    continue
                path = f"{category} {name}"
                description = " ".join(
                    part
                    for part in (
                        _text(item.get("description")),
                        _text(item.get("full_name")),
                        _text(item.get("common_use")),
                    )
                    if part
                )
                documents.append(
                    SearchDocument(
                        name=path,
                        doc_type=DocumentType.REFERENCE,
                        title=path,
                        description=description or cat_desc,
                        keywords=list(dict.fromkeys(_words(category) + _words(name) + _words(item.get("full_name")))),
                        category=category,
                        syntax=_text(item.get("syntax")) or path,
                        examples=[],
                        metadata={
                            "category": category,
                            "item": name,
                            "availability": item.get("availability"),
                            "full_name": item.get("full_name"),
                        },
                    )
                )
                if not ReferenceLoader.is_directory_item(category, name, software=software):
                    continue
                item_doc = ReferenceLoader.load_item_doc(category, name, software=software) or {}
                for sub in item_doc.get("sub_items", []):
                    sub_name = sub.get("name") if isinstance(sub, dict) else None
                    if not sub_name:
                        continue
                    sub_path = f"{path} {sub_name}"
                    documents.append(
                        SearchDocument(
                            name=sub_path,
                            doc_type=DocumentType.REFERENCE,
                            title=sub_path,
                            description=_text(sub.get("description")) or description,
                            keywords=list(dict.fromkeys(_words(category) + _words(name) + _words(sub_name))),
                            category=category,
                            syntax=sub_path,
                            examples=[],
                            metadata={"category": category, "item": name, "sub_item": sub_name},
                        )
                    )
        return documents
