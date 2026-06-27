#!/usr/bin/env python3
"""
arXiv 论文辅助工具 — API 元数据获取 + 引用解析
"""
import re
import os
import urllib.request
import xml.etree.ElementTree as ET


ARXIV_API = "http://export.arxiv.org/api/query"


def fetch_metadata(arxiv_id):
    """从 arXiv API 获取论文元数据
    
    返回: dict 包含 title, authors, year, summary, categories, doi
    """
    url = f"{ARXIV_API}?id_list={arxiv_id}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            xml = r.read().decode('utf-8')
    except Exception as e:
        return {"error": str(e)}
    
    ns = {'a': 'http://www.w3.org/2005/Atom',
          'arxiv': 'http://arxiv.org/schemas/atom'}
    
    root = ET.fromstring(xml)
    entry = root.find('a:entry', ns)
    if entry is None:
        return {"error": "entry not found"}
    
    title = entry.find('a:title', ns)
    published = entry.find('a:published', ns)
    summary = entry.find('a:summary', ns)
    
    authors = []
    for author in entry.findall('a:author', ns):
        name = author.find('a:name', ns)
        if name is not None:
            authors.append(name.text)
    
    categories = []
    for cat in entry.findall('a:category', ns):
        categories.append(cat.get('term', ''))
    
    primary = entry.find('arxiv:primary_category', ns)
    primary_cat = primary.get('term', '') if primary is not None else ''
    
    # DOI 可能在 arxiv:doi 标签或注释中
    doi = ""
    for comment in entry.findall('arxiv:comment', ns):
        if comment.text and 'doi' in comment.text.lower():
            doi_match = re.search(r'10\.\d{4,}/[\S]+', comment.text)
            if doi_match:
                doi = doi_match.group()
    
    result = {
        'arxiv_id': arxiv_id,
        'title': title.text.strip().replace('\n', ' ') if title is not None else '',
        'authors': authors,
        'year': published.text[:4] if published is not None else '',
        'summary': summary.text.strip().replace('\n', ' ') if summary is not None else '',
        'categories': categories,
        'primary_category': primary_cat,
        'doi': doi,
    }
    return result


def download_pdf(arxiv_id, output_path=None):
    """下载 arXiv 论文 PDF
    
    返回: 本地文件路径
    """
    if output_path is None:
        output_path = f"/tmp/arxiv_{arxiv_id}.pdf"
    
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        urllib.request.urlretrieve(pdf_url, output_path)
        return output_path
    except Exception as e:
        return None


def parse_arxiv_id(url_or_id):
    """从 URL 或字符串中提取 arXiv ID"""
    # https://arxiv.org/abs/2301.00001 或 2301.00001
    match = re.search(r'(\d{4}\.\d{4,})(v\d+)?', url_or_id)
    if match:
        return match.group(1)
    return url_or_id.strip()


def extract_references(text):
    """从论文正文提取参考文献列表
    
    返回: list[dict] 每项包含 index, authors, year, title, journal, doi
    """
    # 找 REFERENCES / BIBLIOGRAPHY 章节之后的内容
    ref_match = re.split(
        r'\n\s*(?:REFERENCES|BIBLIOGRAPHY|参考文献)\s*\n',
        text, flags=re.IGNORECASE
    )
    if len(ref_match) < 2:
        return []
    
    ref_text = ref_match[1]
    # 切到下一个主要章节或附录
    ref_text = re.split(
        r'\n\s*(?:APPENDIX|ACKNOWLEDGMENT|附录|致谢)\s*\n',
        ref_text, flags=re.IGNORECASE
    )[0]
    
    references = []
    # 匹配 [N] 开头的引用条目
    pattern = r'\[(\d+)\]\s*(.+?)(?=\n\s*\[\d+\]|\Z)'
    for match in re.finditer(pattern, ref_text, re.DOTALL):
        idx = int(match.group(1))
        entry_text = match.group(2).strip().replace('\n', ' ')
        
        # 清理多余空白
        entry_text = re.sub(r'\s+', ' ', entry_text)
        
        # 提取年份
        year_match = re.search(r'\((\d{4})\)', entry_text)
        year = year_match.group(1) if year_match else ''
        
        # 提取 DOI
        doi_match = re.search(r'doi\.org/(10\.\d{4,}/[\S]+)', entry_text, re.IGNORECASE)
        doi = doi_match.group(1).rstrip('.,)') if doi_match else ''
        
        # 提取作者（年份前面的部分）
        author_text = entry_text
        if year:
            author_text = entry_text.split(f'({year})')[0].strip().rstrip(',').rstrip('.')
        
        references.append({
            'index': idx,
            'raw': entry_text,
            'year': year,
            'doi': doi,
            'authors': author_text[:200],
        })
    
    return references


def classify_arxiv_category(primary_cat):
    """将 arXiv 分类映射到知识引擎的学科分类"""
    cat_map = {
        'cs': '计算机科学',
        'math': '数学',
        'physics': '物理科学',
        'astro-ph': '物理科学',
        'cond-mat': '物理科学',
        'q-bio': '生物科学',
        'q-fin': '金融',
        'stat': '数学',
        'eess': '电子工程',
        'econ': '经济学',
    }
    prefix = primary_cat.split('.')[0]
    return cat_map.get(prefix, '计算机科学')


if __name__ == '__main__':
    # 测试
    meta = fetch_metadata('2301.00001')
    t = meta.get('title', '')[:60]
    print(f'标题: {t}')
    print(f'作者: {meta.get("authors",[])[:3]}')
    print(f'年份: {meta.get("year")}')
    print(f'分类: {meta.get("primary_category")}')
    pc = meta.get('primary_category', '')
    print(f'映射分类: {classify_arxiv_category(pc)}')
    
    # 下载并解析引用
    pdf = download_pdf('2301.00001', '/tmp/test_arxiv.pdf')
    if pdf:
        from pypdf import PdfReader
        reader = PdfReader(pdf)
        full_text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        refs = extract_references(full_text)
        print(f'\n引用数量: {len(refs)}')
        for r in refs[:3]:
            idx = r['index']
            yr = r['year']
            au = r['authors'][:60]
            print(f'  [{idx}] ({yr}) {au}...')
