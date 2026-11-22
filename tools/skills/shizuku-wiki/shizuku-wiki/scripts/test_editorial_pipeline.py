import importlib.util
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
P=Path(__file__).resolve().parent/'editorial_pipeline.py'
spec=importlib.util.spec_from_file_location('editorial_pipeline',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ReviewPipelineTests(unittest.TestCase):
    def test_templates_and_links_restore(self):
        s='しずくは[[しずく|こちら]]で活動を続けた<ref name="a">資料</ref>。\n'
        manifest=m.prepare(s)
        self.assertEqual(len(manifest['editable']),1)
        part=manifest['editable'][0]
        candidate=part['masked'].replace('活動を続けた','活動した')
        out=m.apply(s,manifest,{part['id']:candidate})
        self.assertIn('[[しずく|こちら]]',out)
        self.assertIn('<ref name="a">資料</ref>',out)
        self.assertIn('活動した',out)
    def test_block_tables_skipped(self):
        s='{| class="wikitable"\n| しずくは活動した。\n|}\n本文の説明を書きます。\n'
        obj=m.prepare(s)
        self.assertEqual([x['line'] for x in obj['editable']],[4])
    def test_bad_numbers_rejected(self):
        s='しずくは2026年に活動した。\n'
        manifest=m.prepare(s); p=manifest['editable'][0]
        with self.assertRaisesRegex(ValueError,'numbers'):
            m.apply(s,manifest,{p['id']:'しずくは2027年に活動した。'})
    def test_new_syntax_rejected(self):
        s='しずくは活動している。\n'
        manifest=m.prepare(s);p=manifest['editable'][0]
        with self.assertRaisesRegex(ValueError,'syntax'):
            m.apply(s,manifest,{p['id']:'しずくは[[動画・配信]]で活動している。'})
    def test_unbalanced_ignored(self):
        s='しずくの記録{{複雑なテンプレート\n次の行は本文です。\n'
        obj=m.prepare(s)
        self.assertNotIn(1,[x['line'] for x in obj['editable']])
    def test_comparison_opt_in(self):
        baseline='しずくは非常に素晴らしい活動を実施した。\n'
        revised='しずくは活動した。\n'
        report=m.comparison_report(baseline,revised,m.stats(baseline,revised))
        self.assertIn('## 初稿',report)
        self.assertIn('## 最終稿',report)
    def test_unchanged_source_needed(self):
        s='しずくは活動した。\n';obj=m.prepare(s)
        with self.assertRaisesRegex(ValueError,'source has changed'):
            m.apply('しずくは活動した。\n追加しました。',obj,{})

class TimelineReviewTests(unittest.TestCase):
    # Synthetic fixtures test record enforcement, not semantic classification.
    text = '* 2026-11-05：iPhoneでしずくと会話する試作デモが公開された。<ref>資料</ref>\n'

    def reviewed(self, text=None):
        record = m.timeline_template(text or self.text)
        for item in record['items']:
            item.update(kind='demo', stage='prototype',
                        source_basis=[{'locator': 'fixture:demo', 'fact': '試作動画の公開。一般提供の記載なし。'}],
                        shizuku_event='試作でしずくと会話する様子が示された。',
                        perspective='direct', decision='pass')
            reasons = {'viewpoint': 'しずくとの会話が出来事の中心。',
                       'factual_scope': '試作デモの公開に限定し、実運用を主張していない。',
                       'granularity': '一つの体験を一文で記録。',
                       'context': '仮想の前後項目と整合。足跡への抜粋対象外。'}
            item['checks'] = {key: {'status': 'pass', 'reason': reasons[key]} for key in m.REVIEW_CHECKS}
        return record

    def test_technical_news_without_review_is_blocked_even_when_format_passes(self):
        before = '* 2026-11-08：Shizuku AIが独自の全二重音声対話モデルを発表した。\n'
        after = before.replace('発表', '公開')
        result = m.audit_review(before, after)
        self.assertEqual(result['warnings'], [])
        self.assertEqual(result['timeline_review']['status'], 'blocked')

    def test_unchanged_prose_still_requires_review(self):
        self.assertEqual(m.audit_review(self.text, self.text)['timeline_review']['status'], 'blocked')
        self.assertEqual(m.review_timeline(self.text, m.timeline_template(self.text))['status'], 'blocked')

    def test_complete_review_of_demo_is_accepted(self):
        result = m.audit_review(self.text, self.text, 'timeline', self.reviewed())
        self.assertEqual(result['timeline_review']['status'], 'record_valid')

    def test_technical_exception_needs_alternative_and_reason(self):
        text = '* 2026-11-08：Shizuku AIがしずく向けの音声基盤モデルを発表した。\n'
        record = self.reviewed(text)
        item = record['items'][0]
        item.update(kind='announcement', stage='announced', perspective='technical_exception')
        self.assertEqual(m.review_timeline(text, record)['status'], 'blocked')
        item.update(alternative='しずくが新しいモデルで話せるようになった。',
                    exception_reason='利用実績は未確認で、別案は能力獲得を断定してしまう。',
                    shizuku_event='しずくの会話基盤となる開発の節目。',
                    source_basis=[{'locator': 'fixture:announcement', 'fact': 'しずく向け基盤モデルの発表。運用開始は未記載。'}])
        item['checks']['viewpoint']['reason'] = '活動の土台との関係を残すため発表として記録。'
        item['checks']['factual_scope']['reason'] = '発表のみを記し、運用開始は断定していない。'
        self.assertEqual(m.review_timeline(text, record)['status'], 'record_valid')

    def test_changed_final_invalidates_review(self):
        altered = self.text.replace('試作デモが公開された', 'いつでも話せるようになった')
        self.assertEqual(m.review_timeline(altered, self.reviewed())['status'], 'blocked')

    def test_every_item_requires_review_including_same_date(self):
        text = self.text + self.text.replace('iPhone', 'PC')
        record = self.reviewed(text)
        self.assertEqual(m.review_timeline(text, record)['status'], 'record_valid')
        record['items'].pop()
        self.assertEqual(m.review_timeline(text, record)['status'], 'blocked')

    def test_duplicate_or_held_review_is_rejected(self):
        record = self.reviewed()
        record['items'].append(copy.deepcopy(record['items'][0]))
        self.assertEqual(m.review_timeline(self.text, record)['status'], 'blocked')
        for change in ('hold', 'empty_reason', 'missing_source'):
            record = self.reviewed()
            item = record['items'][0]
            if change == 'hold': item['decision'] = 'hold'
            elif change == 'empty_reason': item['checks']['viewpoint']['reason'] = ' '
            else: item['source_basis'] = []
            self.assertEqual(m.review_timeline(self.text, record)['status'], 'blocked')

    def test_invalid_review_data_and_unparsed_lines_fail_closed(self):
        for record in (None, [], {'items': [None]}, {'items': {}}):
            self.assertEqual(m.review_timeline(self.text, record)['status'], 'blocked')
        for text in ('== 2026 ==\n', self.text + '未審査の文章\n', self.text.replace('11-05', '02-30')):
            with self.assertRaises(ValueError): m.timeline_template(text)

    def test_general_page_is_not_required_to_have_timeline_review(self):
        text = 'しずくはご主人様と話している。\n'
        result = m.audit_review(text, text)
        self.assertEqual(result['timeline_review']['status'], 'not_applicable')

    def test_cli_returns_nonzero_when_review_is_missing_and_never_overwrites_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'proposal.wiki'
            source.write_text(self.text, encoding='utf-8')
            record = Path(tmp) / 'review.json'
            def run(*args):
                return subprocess.run([sys.executable, '-X', 'utf8', str(P), *map(str, args)],
                                      capture_output=True, text=True, encoding='utf-8', timeout=60)
            audit = run('audit', '--baseline', source, '--revised', source, '--page', 'timeline')
            self.assertEqual(audit.returncode, 1, audit.stderr)
            self.assertEqual(run('timeline-template', '--input', source, '--out', record).returncode, 0)
            record.write_text(json.dumps(self.reviewed(), ensure_ascii=False), encoding='utf-8')
            saved = record.read_bytes()
            self.assertEqual(run('timeline-template', '--input', source, '--out', record).returncode, 2)
            self.assertEqual(record.read_bytes(), saved)
            audit = run('audit', '--baseline', source, '--revised', source, '--timeline-review', record)
            self.assertEqual(audit.returncode, 0, audit.stderr)


if __name__=='__main__':unittest.main()
