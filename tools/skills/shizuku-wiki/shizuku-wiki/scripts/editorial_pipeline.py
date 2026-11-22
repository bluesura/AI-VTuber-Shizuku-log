#!/usr/bin/env python3
"""Conservative wikitext prose review helper for shizuku-wiki v2.

Not a grammar model. Models author the prose; this script protects markup and
provides opt-in pre/post comparison. Never changes the live Wiki.
"""
from __future__ import annotations
import argparse
import difflib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JAPANESE = re.compile(r'[ぁ-んァ-ン一-龯々]')
MARKER = re.compile(r'⟦MW\d{4}⟧')
NUMBER = re.compile(r'(?<![A-Za-z0-9])\d+(?:[.,]\d+)?')
ALPHANUM = re.compile(r'(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9_.\-]{2,}')
# Tag, comment, wiki and plain-URL boundaries. More complex constructs fail closed.
REF_TAG = re.compile(r'<ref\b[^>]*>.*?</ref\s*>|<ref\b[^>]*?/\s*>', re.I)
HTML_COMMENT = re.compile(r'<!--.*?-->')
HTML_SINGLE = re.compile(r'</?[A-Za-z][^>]*?>')
EXT_LINK = re.compile(r'\[(?:https?://|//)[^\]\n]+\]')
URL = re.compile(r'https?://[^\s<>\]]+')
STYLE = re.compile(r"'{2,5}")
BLOCK_START = re.compile(r'^\s*<\s*(pre|nowiki|syntaxhighlight|source|gallery|math)\b', re.I)
BLOCK_END = re.compile(r'</\s*(pre|nowiki|syntaxhighlight|source|gallery|math)\s*>', re.I)
SKIP_LINE = re.compile(r'^\s*(?:==|\{\||\|\}|\|-|\||!|\[\[Category:|\[\[カテゴリ:|#REDIRECT|__|\{\{)', re.I)
WIKI_NEW_SYNTAX = re.compile(r'\[\[|\]\]|\{\{|\}\}|<\s*ref\b|https?://', re.I)


def read(p: str) -> str:
    return Path(p).read_text(encoding='utf-8-sig')


def dump(p: str, value: object) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def matched_balanced(s: str, start: int, opening: str, closing: str) -> int | None:
    d = 1
    i = start + len(opening)
    while i < len(s):
        if s.startswith(opening, i): d += 1; i += len(opening)
        elif s.startswith(closing, i):
            d -= 1; i += len(closing)
            if d == 0: return i
        else: i += 1
    return None


def mask_line(line: str) -> tuple[str, list[str]] | None:
    """Mask conservative inline wikitext spans, fail closed if unfinished."""
    out = []
    protected = []
    i = 0
    while i < len(line):
        end = None
        if line.startswith('{{',i): end = matched_balanced(line,i,'{{','}}')
        elif line.startswith('[[',i): end = matched_balanced(line,i,'[[',']]')
        else:
            for pattern in (REF_TAG, HTML_COMMENT, EXT_LINK, URL, STYLE, HTML_SINGLE):
                m = pattern.match(line,i)
                if m:
                    end=m.end()
                    break
        if end is None:
            # Do not pass unbalanced potentially structural fragments to the LLM.
            if any(line.startswith(x,i) for x in ('{{', '[[', '<!--', '<ref')): return None
            out.append(line[i]); i += 1; continue
        protected.append(line[i:end]); out.append(f'⟦MW{len(protected):04d}⟧'); i = end
    masked=''.join(out)
    if not JAPANESE.search(masked): return None
    if any(x in masked for x in ('}}', ']]', '<ref', '-->')): return None
    return masked, protected


def prepare(text: str) -> dict:
    entries=[]
    lines=text.splitlines(keepends=True)
    table=False; block=False
    for i,whole in enumerate(lines):
        line=whole.rstrip('\r\n')
        x=line.strip()
        if x.startswith('{|'): table=True
        if BLOCK_START.search(line): block=True
        if not table and not block and x and not SKIP_LINE.search(line):
            # Raw quotes and non-prose instructions are not rewritten.
            if not x.startswith(('>', '<', '{', '}')) and not re.search(r'<(?!ref\b|br\b|/ref\b)', line, re.I):
                masked=mask_line(line)
                if masked:
                    src,tokens=masked
                    if len(JAPANESE.findall(src))>=3:
                        entries.append({'id':f'L{i+1:05d}','line':i+1,'source':line,'masked':src,'protected':tokens})
        if x.endswith('|}'): table=False
        if BLOCK_END.search(line): block=False
    return {'schema':'shizuku-wiki-editorial-v2','editable':entries,'total_lines':len(lines), 'note':'Only edit masked text and retain all placeholders in their original order.'}


