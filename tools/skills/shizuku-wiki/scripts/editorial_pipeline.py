#!/usr/bin/env python3
"""Conservative wikitext prose review helper for shizuku-wiki v3.

Not a grammar model. Models author the prose; this script protects markup and
provides opt-in pre/post comparison and checks timeline review records.
Record validation is not semantic judgment or proof of user approval.
Never changes the live Wiki.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
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
TIMELINE_LINE = re.compile(r'^\* (\d{4}-\d{2}-\d{2})：\S')
TIMELINE_HINT = re.compile(r'^\s*\*\s*\d{4}-\d{1,2}-\d{1,2}', re.M)
REVIEW_CHECKS = ('viewpoint', 'factual_scope', 'granularity', 'context')
EVENT_KINDS = ('action_change', 'demo', 'announcement', 'foundation')
EVENT_STAGES = ('operational', 'demo', 'prototype', 'announced', 'not_applicable')


def text_hash(text: str) -> str:
    """Hash UTF-8 text after the CLI's BOM/newline normalization."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def timeline_entries(text: str) -> list[dict]:
    """Accept only proposed entry lines and optional year headings, not a diff."""
    entries = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip() or re.fullmatch(r'==\s*\d{4}\s*==', line):
            continue
        match = TIMELINE_LINE.match(line)
        if not match:
            raise ValueError(f'L{line_no}: 年表の提案行ではありません（説明・差分記号は別ファイルへ）。')
        date.fromisoformat(match.group(1))
        entries.append({'id': f'L{line_no:05d}', 'text': line, 'entry_sha256': text_hash(line)})
    if not entries:
        raise ValueError('年表の追加・置換行がありません。')
    return entries


def timeline_template(text: str) -> dict:
    items = []
    for entry in timeline_entries(text):
        items.append({**entry, 'kind': '', 'stage': '',
                      'source_basis': [{'locator': '', 'fact': ''}],
                      'shizuku_event': '', 'perspective': '',
                      'alternative': '', 'exception_reason': '',
                      'checks': {key: {'status': 'pending', 'reason': ''} for key in REVIEW_CHECKS},
                      'decision': 'pending'})
    return {'schema': 'shizuku-wiki-timeline-review-v1',
            'proposal_sha256': text_hash(text), 'items': items,
            'note': 'AI/人間が出典と文脈で審査して記入。機械は意味の適合や公開承認を判定しない。'}


