import chromadb

class VectorDatabaseManager:
    def __init__(self, db_path="./my_knowledge_base"):
        """初始化本地 Chroma 客户端与集合"""
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="papers")

    def clear_collection(self):
        """清空向量数据库中的所有旧数据"""
        try:
            existing_ids = self.collection.get()["ids"]
            if existing_ids:
                self.collection.delete(ids=existing_ids)
        except Exception:
            pass

    def add_documents(self, chunks, ids, metadatas):
        """批量写入文档片段"""
        if chunks:
            self.collection.add(
                documents=chunks,
                ids=ids,
                metadatas=metadatas
            )

    def query(self, query_texts, n_results=5):
        """根据用户问题进行向量相似度检索"""
        return self.collection.query(
            query_texts=query_texts,
            n_results=n_results
        )

# 【核心桥梁】在此处直接实例化管理器，方便其他文件直接 import 共享同一个数据库连接
db_manager = VectorDatabaseManager()