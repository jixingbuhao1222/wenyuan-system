from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class PlagiarismEngine:
    def __init__(self, db_manager):
        """传入数据库管理器以获取私有知识库内容"""
        self.db_manager = db_manager

    def check_similarity(self, target_text, threshold=0.5):
        """
        利用 TF-IDF 和余弦相似度算法进行行级/段落级查重
        """
        # 1. 获取向量数据库中的所有已知文献片段
        all_data = self.db_manager.collection.get()
        documents = all_data.get("documents", [])

        if not documents:
            return 0.0, []

        # 2. 将目标文本按行或短句切分进行细粒度比对
        sentences = [s.strip() for s in target_text.split("\n") if len(s.strip()) > 10]
        if not sentences:
            sentences = [target_text]

        matched_segments = []

        # 3. 计算文本相似度
        for sentence in sentences:
            corpus = documents + [sentence]
            try:
                vectorizer = TfidfVectorizer().fit_transform(corpus)
                vectors = vectorizer.toarray()

                sentence_vector = vectors[-1:]
                doc_vectors = vectors[:-1]

                similarities = cosine_similarity(sentence_vector, doc_vectors)[0]
                max_sim = max(similarities) if len(similarities) > 0 else 0

                # 如果相似度超过设定阈值（默认50%），判定为重合片段
                if max_sim >= threshold:
                    matched_segments.append({
                        "text": sentence,
                        "similarity": round(float(max_sim) * 100, 2)
                    })
            except Exception:
                continue

        # 计算整体综合重复率
        overall_rate = (len(matched_segments) / len(sentences)) * 100 if sentences else 0.0
        return round(overall_rate, 2), matched_segments

    def reduce_weight(self, llm_agent, text_to_reduce, style="学术严谨性"):
        """
        调用大模型对高重复度段落进行降重润色
        """
        prompt = f"""
        请作为学术润色专家，对以下高重复度的文本进行智能降重。
        要求：
        1. 保持原意不变，变换句式、替换同义词或重构学术语序，降低与现有文献的文本相似度。
        2. 润色风格偏向：{style}。
        3. 直接输出降重后的文本，不要包含多余的解释。

        待降重文本：
        {text_to_reduce}
        """

        response = llm_agent.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个严谨的学术论文降重与润色助手。"},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content