def review_timeline(text: str, record: object) -> dict:
    """Reject missing, stale, incomplete or held reviews; do not infer meaning."""
    problems = []

    def nonempty(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    def result() -> dict:
        return {'status': 'blocked' if problems else 'record_valid',
                'problems': problems,
                'note': '審査記録の整合性のみ。事実・文意・文体の適合は記入者が出典と本文で判断する。公開承認とは別。'}

    try:
        expected = timeline_entries(text)
    except ValueError as exc:
        problems.append(str(exc))
        return result()
    if not isinstance(record, dict):
        problems.append('年表の意味的レビュー記録がありません。')
        return result()
    if record.get('schema') != 'shizuku-wiki-timeline-review-v1':
        problems.append('審査記録のschemaが不正です。')
    if record.get('proposal_sha256') != text_hash(text):
        problems.append('審査後に提案本文が変更されています。全項目を再確認してください。')
    items = record.get('items')
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        problems.append('itemsは項目ごとの審査記録の配列が必要です。')
        return result()
    if [item.get('id') for item in items] != [item['id'] for item in expected]:
        problems.append('審査対象の欠落・重複・余分な項目・順序の相違があります。')
        return result()
    for item, entry in zip(items, expected):
        label = entry['id']
        if any(item.get(key) != entry[key] for key in ('text', 'entry_sha256')):
            problems.append(f'{label}: 審査対象の本文が一致しません。')
        if item.get('kind') not in EVENT_KINDS or item.get('stage') not in EVENT_STAGES:
            problems.append(f'{label}: 出来事の種類・確認段階が未分類です。')
        sources = item.get('source_basis')
        if not isinstance(sources, list) or not sources or not all(
            isinstance(source, dict) and nonempty(source.get('locator')) and nonempty(source.get('fact'))
            for source in sources
        ):
            problems.append(f'{label}: 出典の所在と確認できた事実が必要です。')
        if not nonempty(item.get('shizuku_event')):
            problems.append(f'{label}: しずくとの関係が未記入です。')
        if item.get('perspective') not in ('direct', 'technical_exception'):
            problems.append(f'{label}: 視点の判定が必要です。')
        elif item['perspective'] == 'technical_exception':
            if not all(nonempty(item.get(key)) for key in ('alternative', 'exception_reason')):
                problems.append(f'{label}: 技術的例外には検討した別案と採用できない理由が必要です。')
        checks = item.get('checks')
        for key in REVIEW_CHECKS:
            check = checks.get(key) if isinstance(checks, dict) else None
            if not isinstance(check, dict) or check.get('status') != 'pass' or not nonempty(check.get('reason')):
                problems.append(f'{label}: {key} が未審査・不適合、または判断理由が未記入です。')
        if item.get('decision') != 'pass':
            problems.append(f'{label}: 採用判定が未了または保留です。')
    return result()


def audit_review(baseline: str, revised: str, page: str = 'auto', record: object = None) -> dict:
    result = stats(baseline, revised)
    # Detect dated bullets by default; callers on other pages may opt out.
    timeline = page == 'timeline' or record is not None or (
        page == 'auto' and bool(TIMELINE_HINT.search(revised))
    )
    result['timeline_review'] = review_timeline(revised, record) if timeline else {'status': 'not_applicable'}
    return result


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


def wikitext_lint(text: str) -> list[str]:
    """Detect common MediaWiki formatting mistakes (hyphen lists, unintended single newlines)."""
    warnings: list[str] = []
    in_block = False
    in_table = False
    prev_prose_line: int | None = None
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not in_block and BLOCK_START.search(line):
            in_block = True
            prev_prose_line = None
            continue
        if in_block:
            if BLOCK_END.search(line):
                in_block = False
            prev_prose_line = None
            continue
        if stripped.startswith('{|'):
            in_table = True
            prev_prose_line = None
            continue
        if in_table:
            if stripped.startswith('|}'):
                in_table = False
            prev_prose_line = None
            continue
        if re.match(r'^\s*-\s+\S', line):
            warnings.append(f'L{idx}: 箇条書きにハイフン「- 」が使われています（MediaWiki標準の「* 」を使用）。')
        is_special = (
            not stripped
            or bool(SKIP_LINE.match(line))
            or bool(re.match(r'^\s*[*#;:=]', line))
            or stripped.endswith('<br>')
            or stripped.endswith('<br/>')
            or stripped.endswith('<br />')
        )
        if is_special:
            prev_prose_line = None
        else:
            if prev_prose_line is not None:
                warnings.append(f'L{prev_prose_line}-L{idx}: 通常の改行1つで地の文が続いています（段落分けは空行、同段落内改行は <br> を使用）。')
            prev_prose_line = idx
    return warnings


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
    warnings.extend(wikitext_lint(revised))
    added=sorted(set(ALPHANUM.findall(revised)) - set(ALPHANUM.findall(baseline)))
    if added: warnings.append('英字表現が追加されています（固有情報の追加か確認）。')
    return {'baseline_editable_lines':len(before),'revised_editable_lines':len(after),'changed_lines':sum(x!=y for x,y in zip(before,after))+abs(len(before)-len(after)),'added_ascii_terms':added,'warnings':warnings,'note':'形式検査のみ。事実・心理・確度・発言者の変化は人間/AIが原文と出典で照合すること。'}


def run_deslop(text: str) -> dict:
    checker=ROOT/'vendor/deslop-ja/check.py'
    try:
        p=subprocess.run([sys.executable,'-X','utf8',str(checker),'--json','--reading-load'],input=text,capture_output=True,encoding='utf-8',timeout=25)
        if p.returncode == 0: return {'status':'ran','result':json.loads(p.stdout)}
        return {'status':'failed','message':p.stderr[-600:]}
    except Exception as ex: return {'status':'unavailable','message':str(ex)}


def run_natural_newfacts(original_path: str, revised_path: str) -> dict:
    if importlib.util.find_spec('sudachipy') is None:
        return {'status':'skipped','reason':'SudachiPy is not installed (optional)'}
    script=ROOT/'vendor/natural-japanese/newfacts.py'
    try:
        p=subprocess.run([sys.executable,'-X','utf8',str(script),original_path,revised_path,'--json'],capture_output=True,encoding='utf-8',timeout=25)
        if p.returncode==0: return {'status':'ran','result':json.loads(p.stdout)}
        return {'status':'failed','message':p.stderr[-700:]}
    except Exception as exc: return {'status':'failed','message':str(exc)}


def comparison_report(before: str,after: str, results: dict) -> str:
    delta=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='初稿',tofile='最終稿'))
    notes='\n'.join('- '+w for w in results['warnings']) if results['warnings'] else '- 形式的な不一致は検出されませんでした（意味の一致は別途確認）。'
    gate = results.get('timeline_review', {'status': 'not_applicable'})
    gate_notes = '\n'.join('- ' + item for item in gate.get('problems', []))
    return f'''# しずくWiki 文章比較（公開前・未反映）\n\n## 初稿（文章改善前）\n\n```wikitext\n{before.rstrip()}\n```\n\n## 最終稿（文章改善後）\n\n```wikitext\n{after.rstrip()}\n```\n\n## 文章差分\n\n```diff\n{delta.rstrip() or '(変更なし)'}\n```\n\n## 形式検査・人間の確認事項\n\n{notes}\n\n年表審査記録: {gate['status']}\n{gate_notes}\n\n**注意**：同一実行内の比較であり、旧版Skillを独立実行した比較ではありません。意味・文体の適合はAI/人間が出典と照合し、公開承認は別途確認してください。\n'''


