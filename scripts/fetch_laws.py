"""S2.1 抓取法条原文并拆成「条」级 JSONL。

为什么要绕道 GitHub：
    本机网络对 flk.npc.gov.cn / www.gov.cn 返回 ENOENT（沙箱出口限制），
    但 raw.githubusercontent.com 可达。LawRefBook/Laws 是公开的法律文本仓库，
    内容与官方版本一致，且带版本日期，便于我们做「生效日期 + 版本」字段。

输出：data/laws/<slug>.jsonl，每条 = 一部法的一个条文
    {"law": "...", "slug": "...", "version_date": "2012-12-28",
     "article_no": "第四十七条", "article_idx": 47, "text": "...",
     "source_url": "https://raw.githubusercontent.com/...", "fetched_at": "..."}

用法：
    python -m scripts.fetch_laws           # 抓取并写入
    python -m scripts.fetch_laws --check   # 只核对条数，不写盘
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import socket
import sys
import urllib.request

REPO = "LawRefBook/Laws"
RAW = f"https://raw.githubusercontent.com/{REPO}/master/"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "laws")

# 我们要的法：关键词 -> (slug, 官方全称, 期望条数用于自检)
TARGETS = [
    ("劳动合同法", "labor_contract_law", "中华人民共和国劳动合同法", 98),
    ("劳动争议调解仲裁法", "arbitration_law", "中华人民共和国劳动争议调解仲裁法", None),
    ("劳动法(2018", "labor_law", "中华人民共和国劳动法", None),
    ("职工带薪年休假条例", "annual_leave_regulation", "职工带薪年休假条例", None),
    ("企业职工带薪年休假实施办法", "annual_leave_impl", "企业职工带薪年休假实施办法", None),
    ("社会保险法", "social_insurance_law", "中华人民共和国社会保险法", None),
    ("劳动合同法实施条例", "labor_contract_impl", "中华人民共和国劳动合同法实施条例", None),
    ("工资支付暂行规定", "wage_payment_rules", "工资支付暂行规定", None),
]

CN_NUM = "零一二三四五六七八九十百"


def http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def repo_tree() -> list[str]:
    info = json.loads(http_get(f"https://api.github.com/repos/{REPO}"))
    branch = info["default_branch"]
    tree = json.loads(http_get(f"https://api.github.com/repos/{REPO}/git/trees/{branch}?recursive=1"))
    return [t["path"] for t in tree["tree"] if t["type"] == "blob"]


def find_path(paths: list[str], keyword: str) -> str | None:
    hits = [p for p in paths if keyword in p]
    if not hits:
        return None
    # 正典优先，其次司法解释/规章
    hits.sort(key=lambda p: (("司法解释" in p), len(p)))
    return hits[0]


def cn_to_int(s: str) -> int | None:
    """第一百零五条 -> 105"""
    if not s:
        return None
    if s.isdigit():
        return int(s)
    total, section, num = 0, 0, 0
    for ch in s:
        if ch == "百":
            section = (section or 1) * 100
        elif ch == "十":
            section = (section or 1) * 10
        elif ch in "零一二三四五六七八九":
            num = "零一二三四五六七八九".index(ch)
            section += num
        else:
            return None
    total = section + num
    return total or None


ARTICLE_RE = re.compile(r"^\s*第([零一二三四五六七八九十百]+)条\s*", re.M)


def split_articles(text: str) -> list[tuple[str, str]]:
    """按「第X条」切分，返回 [(原始条号, 正文)]。"""
    matches = list(ARTICLE_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # 切掉被吞进来的章节标题（如 "## 第四章 劳务派遣"），否则会混进法条正文
        body = re.split(r"\n\s*(?:#{1,6}\s|第[一二三四五六七八九十百]+章)", body)[0].strip()
        body = re.sub(r"\n{2,}", "\n", body)
        out.append((f"第{m.group(1)}条", body))
    return out


def guess_version(path: str) -> str:
    m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", path)
    return m.group(1) if m else ""


def fetch_one(path: str) -> str:
    return http_get(RAW + urllib.parse.quote(path)).decode("utf-8", "replace")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只打印条数，不写盘")
    args = ap.parse_args(argv)
    socket.setdefaulttimeout(30)

    paths = repo_tree()
    print(f"[repo] {len(paths)} files in {REPO}")

    report = []
    os.makedirs(OUT_DIR, exist_ok=True)
    for keyword, slug, official, expect in TARGETS:
        path = find_path(paths, keyword)
        if not path:
            print(f"[MISS] {slug}: 仓库里没找到含「{keyword}」的文件")
            report.append((slug, 0, "MISS"))
            continue
        text = fetch_one(path)
        arts = split_articles(text)
        print(f"[ok] {slug:26s} articles={len(arts):3d} version={guess_version(path)}")

        if not args.check:
            out_path = os.path.join(OUT_DIR, f"{slug}.jsonl")
            with open(out_path, "w", encoding="utf-8") as f:
                for no, body in arts:
                    rec = {
                        "law": official,
                        "slug": slug,
                        "version_date": guess_version(path),
                        "article_no": no,
                        "article_idx": cn_to_int(no[1:-1]),
                        "text": body,
                        "source_repo": REPO,
                        "source_path": path,
                        "source_url": RAW + urllib.parse.quote(path),
                        "fetched_at": dt.date.today().isoformat(),
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        report.append((slug, len(arts), guess_version(path)))

    print("\n=== 条数自检 ===")
    ok = True
    for keyword, slug, official, expect in TARGETS:
        got = next((n for s, n, _ in report if s == slug), 0)
        flag = "?"
        if expect:
            flag = "OK" if got == expect else f"FAIL(期望 {expect})"
            ok = ok and got == expect
        print(f"  {slug:26s} {got:3d}  {flag}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