def unmask(edited: str, tokens: list[str], original_masked: str) -> str:
    expected = [f'⟦MW{i+1:04d}⟧' for i in range(len(tokens))]
    actual = MARKER.findall(edited)
    if actual != expected: raise ValueError(f'wiki placeholder order/count mismatch: {actual} != {expected}')
    # Unmask cannot introduce new markup outside an original placeholder.
    stripped = MARKER.sub('',edited)
    old_stripped = MARKER.sub('',original_masked)
    if WIKI_NEW_SYNTAX.search(stripped) and not WIKI_NEW_SYNTAX.search(old_stripped):
        raise ValueError('new wikitext/URL syntax outside protected placeholders')
    if NUMBER.findall(stripped) != NUMBER.findall(old_stripped):
        raise ValueError('numbers or dates changed (manual, source-backed revision required)')
    for i,t in enumerate(tokens,1): edited=edited.replace(f'⟦MW{i:04d}⟧',t)
    return edited


def apply(text: str, manifest: dict, edits: dict) -> str:
    expected = prepare(text)
    if expected != manifest:
        raise ValueError('source has changed after prepare; regenerate manifest')
    lines=text.splitlines(keepends=True)
    allowed={x['id'] for x in manifest['editable']}
    if not set(edits)<=allowed:
        raise ValueError('an edit targets a protected or unknown segment')
    for obj in manifest['editable']:
        if obj['id'] not in edits: continue
        new=edits[obj['id']]
        if not isinstance(new,str) or '\n' in new or '\r' in new:
            raise ValueError('edit must be a single-line string')
        changed=unmask(new,obj['protected'],obj['masked'])
        raw=lines[obj['line']-1]
        ending='\r\n' if raw.endswith('\r\n') else ('\n' if raw.endswith('\n') else '')
        lines[obj['line']-1]=changed+ending
    return ''.join(lines)


def stats(baseline: str,revised: str) -> dict:
    a,b=prepare(baseline), prepare(revised)
    before=[item['source'] for item in a['editable']]
    after=[item['source'] for item in b['editable']]
    numbers_a=NUMBER.findall(baseline); numbers_b=NUMBER.findall(revised)
    # Extract protected spans conservatively (not exhaustive MediaWiki parsing).
    token_a=[t for item in a['editable'] for t in item['protected']]
    token_b=[t for item in b['editable'] for t in item['protected']]
    warnings=[]
    if numbers_a != numbers_b: warnings.append('数値・日付の出現順が異なります（要原典照合）。')
    if Counter(token_a) != Counter(token_b): warnings.append('Wiki保護要素の構成が異なります（要ソース照合）。')
    if baseline.count('\n') != revised.count('\n'): warnings.append('改行数が異なります（Wiki構造を確認）。')
    old_lines=baseline.splitlines(); new_lines=revised.splitlines()
    old_editable={x['line'] for x in a['editable']}; new_editable={x['line'] for x in b['editable']}
    if len(old_lines)==len(new_lines):
        for index,(old,new) in enumerate(zip(old_lines,new_lines),1):
            if old!=new and (index not in old_editable or index not in new_editable):
                warnings.append(f'保護対象または非本文の行 L{index} が変更されています。')
                if len(warnings)>10: break
    added=sorted(set(ALPHANUM.findall(revised)) - set(ALPHANUM.findall(baseline)))
    if added: warnings.append('英字表現が追加されています（固有情報の追加か確認）。')
    return {'baseline_editable_lines':len(before),'revised_editable_lines':len(after),'changed_lines':sum(x!=y for x,y in zip(before,after))+abs(len(before)-len(after)),'added_ascii_terms':added,'warnings':warnings,'note':'形式検査のみ。事実・心理・確度・発言者の変化は人間/AIが原文と出典で照合すること。'}


