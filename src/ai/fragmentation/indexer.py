
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from src.ai.fragmentation.loaders import load_folder
from src.ai.fragmentation.chunking import chunk_documents


DATA_DIR = "materials"
DB_DIR = "storage/chroma"
COLLECTION_NAME = "study_materials"

EMBEDDING_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


def build_index():
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)

    print("Loading documents...")
    documents = load_folder(DATA_DIR)

    if not documents:
        raise ValueError(
            f"No readable documents found in {DATA_DIR}"
        )

    chunks = chunk_documents(documents)

    if not chunks:
        raise ValueError("No text chunks were produced")

    print(f"Documents/sections: {len(documents)}")
    print(f"Chunks: {len(chunks)}")

    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
    ).tolist()

    client = chromadb.PersistentClient(path=DB_DIR)

    # Учебный прототип: пересоздаём индекс целиком.
    # при каждом запуске старый индекс будет удалён.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    collection.add(
        ids=[f"chunk-{i}" for i in range(len(chunks))],
        documents=texts,
        embeddings=embeddings,
        metadatas=[
            {
                "source": chunk["source"],
                "location": chunk["location"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in chunks
        ],
    )

    print("Index created successfully!")


if __name__ == "__main__":
    build_index()


# запустить: python -m src.ai.fragmentation.indexer

'''
Этот код удаляет старую коллекцию и создаёт новую. Пока это удобно, но для реального приложения 
понадобится обновление индекса без потери остальных документов, удаление отдельных файлов и защита от дублирования чанков.
    
    Также модель embeddings должна быть одинаковой для индексирования документов и обработки запросов. 
Если поменять её, нужно заново пересчитать векторы всех чанков.
'''