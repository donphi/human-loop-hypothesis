# 🤖 Human-in-the-Loop for Automated Hypothesis Testing in Biobank Research

This repository supports the MSc research project by Donald Philp at the University of Westminster, School of Life Sciences. It forms part of the MSc in Artificial Intelligence and Digital Health. The objective is to build a modular, reproducible pipeline that automates hypothesis generation and validation using phenotypic extraction, graph-based retrieval, and AutoML—applied to UK Biobank data.

---

## 📁 Folder Structure

```bash
.
├── data_ingestion/          # 📄 PDF parsing and ingestion (GROBID, ScienceParse)
├── embeddings/              # 🧠 Embedding generation (PubMedBERT, NV-Embed v2)
├── vector_db/               # 🗃️ Vector DBs (Milvus, FAISS, Weaviate)
├── knowledge_graph/         # 🧬 Monarch Initiative integration, phenotype-disease linking
├── rag_pipeline/            # 🔁 RAG pipelines: vanilla, multi-head, graph-enhanced
├── automl_validation/       # 🤖 AutoML pipelines using PyCaret, H2O, scikit-learn
├── evaluation/              # 📊 Metrics: MAP, NDCG, Jaccard, Cohen’s Kappa
├── configs/                 # ⚙️ YAML configs, DB schema, environment settings
├── notebooks/               # 📓 Jupyter notebooks for analysis and validation
├── reports/                 # 📝 Research outputs and evaluation summaries
├── docker/                  # 🐳 Dockerfiles and compose files per process
├── thesis/                  # 📄 Final MSc thesis and research proposal (PDFs)
└── README.md                # 📘 This file
```

---

## 🎯 Project Scope

- 📚 Process and embed >6M PubMed articles for semantic retrieval  
- 🧪 Extract hypotheses and phenotype clusters from literature  
- 🧬 Link phenotypes to genes/diseases via biomedical knowledge graphs  
- 🧠 Use RAG pipelines and vector search for contextual relevance  
- 🤖 Validate outputs with AutoML tools and gold-standard comparisons  
- 📈 Deliver statistically sound and reproducible outcomes  

---

## 🛠️ Technologies Used

- **Embedding**: PubMedBERT, NVIDIA NV-Embed v2  
- **Chunking**: LangChain, LlamaIndex, Anthropic contextual chunking  
- **Vector Stores**: FAISS, Milvus, Weaviate  
- **RAG Frameworks**: LangChain RAG, custom Graph-RAG  
- **AutoML**: PyCaret, H2O AutoML, scikit-learn  
- **Evaluation**: Precision, Recall, MAP, NDCG, Cohen’s Kappa  
- **Infrastructure**: Docker, Compose, NVIDIA DGX (Grace Blackwell), CUDA, Ubuntu  

---

## 🧪 Reproducibility

Each module is isolated in its own container with dedicated `Dockerfile` and `docker-compose.yml` for environment consistency. This ensures that third parties can validate results and replicate experiments end-to-end with minimal setup.

---

## 📄 Academic Materials

PDFs for the final thesis and original research proposal are located in the `thesis/` directory.

---

## 🔒 License & Access

This work forms part of a confidential MSc submission. To request access or propose collaboration, contact [Donald Philp](https://github.com/donphi).