import os
import streamlit as st
from openai import OpenAI
from database import db_manager  # 完美引入底层向量数据库实例


class DeepSeekAgent:
    def __init__(self):
        # 1. 优先从 Streamlit 的 secrets.toml 中安全读取 API Key
        try:
            self.api_key = st.secrets["DEEPSEEK_API_KEY"]
        except Exception:
            # 2. 如果未配置 secrets，则尝试从系统环境变量中读取（本地调试兜底）
            self.api_key = os.getenv("DEEPSEEK_API_KEY", "")

        if not self.api_key:
            st.error("⚠️ 未检测到 DeepSeek API Key！请在项目根目录下创建 `.streamlit/secrets.toml` 文件并正确配置。")

        # 3. 初始化 DeepSeek 客户端（基于兼容的 OpenAI SDK 格式）
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

    def generate_chat_response(self, system_prompt: str, context: str, history: list, user_query: str) -> str:
        """
        核心对话逻辑：高度融合管理员配置、向量库检索上下文和历史对话流
        """
        try:
            # 动态拼接大模型的 System 指导语：融合后台配置的学术模版与私有向量知识库
            full_system_prompt = (
                f"{system_prompt}\n\n"
                f"【学术文献参考资料（来自学生上传的私有知识库）】:\n{context}\n\n"
                "请严格结合上述参考资料与你的学术背景进行回答。如果参考资料中不包含相关信息，请予以客观说明或进行正向学术引导，切勿胡编乱造。"
            )

            # 构建大模型标准的 messages 消息队列
            messages = [{"role": "system", "content": full_system_prompt}]

            # 顺次注入完整的历史会话上下文，让大模型拥有长文本记忆能力
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # 压入本次提问
            messages.append({"role": "user", "content": user_query})

            response = self.client.chat.completions.create(
                model="deepseek-chat",  # 对应 DeepSeek-V3 核心对话底座
                messages=messages,
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ 调用 DeepSeek 大模型时发生错误: {str(e)}"


# 实例化全局全局大模型代理实例
_agent = DeepSeekAgent()


def call_deepseek(system_prompt: str, top_k: int, user_query: str, history: list) -> str:
    """
    【高阶盘活桥梁】供学生端 s_tab1 调用的统一 RAG 大模型交互接口
    """
    context_segments = []
    try:
        # 1. 动态召回：利用 database.py 的 query 方法，根据管理员配置的 Top-K 捞取最相关的切片
        search_results = db_manager.query(query_texts=[user_query], n_results=int(top_k))

        # 提取 Chroma 返回的文本内容
        if search_results and "documents" in search_results and search_results["documents"]:
            context_segments = search_results["documents"][0]
    except Exception as e:
        # 容错处理：若数据库为空或未初始化，不阻断正常大模型对话
        pass

    # 拼装检索到的上下文内容
    if context_segments:
        context_text = "\n---\n".join([f"片段{idx + 1}: {text}" for idx, text in enumerate(context_segments)])
    else:
        context_text = "（当前学生未上传文献，或私有知识库中未检索到与该问题直接相关的文本片段）"

    # 2. 送入大模型生成最终的学术级安全答复
    return _agent.generate_chat_response(
        system_prompt=system_prompt,
        context=context_text,
        history=history,
        user_query=user_query
    )