import re

SKILL_ALIASES = {
    "rag": "retrieval augmented generation",
    "vector db": "vector database",
    "vector search": "vector database",
    "semantic search": "information retrieval",
    "semantic retrieval": "information retrieval",
    "llm": "large language models",
    "llms": "large language models",
    "gen ai": "generative ai",
    "genai": "generative ai",
    "sentence-transformers": "embeddings",
    "llamaindex": "retrieval augmented generation",
    "langchain": "retrieval augmented generation",
    "pinecone": "vector database",
    "milvus": "vector database",
    "qdrant": "vector database",
    "weaviate": "vector database",
    "faiss": "approximate nearest neighbor",
    "ann search": "approximate nearest neighbor",
    "opensearch": "hybrid search",
    "elastic search": "hybrid search",
    "elasticsearch": "hybrid search",
    "bm25": "hybrid search",
    "ranker": "ranking systems",
    "ranking": "ranking systems",
    "recommendation": "recommendation systems",
    "recommender systems": "recommendation systems",
    "recommenders": "recommendation systems",
    "learning to rank": "learning-to-rank",
    "ltr": "learning-to-rank",
    "ndcg": "ranking evaluation",
    "mrr": "ranking evaluation",
    "map": "ranking evaluation",
    "ab testing": "a/b testing",
    "a/b tests": "a/b testing",
    "python3": "python",
    "py": "python",
    "mlops": "ml ops",
    "machine learning operations": "ml ops",
    "search relevance": "ranking systems",
    "relevance engineering": "ranking systems",
    "personalization": "recommendation systems",
    "candidate matching": "ranking systems",
    "entity matching": "information retrieval",
    "dense retrieval": "information retrieval",
    "sparse retrieval": "information retrieval",
    "cross encoder": "ranking systems",
    "cross-encoder": "ranking systems",
    "reranker": "ranking systems",
    "re-ranker": "ranking systems",
    "reranking": "ranking systems",
    "re-ranking": "ranking systems",
    "xgboost ranker": "learning-to-rank",
    "lambda mart": "learning-to-rank",
    "lambdamart": "learning-to-rank",
    "lightgbm ranker": "learning-to-rank",
    "click model": "ranking evaluation",
    "ab test": "a/b testing",
}

CORE_AI_SKILLS = {
    "embeddings", "vector database", "retrieval augmented generation", 
    "information retrieval", "large language models", "generative ai",
    "nlp", "natural language processing", "approximate nearest neighbor",
    "hybrid search", "ranking systems", "ranking evaluation",
    "recommendation systems", "learning-to-rank", "python"
}

def normalize_skill(skill_name):
    """Normalize a skill name to its canonical form."""
    if not skill_name:
        return ""
    s = skill_name.lower().strip()
    return SKILL_ALIASES.get(s, s)

def normalize_text(text):
    if not text:
        return ""
    # Strip special chars but keep spaces and alphanumerics
    text = re.sub(r'[^a-zA-Z0-9\s.,-]', '', text)
    return text.strip()