def run_deslop(text: str) -> dict:
    checker=ROOT/'vendor/deslop-ja/check.py'
    try:
        p=subprocess.run([sys.executable,str(checker),'--json','--reading-load'],input=text,capture_output=True,text=True,timeout=25)
        if p.returncode == 0: return {'status':'ran','result':json.loads(p.stdout)}
        return {'status':'failed','message':p.stderr[-600:]}
    except Exception as ex: return {'status':'unavailable','message':str(ex)}


def run_natural_newfacts(original_path: str, revised_path: str) -> dict:
    if importlib.util.find_spec('sudachipy') is None:
        return {'status':'skipped','reason':'SudachiPy is not installed (optional)'}
    script=ROOT/'vendor/natural-japanese/newfacts.py'
    try:
        p=subprocess.run([sys.executable,str(script),original_path,revised_path,'--json'],capture_output=True,text=True,timeout=25)
        if p.returncode==0: return {'status':'ran','result':json.loads(p.stdout)}
        return {'status':'failed','message':p.stderr[-700:]}
    except Exception as exc: return {'status':'failed','message':str(exc)}


def comparison_report(before: str,after: str, results: dict) -> str:
    delta=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='v1相当初稿',tofile='v2推敲稿'))
    notes='\n'.join('- '+w for w in results['warnings']) if results['warnings'] else '- 形式的な不一致は検出されませんでした（意味の一致は別途確認）。'
    return f'''# しずくWiki v2 テスト比較（公開前・未反映）\n\n## v1相当初稿（文章改善前）\n\n```wikitext\n{before.rstrip()}\n```\n\n## v2推敲稿（文章改善後）\n\n```wikitext\n{after.rstrip()}\n```\n\n## 文章差分\n\n```diff\n{delta.rstrip() or '(変更なし)'}\n```\n\n## 形式検査・人間の確認事項\n\n{notes}\n\n**注意**：これは一つのv2実行における推敲前／推敲後の比較であり、旧v1 Skillを独立実行した比較ではありません。データ・事実・出典・ニュアンス・禁止事項は別途照合してください。\n'''


def main() -> int:
    p=argparse.ArgumentParser(description='shizuku-wiki v2 editorial helper (read-only for live wiki)')
    cmd=p.add_subparsers(dest='command',required=True)
    prep=cmd.add_parser('prepare'); prep.add_argument('--input',required=True);prep.add_argument('--out',required=True)
    ap=cmd.add_parser('apply'); ap.add_argument('--input',required=True); ap.add_argument('--segments',required=True); ap.add_argument('--edits',required=True); ap.add_argument('--out',required=True)
    au=cmd.add_parser('audit'); au.add_argument('--baseline',required=True); au.add_argument('--revised',required=True); au.add_argument('--json-out'); au.add_argument('--compare-report',help='Explicit test mode only: pre/post markdown report')
    args=p.parse_args()
    try:
        if args.command=='prepare':
            x=prepare(read(args.input));dump(args.out,x); print(f'編集候補行: {len(x["editable"])}（Wiki原稿は変更していません）')
        elif args.command=='apply':
            manifest=json.loads(read(args.segments)); data=json.loads(read(args.edits)); edits=data.get('edits',data)
            rewritten=apply(read(args.input),manifest,edits)
            Path(args.out).write_text(rewritten,encoding='utf-8'); print('保護要素を維持してローカル推敲稿を出力しました。公開はしていません。')
        else:
            before,after=read(args.baseline),read(args.revised)
            result=stats(before,after)
            clean='\n'.join(x['masked'] for x in prepare(after)['editable'])
            result['deslop_ja_diagnostic']=run_deslop(clean) if clean else {'status':'skipped','reason':'no editable prose'}
            result['natural_japanese_newfacts']=run_natural_newfacts(args.baseline,args.revised)
            if args.json_out: dump(args.json_out,result)
            if args.compare_report:
                Path(args.compare_report).write_text(comparison_report(before,after,result),encoding='utf-8')
                print('テスト比較資料を生成しました（公開はしていません）。')
            else:
                print('形式検査:', '警告あり' if result['warnings'] else '重大な形式警告なし', f'／編集対象の変更候補行 {result["changed_lines"]}')
            for warning in result['warnings']:print('注意:',warning)
        return 0
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        print('エラー:',exc,file=sys.stderr); return 2

if __name__=='__main__':sys.exit(main())
