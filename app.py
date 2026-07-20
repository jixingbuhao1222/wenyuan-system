import streamlit as st
from PDFparse import parse_and_chunk_pdf
from database import VectorDatabaseManager
from DeepSeekAPI import DeepSeekAgent
from plagiarism import PlagiarismEngine

# ==================== 1. 页面与初始化配置 ====================
st.set_page_config(page_title="文渊—大学生文献知识库与报告文档智能生成系统", page_icon="📚", layout="wide")

db_manager = VectorDatabaseManager()
llm_agent = DeepSeekAgent()
plagiarism_engine = PlagiarismEngine(db_manager)

st.title("📚 文渊—大学生文献知识库与报告文档智能生成系统")

# ==================== 2. 侧边栏：多文件上传与管理 ====================
with st.sidebar:
    st.header("📂 文献知识库管理")

    uploaded_files = st.file_uploader(
        "上传参考文献/PDF文件（支持多选）",
        type=["pdf"],
        accept_multiple_files=True,
        help="您可以同时选中并上传多个 PDF 文件"
    )

    if uploaded_files:
        current_file_names = sorted([f.name for f in uploaded_files])

        if "last_uploaded_files" not in st.session_state or st.session_state.last_uploaded_files != current_file_names:
            with st.spinner(f"正在批量解析 {len(uploaded_files)} 篇文献，构建向量知识库..."):
                db_manager.clear_collection()
                total_chunks = 0

                for file in uploaded_files:
                    chunks, ids, metadatas = parse_and_chunk_pdf(file)
                    db_manager.add_documents(chunks, ids, metadatas)
                    total_chunks += len(chunks)

                st.session_state.last_uploaded_files = current_file_names
                st.session_state.num_chunks = total_chunks

            st.success(f"🎉 成功！共解析 {len(uploaded_files)} 篇文献，切分 {total_chunks} 个知识片段！")

        st.markdown("---")
        st.markdown("**当前已加载的文献清单：**")
        for f in uploaded_files:
            st.text(f"📄 {f.name}")
    else:
        if "last_uploaded_files" in st.session_state:
            del st.session_state.last_uploaded_files
        st.info("请先上传至少一个 PDF 文件以构建知识库")

# ==================== 3. 主界面：多 Tab 功能区块 ====================
tab1, tab2, tab3 = st.tabs(["💬 智能问答与报告生成", "🔍 学术查重与一键降重", "📂 知识库管理"])

# === Tab 1: 智能问答与报告生成 ===
with tab1:
    st.subheader("💬 智能问答与报告生成")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("请输入你想查询的内容（支持跨文献检索与报告生成）..."):
        if not uploaded_files:
            st.warning("⚠️ 请先在左侧边栏上传至少一个文献文件，然后再发起提问！")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("正在跨多篇文献检索并呼叫 DeepSeek 大模型生成综合回答..."):
                    try:
                        search_results = db_manager.query(
                            query_texts=[prompt],
                            n_results=5
                        )

                        retrieved_chunks = search_results.get('documents', [[]])[0]
                        retrieved_metadatas = search_results.get('metadatas', [[]])[0]

                        if retrieved_chunks:
                            context_list = []
                            for chunk, meta in zip(retrieved_chunks, retrieved_metadatas):
                                source_name = meta.get('source', '未知文件')
                                context_list.append(f"[来源文件: {source_name}]\n{chunk}")

                            context = "\n\n-------------------\n\n".join(context_list)
                            response = llm_agent.generate_answer(prompt, context)
                        else:
                            response = "未能从上传的文献中检索到任何相关的知识片段。"

                    except Exception as e:
                        response = f"❌ 运行出错: {e}"

                st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})

# === Tab 2: 学术查重与一键降重 ===
with tab2:
    st.subheader("🛡️ AI 学术查重与智能降重引擎")

    col1, col2 = st.columns(2)

    with col1:
        user_input_text = st.text_area("请粘贴需要查重的报告段落或文章内容：", height=250,
                                       placeholder="在此输入或粘贴需要进行查重检测的文本...")
        style_choice = st.selectbox("选择降重润色风格：", ["学术严谨性", "通俗易懂", "精简冗余字数"])

        if st.button("🚀 开始本地查重", type="primary"):
            if not user_input_text.strip():
                st.warning("请输入需要检测的文本内容！")
            else:
                with st.spinner("正在基于私有知识库进行向量/文本相似度比对..."):
                    rate, segments = plagiarism_engine.check_similarity(user_input_text)
                    st.session_state.check_rate = rate
                    st.session_state.segments = segments
                    st.session_state.checked_text = user_input_text

    with col2:
        if "check_rate" in st.session_state:
            rate = st.session_state.check_rate
            if rate > 30:
                st.error(f"⚠️ 综合重复率：{rate}% （重复率偏高，建议进行降重）")
            else:
                st.success(f"🎉 综合重复率：{rate}% （重复率在安全范围内）")

            st.markdown("**🔍 重合片段详情：**")
            if st.session_state.segments:
                for seg in st.session_state.segments:
                    st.markdown(f"> 🔴 **相似度 {seg['similarity']}%**：`{seg['text']}`")

                if st.button("✨ 调用大模型一键智能降重"):
                    with st.spinner("正在通过 DeepSeek 进行学术语序重构与降重..."):
                        reduced_result = plagiarism_engine.reduce_weight(llm_agent, st.session_state.checked_text,
                                                                         style_choice)
                        st.session_state.reduced_result = reduced_result
            else:
                st.info("未检测到与私有知识库高度重合的片段。")

        if "reduced_result" in st.session_state:
            st.markdown("---")
            st.markdown("**💡 降重后优化文本：**")
            st.info(st.session_state.reduced_result)

# === Tab 3: 知识库管理 ===
with tab3:
    st.subheader("📂 知识库文件总览")
    if uploaded_files:
        st.write(f"当前已成功加载 {len(uploaded_files)} 篇文献：")
        for f in uploaded_files:
            st.markdown(f"- 📄 **{f.name}**")
    else:
        st.info("当前尚未上传任何文献文件，请在左侧边栏添加。")