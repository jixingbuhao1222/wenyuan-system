import os
import streamlit as st
from openai import OpenAI


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

    def generate_answer(self, prompt: str, context: str) -> str:
        """
        根据检索到的知识库上下文和用户问题，调用 DeepSeek 模型生成回答
        """
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",  # 对应 DeepSeek-V3 / 基础对话模型
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个专业的大学生学术助手与知识库问答系统。请严格根据下方提供的参考资料来回答用户的问题。"
                            "如果参考资料中没有包含答案，请明确告知用户无法从已知文献中找到相关信息，切勿胡编乱造。"
                            f"\n\n参考资料：\n{context}"
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ 调用 DeepSeek 大模型时发生错误: {str(e)}"