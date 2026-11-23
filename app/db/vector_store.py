import chromadb

from ..config import get_settings


class VectorStore:
    """ChromaDB HTTP client used for semantic product retrieval."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = chromadb.HttpClient(
            host=settings.chroma_host, port=settings.chroma_port
        )
        self.collection = self.client.get_or_create_collection(
            name="surgical_products",
            metadata={"hnsw:space": "cosine"},
        )

    def index_product(self, product) -> None:
        if product.status != "approved":
            return

        document = (
            f"{product.canonical_name} | {product.category} | "
            f"{product.sterile_type} | {product.unit_of_measure} | "
            f"package qty {product.package_qty} | SKU {product.sku}"
        )
        metadata = {
            "sku": product.sku,
            "canonical_name": product.canonical_name,
            "category": product.category,
            "status": product.status,
            "stock_quantity": product.stock_quantity,
            "clinic_code": product.clinic_code,
        }

        existing = self.collection.get(ids=[str(product.id)])
        if existing["ids"]:
            self.collection.delete(ids=[str(product.id)])

        self.collection.add(
            ids=[str(product.id)],
            documents=[document],
            metadatas=[metadata],
        )

    def query(
        self, text: str, limit: int = 5, clinic_code: str | None = None
    ) -> list[dict]:
        kwargs = {
            "query_texts": [text],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if clinic_code:
            kwargs["where"] = {"clinic_code": clinic_code}

        results = self.collection.query(**kwargs)

        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metadata = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        matches: list[dict] = []
        for idx, doc, meta, distance in zip(ids, docs, metadata, distances):
            matches.append(
                {
                    "id": idx,
                    "document": doc,
                    "metadata": meta,
                    "distance": distance,
                }
            )
        return matches
