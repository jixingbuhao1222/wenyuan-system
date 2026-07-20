import hashlib
import psycopg2
import streamlit as st


def make_hash(password):
    """密码加盐/哈希加密"""
    return hashlib.sha256(str.encode(password)).hexdigest()


def get_db_connection():
    """获取云端 PostgreSQL 数据库连接"""
    # 直接从 secrets.toml 安全读取，不再在代码里硬编码任何密码
    db_url = st.secrets["postgres"]["url"]
    return psycopg2.connect(db_url)


def init_db():
    """初始化云端用户数据表和系统配置表"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 原有的 users 表保持不变...
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT
        )
    ''')

    # 【新增】创建全局系统配置表 (限制只能有一行记录，完美存储全局配置)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            id INT PRIMARY KEY DEFAULT 1,
            system_prompt TEXT,
            top_k INT,
            sensitive_words TEXT,
            CONSTRAINT one_row CHECK (id = 1)
        )
    ''')

    # 【新增】如果表是空的，初始化插入一条默认数据
    cursor.execute('''
        INSERT INTO system_config (id, system_prompt, top_k, sensitive_words)
        VALUES (1, '你是一位严谨的西大导师，负责对学生的开题报告进行严格的学术合规审查。', 5, '抄袭, 代写, 枪手, 买卖论文')
        ON CONFLICT (id) DO NOTHING
    ''')

    conn.commit()
    cursor.close()
    conn.close()


def register_student(username, password):
    """学生自主注册逻辑（云端版）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
            (username, make_hash(password), "student")
        )
        conn.commit()
        return True
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return False  # 学号已存在
    except Exception as e:
        conn.rollback()
        print(f"注册异常: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def login_user(username, password):
    """统一登录校验，成功则返回角色类型"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # PostgreSQL 占位符使用 %s
    cursor.execute(
        "SELECT password, role FROM users WHERE username = %s", (username,)
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result and result[0] == make_hash(password):
        return result[1]  # 返回 'student' 或 'admin'
    return None


def get_students_list():
    """获取所有已注册学生列表（供管理员端调用）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE role='student'")
    students = cursor.fetchall()
    cursor.close()
    conn.close()
    return [s[0] for s in students]
# 2. 【新增】读取系统配置的函数
def get_system_config():
    """从云端数据库获取当前的系统配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT system_prompt, top_k, sensitive_words FROM system_config WHERE id = 1;")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {"system_prompt": row[0], "top_k": row[1], "sensitive_words": row[2]}
    return {"system_prompt": "你是一位严谨的西大导师...", "top_k": 5, "sensitive_words": "抄袭, 代写"}

# 3. 【新增】更新大模型 Prompt 和 Top-K 的函数
def update_system_config(system_prompt, top_k):
    """更新大模型 Prompt 与权重配置"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE system_config 
        SET system_prompt = %s, top_k = %s 
        WHERE id = 1;
    """, (system_prompt, top_k))
    conn.commit()
    cursor.close()
    conn.close()

# 4. 【新增】更新敏感词的函数
def update_sensitive_words(sensitive_words):
    """更新合规治理敏感词库"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE system_config 
        SET sensitive_words = %s 
        WHERE id = 1;
    """, (sensitive_words,))
    conn.commit()
    cursor.close()
    conn.close()