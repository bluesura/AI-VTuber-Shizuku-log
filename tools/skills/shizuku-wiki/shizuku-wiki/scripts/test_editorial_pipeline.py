import importlib.util
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
        self.assertIn('v1相当初稿',report)
        self.assertIn('v2推敲稿',report)
    def test_unchanged_source_needed(self):
        s='しずくは活動した。\n';obj=m.prepare(s)
        with self.assertRaisesRegex(ValueError,'source has changed'):
            m.apply('しずくは活動した。\n追加しました。',obj,{})

if __name__=='__main__':unittest.main()
