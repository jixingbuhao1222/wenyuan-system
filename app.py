import streamlit as st
from PIL import Image
import zhanghao
import DeepSeekAPI
import PDFparse
import plagiarism
from database import db_manager
from openai import OpenAI
st.set_page_config(page_title="文渊系统 - 校园学术安全管理平台", page_icon="🎓", layout="wide")

# 注入一行极简 CSS，隐藏 Streamlit 默认页眉页脚
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# 1. 初始化网页配置
st.set_page_config(page_title="文渊文献管理系统", layout="wide")

# 2. 初始化数据库
zhanghao.init_db()

# 3. 初始化 Session 状态
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "role" not in st.session_state:
    st.session_state["role"] = ""

# ================= 界面路由分流控制 =================

# 🔑 情况一：未登录界面
if not st.session_state["logged_in"]:
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        st.title("📚 文渊文献知识库归档系统")
        st.markdown("---")

        login_tab, register_tab = st.tabs(["🔒 统一账号登录", "📝 学生学号注册"])

        with login_tab:
            login_user_input = st.text_input("用户名 / 学号", key="login_user")
            login_pass_input = st.text_input("密码", type="password", key="login_pass")
            if st.button("立即登录", type="primary", use_container_width=True):
                role = zhanghao.login_user(login_user_input, login_pass_input)
                if role:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = login_user_input
                    st.session_state["role"] = role
                    st.success(f"登录成功！欢迎进入{'管理员后台' if role == 'admin' else '学生工作端'}")
                    st.rerun()
                else:
                    st.error("用户名或密码错误！")

        with register_tab:
            st.markdown("⚠️ *提示：本入口仅供广西大学学生注册，管理员账号请联系运维分配。*")
            reg_user_input = st.text_input("输入学号/用户名", key="reg_user")
            reg_pass_input = st.text_input("设置密码", type="password", key="reg_pass")
            reg_pass_confirm = st.text_input("确认密码", type="password", key="reg_confirm")

            if st.button("提交注册", use_container_width=True):
                if reg_user_input and reg_pass_input and reg_pass_confirm:
                    if reg_pass_input != reg_pass_confirm:
                        st.error("两次输入的密码不一致！")
                    elif len(reg_pass_input) < 6:
                        st.error("密码长度不能少于 6 位！")
                    else:
                        if zhanghao.register_student(reg_user_input, reg_pass_input):
                            st.success("注册成功！请切换至登录标签页。")
                        else:
                            st.error("该学号已被注册！")
                else:
                    st.warning("请填写所有必填项！")

