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


def _property_docs(
    category: str, item: str, item_doc: dict[str, Any], base_keywords: list[str]
) -> list[SearchDocument]:
    """One document per property of a model doc, named by its browse path ('contact-models linearpbond pb_ten').

    The keyword is kept whole as well as split: the tokenizer breaks 'pb_ten' into
    'pb' and 'ten', so only the whole name lets exact-name promotion find it.
    """
    docs: list[SearchDocument] = []
    for group in item_doc.get("property_groups") or []:
        if not isinstance(group, dict):
            continue
        for prop in group.get("properties", []):
            keyword = prop.get("keyword") if isinstance(prop, dict) else None
            if not keyword:
                continue
            path = f"{category} {item} {keyword}"
            description = " ".join(part for part in (_text(prop.get("description")), _text(prop.get("notes"))) if part)
            metadata: dict[str, Any] = {"category": category, "item": item, "property": keyword}
            if prop.get("since"):
                metadata["since"] = prop["since"]
            docs.append(
                SearchDocument(
                    name=path,
                    doc_type=DocumentType.REFERENCE,
                    title=path,
                    description=description or f"{keyword} property of {item}",
                    keywords=list(dict.fromkeys(base_keywords + [str(keyword).lower()] + _words(keyword))),
                    category=category,
                    syntax=path,
                    examples=[],
                    metadata=metadata,
                )
            )
    return docs


class ReferenceDocumentAdapter:
    """One document per reference item, one per sub-item of directory items (plot-items),
    and one per property of model docs that carry ``property_groups``."""

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
                own = _text(item.get("description"))
                if not own:
                    # range-elements indexes carry no description; the element's file does.
                    own = _text(
                        (ReferenceLoader.load_item_doc(category, name, software=software) or {}).get("description")
                    )
                description = " ".join(
                    part
                    for part in (
                        own,
                        _text(item.get("full_name")),
                        _text(item.get("common_use")),
                    )
                    if part
                )
                item_doc = ReferenceLoader.load_item_doc(category, name, software=software) or {}
                base_keywords = list(dict.fromkeys(_words(category) + _words(name) + _words(item.get("full_name"))))
                documents.append(
                    SearchDocument(
                        name=path,
                        doc_type=DocumentType.REFERENCE,
                        title=path,
                        description=description or cat_desc,
                        keywords=list(dict.fromkeys(base_keywords + _words(item_doc.get("search_keywords")))),
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
                documents.extend(_property_docs(category, name, item_doc, base_keywords))
                if not ReferenceLoader.is_directory_item(category, name, software=software):
                    continue
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
