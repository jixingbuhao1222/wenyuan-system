import io
import pdfplumber

def parse_and_chunk_pdf(uploaded_file):
    """解析单个上传的 PDF 文件流并切片"""
    uploaded_file.seek(0)
    full_text = ""
    with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # 文本切片（每 500 个字为一段）
    chunk_size = 500
    chunks = []
    ids = []
    metadatas = []

    for i in range(0, len(full_text), chunk_size):
        chunk = full_text[i:i + chunk_size]

        # 过滤掉太短或包含特定特征的乱码片段
        if len(chunk.strip()) > 50 and "评审教师签字" not in chunk and "合计 100" not in chunk:
            chunks.append(chunk)
            ids.append(f"{uploaded_file.name}_chunk_{i // chunk_size}")
            metadatas.append({"source": uploaded_file.name})

    return chunks, ids, metadatas