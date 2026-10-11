import os

from langchain_chroma import Chroma
from langchain_community.document_loaders import (DirectoryLoader, Docx2txtLoader,
                                                  PyPDFLoader, TextLoader)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (CHROMA_DIR, CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION_NAME,
                        DOCS_DIR, EMBEDDING_MODEL, TOP_K)


# ---------- 1. load the documents (pdf, txt, docx) ----------
def load_documents() -> list:
    docs_dir = str(DOCS_DIR)
    documents = []
    documents += DirectoryLoader(docs_dir, glob="**/*.pdf", loader_cls=PyPDFLoader).load()
    documents += DirectoryLoader(docs_dir, glob="**/*.txt", loader_cls=TextLoader,
                                 loader_kwargs={"encoding": "utf-8"}).load()
    documents += DirectoryLoader(docs_dir, glob="**/*.docx", loader_cls=Docx2txtLoader).load()
    return documents


# ---------- 2. split into chunks ----------
def split_documents(documents: list) -> list:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return splitter.split_documents(documents)


# ---------- 3. embeddings + ChromaDB ----------
_embeddings = None          # filled the first time it is needed


def get_embeddings():
    """Load the embedding model once and reuse it (loading takes a few seconds)."""
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def get_vector_db() -> Chroma:
    """Open the saved ChromaDB (creates an empty one if it does not exist yet)."""
    return Chroma(collection_name=COLLECTION_NAME,
                  persist_directory=str(CHROMA_DIR),
                  embedding_function=get_embeddings())


def build_index() -> int:
    """Rebuild the index from scratch. Returns the number of chunks stored."""
    documents = load_documents()
    if not documents:
        raise ValueError(f"No pdf/txt/docx files found in {DOCS_DIR}")
    chunks = split_documents(documents)

    get_vector_db().delete_collection()             # clear old chunks -> no duplicates
    Chroma.from_documents(documents=chunks, embedding=get_embeddings(),
                          collection_name=COLLECTION_NAME,
                          persist_directory=str(CHROMA_DIR))
    return len(chunks)


# ---------- 4. retrieval ----------
def retrieve(query: str, k: int = TOP_K) -> list:
    """Return the k most similar chunks as [{text, source, score}]."""
    db = get_vector_db()
    if not db.get(limit=1)["ids"]:                  # empty store -> build it first
        build_index()
        db = get_vector_db()
    results = db.similarity_search_with_score(query, k=k)
    return [{"text": doc.page_content,
             "source": os.path.basename(doc.metadata.get("source", "unknown")),
             "score": round(float(score), 4)}        # lower score = closer match
            for doc, score in results]


def retrieve_context(question: str, top_k: int = TOP_K) -> str:
    """Same job as your Topkretriver, but it RETURNS the context string."""
    return "\n\n".join(["text"])