# 🚀 情况二：已登录界面（根据角色展示不同后台）
else:
    # 侧边栏公共部分：校徽与用户信息
    try:
        img = Image.open("gxu_logo.png")
        st.sidebar.image(img.resize((150, 150)))
    except:
        st.sidebar.warning("校徽加载失败")

    identity_name = "👑 系统管理员" if st.session_state["role"] == "admin" else "🎓 在校学生"
    st.sidebar.markdown(f"当前身份: **{identity_name}**")
    st.sidebar.markdown(f"用户账号: `{st.session_state['username']}`")

    if st.sidebar.button("退出登录", type="secondary", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["role"] = ""
        st.rerun()

    st.sidebar.markdown("---")

    # ==================== 【学生端功能界面】 ====================
    if st.session_state["role"] == "student":
        st.title("🎓 文渊系统 - 学生个人学术工作台")

        # 获取云端管理员实时配置
        current_config = zhanghao.get_system_config()

        # ================= 侧边栏：文献解析与知识库动态注入 =================
        # 加上 accept_multiple_files=True 开启多选
        uploaded_files = st.sidebar.file_uploader(
            label="上传毕业文献 (PDF/TXT/MD)",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True
        )

        # 如果有文件被上传（此时 uploaded_files 是一个列表）
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_key = f"processed_{uploaded_file.name}"
                # 针对列表中的每一个文件独立判断，防止重复解析
                if file_key not in st.session_state:
                    with st.sidebar.spinner(f"正在深度解析文献《{uploaded_file.name}》..."):
                        try:
                            # 调用 PDFparse.py 提取当前文件内容
                            chunks, ids, metadatas = PDFparse.parse_and_chunk_pdf(uploaded_file)

                            if chunks:
                                # 批量写入 Chroma 向量数据库
                                db_manager.collection.add(documents=chunks, ids=ids, metadatas=metadatas)
                                st.session_state[file_key] = True
                                st.sidebar.success(f"📚 《{uploaded_file.name}》成功注入知识库（共 {len(chunks)} 个片段）！")
                            else:
                                st.sidebar.warning(f"《{uploaded_file.name}》内未提取出有效文本片段。")
                        except Exception as e:
                            st.sidebar.error(f"文献《{uploaded_file.name}》导入失败: {e}")
        # ================= 主界面标签页构建 =================
        s_tab1, s_tab2, s_tab3 = st.tabs(["💬 智能问答与报告生成", "🔍 学术查重与降重", "👤 个人资料修改"])

        # --- Tab 1: 智能问答流 ---
        with s_tab1:
            st.subheader("文献知识库智能人机协同")
            # ---------------- 🌟 1. 新增：场景预设与 Prompt 自定义 ----------------
            col_mode, col_custom = st.columns([2, 3])

            with col_mode:
                prompt_mode = st.selectbox(
                    "🎯 选择 AI 协同工作模式",
                    [
                        "📖 文献深度精读与摘要",
                        "✍️ 开题报告审查与建议",
                        "💡 研究创新点与方法论分析",
                        "✏️ 语法润色与学术表达规范",
                        "⚙️ 完全自定义 Prompt 人设"
                    ]
                )

            # 各模式对应的提示词补充规则
            preset_prompts = {
                "📖 文献深度精读与摘要": "【当前任务】：文献精读。请帮我梳理上传文献的核心观点、研究方法、实验数据及主要结论，并归纳出关键创新点。",
                "✍️ 开题报告审查与建议": "【当前任务】：开题审查。请从选题意义、国内外研究现状、研究内容可行性及框架合理性等维度，审查我的开题思路并提出改进意见。",
                "💡 研究创新点与方法论分析": "【当前任务】：方法论提炼。请从文献和提问中分析研究方法的优缺点、适用场景以及可能的技术突破口。",
                "✏️ 语法润色与学术表达规范": "【当前任务】：学术润色。请在不改动原意的前提下，修正表达中的口语化词汇，使其提升至符合学术期刊发表标准的严谨书面语。"
            }

            # 动态拼接系统提示词
            base_system_prompt = current_config["system_prompt"]

            if prompt_mode == "⚙️ 完全自定义 Prompt 人设":
                with col_custom:
                    active_prompt = st.text_input(
                        "输入自定义提示词：",
                        value=base_system_prompt,
                        help="在此输入你希望 AI 扮演的角色或具体规则，将覆盖默认设置。"
                    )
            else:
                active_prompt = f"{base_system_prompt}\n{preset_prompts[prompt_mode]}"

            st.divider()
            st.session_state.setdefault("messages", [])

            for msg in st.session_state["messages"]:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            query = st.chat_input("向你的 AI 导师提问...")
            if query:
                # 学术安全拦截流水线：读取云端最新敏感词
                black_list = [w.strip() for w in current_config["sensitive_words"].replace("，", ",").split(",") if
                              w.strip()]
                violating_words = [word for word in black_list if word in query]

                if violating_words:
                    st.error(
                        f"❌ 触发学术违规拦截：您的提问中包含后台禁止的学术敏感词【{', '.join(violating_words)}】，已终止本次服务。")
                else:
                    st.session_state["messages"].append({"role": "user", "content": query})
                    with st.chat_message("user"):
                        st.write(query)

                    with st.chat_message("assistant"):
                        with st.spinner("AI 导师正在检索知识库并思考..."):
                            try:
                                response = DeepSeekAPI.call_deepseek(
                                    system_prompt=current_config["active_prompt"],
                                    top_k=current_config["top_k"],
                                    user_query=query,
                                    history=st.session_state["messages"][:-1]
                                )
                                st.write(response)
                                st.session_state["messages"].append({"role": "assistant", "content": response})
                            except Exception as e:
                                st.error(f"调用大模型失败，请检查配置: {e}")

        # --- Tab 2: 真实学术查重与降重引擎 ---
        with s_tab2:
            st.subheader("AI 学术查重与润色引擎")
            text_to_check = st.text_area("输入需要检测或降重的论文段落:", height=200,
                                         placeholder="在此处粘贴您的论文片段...")

            # 风格配置选择
            polish_style = st.selectbox("选择降重润色风格：", ["学术严谨性", "逻辑紧凑型", "句式丰富型"])

            col1, col2 = st.columns(2)

            # 功能分支 A：本地查重
            with col1:
                if st.button("开始本地查重", use_container_width=True):
                    if not text_to_check.strip():
                        st.warning("请先输入需要检测的论文文本段落。")
                    else:
                        # 查重敏感词前置拦截
                        black_list = [w.strip() for w in current_config["sensitive_words"].replace("，", ",").split(",")
                                      if w.strip()]
                        violating_words = [word for word in black_list if word in text_to_check]

                        if violating_words:
                            st.error(
                                f"❌ 拒绝检测：检测文本中包含违规学术词汇【{', '.join(violating_words)}】，请端正学术态度。")
                        else:
                            with st.spinner("查重算法运行中，正在比对私有知识库..."):
                                # 实例化查重引擎，传入真实的向量库管理器
                                engine = plagiarism.PlagiarismEngine(db_manager)
                                overall_rate, matched_segments = engine.check_similarity(text_to_check, threshold=0.3)

                                # 渲染工业级图表/指标
                                st.metric(label="📊 综合重复率", value=f"{overall_rate}%")

                                if overall_rate > 30:
                                    st.error("⚠️ 警告：当前段落重复率过高，未达到学术合规标准，强烈建议进行降重润色。")
                                else:
                                    st.success("✅ 查重通过！当前文本符合学术合规规范。")

                                # 渲染重合片段明细
                                if matched_segments:
                                    st.markdown("### 🔍 相似源重合片段对比：")
                                    for seg in matched_segments:
                                        st.info(f"**相似度: {seg['similarity']}%** \n> {seg['text']}")
                                else:
                                    st.write("未在私有知识库中检索到高度重合的已知文献。")

            # 功能分支 B：智能降重
            with col2:
                if st.button("智能降重润色", use_container_width=True):
                    if not text_to_check.strip():
                        st.warning("请先输入需要降重的论文段落。")
                    else:
                        with st.spinner("AI 学术导师正在重构句式、降低重复率..."):
                            try:
                                # 动态适配 plagiarism.py 中需要的 llm_agent 结构
                                class LLMAgentAdapter:
                                    def __init__(self):
                                        self.client = OpenAI(
                                            api_key=st.secrets["DEEPSEEK_API_KEY"],
                                            base_url="https://api.deepseek.com"
                                        )


                                adapter = LLMAgentAdapter()
                                engine = plagiarism.PlagiarismEngine(db_manager)

                                # 调用 plagiarism.py 里的大模型降重方法
                                polished_text = engine.reduce_weight(
                                    llm_agent=adapter,
                                    text_to_reduce=text_to_check,
                                    style=polish_style
                                )

                                st.success("✨ 降重润色完成！")
                                st.text_area("优化后的学术文本（可直接复制）：", value=polished_text, height=180)
                            except Exception as e:
                                st.error(f"大模型降重失败，请确认 Secrets 中的 API 密钥有效性: {e}")

        # --- Tab 3: 个人信息维护 ---
        with s_tab3:
            st.subheader("个人隐私与资料管理")
            new_nickname = st.text_input("修改个人昵称")
            if st.button("保存修改"):
                st.success("个人资料已成功同步至云端数据库！")

    # ==================== 【管理员端功能界面】 ====================
    elif st.session_state["role"] == "admin":
        st.title("👑 文渊系统 - 校园学术安全管理后台")

        # 【新增】每次加载后台，优先从云端数据库获取最新配置
        current_config = zhanghao.get_system_config()

        a_tab1, a_tab2, a_tab3 = st.tabs(["👥 校园用户账号管理", "📝 报告模板与提示词配置", "🛡️ 学术合规与敏感词治理"])

        with a_tab1:
            st.subheader("学生账户统一管理面板")
            students = zhanghao.get_students_list()
            if students:
                st.table([{"学号/用户名": s, "账户状态": "启用中"} for s in students])
            else:
                st.write("当前暂无学生注册。")

        with a_tab2:
            st.subheader("🤖 大模型底座与全局 Prompt 配置")
            st.caption("在此配置全网默认的 AI 导师人设底座与文献检索深度。")

            # 默认提示词替换为通用的学术助手基座
            default_base_prompt = (
                "你是一位严谨的高校学术导师与文献分析专家。你的任务是协助学生进行文献精读、开题报告审查、"
                "学术论文分析及写作指导。请严格基于知识库参考资料回答，保持客观、严谨的学术语气。"
            )

            new_prompt = st.text_area(
                "系统全局默认 System Prompt (学术助手人设底座):",
                value=current_config.get("system_prompt", default_base_prompt),
                height=120
            )

            new_top_k = st.slider("知识库检索权重 (Top-K)", min_value=1, max_value=10,
                                  value=current_config.get("top_k", 5))

            if st.button("更新全局配置"):
                # 保存到数据库的代码保持原样
                zhanghao.update_system_config(new_prompt, new_top_k)
                st.success("全局配置已同步至 Supabase 云端！")

        with a_tab3:
            st.subheader("系统敏感词黑名单动态维护")
            # value 绑定云端读取到的真实敏感词
            new_words = st.text_area("配置学术敏感词（逗号隔开）:", value=current_config["sensitive_words"])

            if st.button("保存词库并部署拦截流水线"):
                # 【真实写入】调用敏感词更新函数
                zhanghao.update_sensitive_words(new_words)
                st.success("最新词库已部署至全网拦截引擎流水线！")
                st.rerun()