def main() -> int:
    p=argparse.ArgumentParser(description='shizuku-wiki v3 editorial helper (read-only for live wiki)')
    cmd=p.add_subparsers(dest='command',required=True)
    prep=cmd.add_parser('prepare'); prep.add_argument('--input',required=True);prep.add_argument('--out',required=True)
    ap=cmd.add_parser('apply'); ap.add_argument('--input',required=True); ap.add_argument('--segments',required=True); ap.add_argument('--edits',required=True); ap.add_argument('--out',required=True)
    au=cmd.add_parser('audit'); au.add_argument('--baseline',required=True); au.add_argument('--revised',required=True); au.add_argument('--json-out'); au.add_argument('--compare-report',help='Explicit test mode only: pre/post markdown report')
    au.add_argument('--page', choices=('auto', 'timeline', 'general'), default='auto')
    au.add_argument('--timeline-review', help='AI/human-authored timeline review JSON bound to revised text')
    tr=cmd.add_parser('timeline-template'); tr.add_argument('--input',required=True); tr.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        if args.command=='timeline-template':
            target = Path(args.out)
            target.parent.mkdir(parents=True, exist_ok=True)
            template = timeline_template(read(args.input))
            with target.open('x', encoding='utf-8') as handle:
                json.dump(template, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            print('未審査の年表テンプレートを作成しました。全項目の根拠と判断理由を記入してください。')
        elif args.command=='prepare':
            x=prepare(read(args.input));dump(args.out,x); print(f'編集候補行: {len(x["editable"])}（Wiki原稿は変更していません）')
        elif args.command=='apply':
            manifest=json.loads(read(args.segments)); data=json.loads(read(args.edits)); edits=data.get('edits',data)
            rewritten=apply(read(args.input),manifest,edits)
            Path(args.out).write_text(rewritten,encoding='utf-8'); print('保護要素を維持してローカル推敲稿を出力しました。公開はしていません。')
        else:
            before,after=read(args.baseline),read(args.revised)
            record=json.loads(read(args.timeline_review)) if args.timeline_review else None
            result=audit_review(before,after,args.page,record)
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
            gate=result['timeline_review']
            print('年表審査記録:',gate['status'],'（意味の自動判定ではありません）')
            for problem in gate.get('problems',[]): print('保留:',problem)
            if gate['status'] == 'blocked': return 1
        return 0
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as exc:
        print('エラー:',exc,file=sys.stderr); return 2

if __name__=='__main__':sys.exit(main())
