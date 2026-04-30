import pickle
import numpy as np
import faiss
import pandas as pd
import networkx as nx
from sentence_transformers import SentenceTransformer
import spacy
from pathlib import Path

# =========================
# Load artifacts (ONCE)
# =========================

ARTIFACTS_DIR = Path("artifacts")

# Load items
items = pd.read_pickle(ARTIFACTS_DIR / "items.pkl")

# Load embeddings
doc_embeddings = np.load(ARTIFACTS_DIR / "doc_embeddings.npy")

# Load FAISS index
index = faiss.read_index(str(ARTIFACTS_DIR / "faiss.index"))

# Load Knowledge Graph 
G = nx.read_graphml(ARTIFACTS_DIR / "knowledge_graph.graphml")

# Load models
embed_model = SentenceTransformer("all-mpnet-base-v2")
nlp = spacy.load("en_core_web_sm")

# =========================
# Graph-RAG retrieval
# =========================

def graph_rag_retrieve(query, top_k=5, kg_expand_k=5):
    # Embed query
    q_emb = embed_model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q_emb)

    # FAISS search
    D, I = index.search(q_emb, top_k)
    faiss_docs = [items.iloc[i] for i in I[0] if i != -1]

    # KG expansion
    doc = nlp(query)
    ents = set([ent.text.lower() for ent in doc.ents if len(ent.text) > 2])

    kg_docs = []
    for e in ents:
        node = f"concept_{e}"
        if node in G:
            neighbors = [
                n for n in G.neighbors(node)
                if G.nodes[n]["type"] == "item"
            ]
            for n in neighbors[:kg_expand_k]:
                cid = n.split("_", 1)[1]
                row = items[items["course_id"] == cid]
                if not row.empty:
                    kg_docs.append(row.iloc[0])

    # Merge + deduplicate
    all_docs = faiss_docs + kg_docs
    seen = set()
    merged = []

    for r in all_docs:
        cid = r["course_id"]
        if cid not in seen:
            merged.append(r)
            seen.add(cid)

    return merged

# =========================
# Prompt builder
# =========================

def build_rag_prompt(question: str, docs: list) -> str:
    context = "\n".join(
        f"- {d['doc_text']}" for d in docs[:3]
    )

    return f"""
Answer the question clearly and concisely.

Context:
{context}

Question:
{question}

Answer:
"""

    
import random

QUIZ_TEMPLATES = [
    "What best describes {topic}?",
    "Which statement about {topic} is correct?",
    "What is the main purpose of {topic}?"
]

def generate_quiz(topic: str, level: str):
    questions = []

    for template in QUIZ_TEMPLATES:
        q_text = template.format(topic=topic)

        questions.append({
            "question": q_text,
            "choices": [
                f"It introduces the basic concepts of {topic}",
                f"It focuses on advanced mathematics in {topic}",
                "It is mainly about hardware systems",
                "It is unrelated to artificial intelligence"
            ],
            "answer": f"It introduces the basic concepts of {topic}"
        })

    return questions


def mock_llm(prompt: str) -> str:
    if "machine learning" in prompt.lower():
        return "Machine learning is a field of artificial intelligence that allows systems to learn from data and improve their performance without being explicitly programmed."
    
    if "neural network" in prompt.lower():
        return "Neural networks are computational models inspired by the human brain, used to recognize patterns and solve complex problems like image and speech recognition."

    return "This topic involves key concepts in artificial intelligence. It focuses on learning from data and building intelligent systems."



