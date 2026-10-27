
import chromadb
from sentence_transformers import SentenceTransformer

from src.ai.fragmentation.indexer import (
    DB_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
)


class Retriever:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)

        self.client = chromadb.PersistentClient(
            path=DB_DIR
        )

        self.collection = self.client.get_collection(
            COLLECTION_NAME
        )

    def search(
        self,
        question: str,
        top_k: int = 4,
    ) -> list[dict]:
        if not question.strip():
            return []

        count = self.collection.count()

        if count == 0:
            return []

        query_embedding = self.model.encode(
            [question],
            normalize_embeddings=True,
        ).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )

        found = []

        for text, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            found.append({
                "text": text,
                "source": metadata["source"],
                "location": metadata["location"],
                "distance": distance,
            })

        return found


if __name__ == "__main__":
    retriever = Retriever()

    while True:
        question = input("\nВопрос (или exit): ")

        if question.lower() == "exit":
            break

        for item in retriever.search(question):
            print(
                f"\n[{item['source']}, "
                f"{item['location']}, "
                f"distance={item['distance']:.3f}]"
            )
            print(item["text"])