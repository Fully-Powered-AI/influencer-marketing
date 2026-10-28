"""Public configuration regressions; all entities are fictional, no network calls."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / '.test-tmp'
SCRATCH.mkdir(exist_ok=True)
os.environ['TMPDIR'] = str(SCRATCH)
sys.path.insert(0, str(ROOT / 'references'))
from brand_context import AUDIENCE_LABEL, claim_cues


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, skill, suffix):
        dest = self.base / skill
        shutil.copytree(ROOT / 'skills' / skill / 'scripts/fixtures' / suffix, dest)
        return dest

    def run_cli(self, skill, script, *args):
        result = subprocess.run([sys.executable, '-I', str(ROOT / 'skills' / skill / 'scripts' / script),
                                 *map(str, args)], text=True, capture_output=True, cwd=ROOT)
        return result.returncode, result.stdout + result.stderr

    def caption_workspace(self):
        ws = self.fixture('content-approval', 'ws')
        p = ws / 'program/program.md'
        program = p.read_text().replace('Cedar Lane', 'Northline Studio')
        program = re.sub(r'^- Audience age:.*$', '- ' + AUDIENCE_LABEL + ' none; general home goods [owner]', program, flags=re.M)
        program = re.sub(r'^\| youtube \|[^|]*\|', '| youtube | yes |', program, flags=re.M)
        p.write_text(program)
        brief = ws / 'campaigns/2026-12-fixture-launch/briefs/c-fx0003.md'
        brief.write_text('# Northline Studio: tote introduction\n\nCreator: c-fx0003\nPlatform: youtube\nProduct: Canvas Tote (fixture)\nAudience: general home goods; no age restriction.\nDisclosure: #ad and the programme spoken form.\n')
        caption = ws / 'exports/caption.txt'
        caption.write_text('#ad Paid partnership with Northline Studio. Cotton canvas construction. '
                           'Code FX0003 at https://www.example.com/pages/fixture?utm_source=creator&utm_campaign=fx0003')
        return ws, caption

    def caption(self, ws, caption, *extra):
        return self.run_cli('content-approval', 'check_caption.py', ws, '--campaign',
                            '2026-12-fixture-launch', '--creator', 'c-fx0003', '--platform',
                            'youtube', '--format', 'video', *extra, caption)

    def test_other_brand_spoken_timing_and_explicit_override(self):
        ws, caption = self.caption_workspace()
        transcript = ws / 'exports/transcript.txt'
        transcript.write_text('Northline Studio makes this tote. ' + 'Here is how I use it. ' * 20
                              + 'This video is sponsored by Northline Studio.')
        code, out = self.caption(ws, caption, '--transcript', transcript)
        self.assertEqual(code, 2, out)
        self.assertIn('after the first brand or code mention at 0: say it earlier', out)
        transcript.write_text('This video is sponsored by Northline Studio. Here is my tote.')
        code, out = self.caption(ws, caption, '--transcript', transcript)
        self.assertEqual(code, 0, out)
        self.assertIn('within the spoken window', out)
        program = ws / 'program/program.md'
        program.write_text(re.sub(r'^- Brand name:.*\n', '', program.read_text(), flags=re.M))
        code, out = self.caption(ws, caption, '--transcript', transcript)
        self.assertEqual(code, 1, out)
        self.assertIn('Brand name field', out)
        code, out = self.caption(ws, caption, '--transcript', transcript, '--brand-name', 'Northline Studio')
        self.assertEqual(code, 0, out)

    def test_ordinary_category_brief_and_restricted_variant(self):
        ws = self.fixture('creator-brief', 'workspace')
        program = ws / 'program/program.md'
        t = program.read_text().replace('Cedar Lane', 'Northline Studio')
        t = re.sub(r'^- Audience age:.*$', '- ' + AUDIENCE_LABEL + ' none; general home-goods audience [owner]', t, flags=re.M)
        t = re.sub(r'^\| instagram \|[^|]*\|', '| instagram | yes |', t, flags=re.M)
        program.write_text(t)
        brief = ws / 'campaigns/2026-12-fixture-launch/briefs/c-fx0001.md'
        text = brief.read_text().replace('Cedar Lane', 'Northline Studio')
        text = re.sub(r'## Platform and audience rules\n.*?(?=\n## )',
                      '## Platform and audience rules\n\nInstagram is allowed. No audience age restriction; general home-goods audience.\n', text, flags=re.S)
        brief.write_text(text)
        code, out = self.run_cli('creator-brief', 'check_brief.py', ws, brief, '--today', '2026-10-20')
        self.assertEqual(code, 0, out)
        self.assertIn('requires no audience age restriction', out)
        program.write_text(t.replace('none; general home-goods audience', 'minimum age 21; platform evidence required'))
        code, out = self.run_cli('creator-brief', 'check_brief.py', ws, brief, '--today', '2026-10-20')
        self.assertEqual(code, 2, out)
        self.assertIn('omits the configured audience restriction', out)

    def test_publication_applies_program_audience_rule(self):
        ws = self.fixture('publication-tracking', 'must-attend')
        p = ws / 'program/program.md'
        original = p.read_text()
        p.write_text(re.sub(r'^- Audience age:.*$', '- ' + AUDIENCE_LABEL + ' none; general home goods [owner]', original, flags=re.M))
        code, out = self.run_cli('publication-tracking', 'checks_due.py', ws, '--as-of', '2026-11-10')
        self.assertNotEqual(code, 1, out)
        self.assertNotIn('age setting', out)
        self.assertNotIn('audience evidence does not meet', out)
        mod = load('public_tracking_test', 'skills/publication-tracking/scripts/checks_due.py')
        row = dict.fromkeys(mod.PUB_HEADER, '')
        row.update(disclosure_seen='yes', notes='')
        entries = [{'token': 'live-check', 'kv': {'age': 'not-required'}}]
        self.assertEqual(mod.issue_states(row, None, entries, 'minimum age 21')["age"][0], 'open')
        self.assertEqual(mod.issue_states(row, None, entries, 'none; general home goods')["age"][0], 'n/a')
        entries[0]['kv']['age'] = 'not-offered'
        self.assertEqual(mod.issue_states(row, None, entries, 'minimum age 21')["age"][0], 'open')
        self.assertEqual(mod.issue_states(row, None, entries, None)["age"][0], 'unchecked')

    def test_claim_cues_are_explicit_and_malformed_values_fail(self):
        self.assertEqual(claim_cues([], ('certified',)), ('certified',))
        self.assertEqual(claim_cues(['- Claim review cues: none [owner]'], ('certified',)), ())
        self.assertEqual(claim_cues(['- Claim review cues: "Waterproof"; "recycled" [owner]'], ()), ('waterproof', 'recycled'))
        for value in ('waterproof', '"waterproof"; recycled', '""', '"  "', '"unfinished'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Claim review cues must be quoted'):
                claim_cues(['- Claim review cues: ' + value + ' [owner]'], ('certified',))

    def test_caption_cues_change_by_category(self):
        ws, caption = self.caption_workspace()
        program = ws / 'program/program.md'
        program.write_text(program.read_text().replace('### Approved claims', '- Claim review cues: "reclaimed" [owner]\n\n### Approved claims', 1))
        caption.write_text(caption.read_text() + ' A reclaimed finish.')
        transcript = ws / 'exports/transcript.txt'
        transcript.write_text('This video is sponsored by Northline Studio.')
        code, out = self.caption(ws, caption, '--transcript', transcript)
        self.assertEqual(code, 2, out)
        self.assertIn("cue 'reclaimed'", out)
        program.write_text(program.read_text().replace('"reclaimed" [owner]', 'none [owner]'))
        code, out = self.caption(ws, caption, '--transcript', transcript)
        self.assertEqual(code, 0, out)
        self.assertNotIn("cue 'reclaimed'", out)

    def test_malformed_cues_are_normal_errors_in_all_callers(self):
        ws, caption = self.caption_workspace()
        p = ws / 'program/program.md'
        p.write_text(p.read_text().replace('### Approved claims', '- Claim review cues: waterproof [owner]\n\n### Approved claims', 1))
        code, out = self.caption(ws, caption)
        self.assertEqual(code, 1, out)
        self.assertIn('Claim review cues must be quoted', out)
        self.assertNotIn('Traceback', out)
        code, out = self.run_cli('creator-outreach', 'check_drafts.py', ws, caption)
        self.assertEqual(code, 1, out)
        self.assertIn('Claim review cues must be quoted', out)
        self.assertNotIn('Traceback', out)
        kit = ws / 'campaigns/2026-12-fixture-launch/welcome/c-fx0001.md'
        kit.parent.mkdir()
        kit.write_text('Draft welcome kit.')
        code, out = self.run_cli('affiliate-onboarding', 'check_kit.py', ws, kit)
        self.assertEqual(code, 1, out)
        self.assertIn('Claim review cues must be quoted', out)
        self.assertNotIn('Traceback', out)

    def test_filled_program_accepts_brand_and_category_configuration(self):
        ws = self.base / 'filled'
        (ws / 'program').mkdir(parents=True)
        text = (ROOT / 'skills/program-setup/scripts/fixtures/filled-program.md').read_text()
        text = text.replace('Cedar Lane', 'Northline Studio')
        text = re.sub(r'^- Audience age:.*$', '- ' + AUDIENCE_LABEL + ' none; general home goods [owner]', text, flags=re.M)
        text = text.replace('### Approved claims', '- Claim review cues: "recycled"; "certified" [owner]\n\n### Approved claims', 1)
        (ws / 'program/program.md').write_text(text)
        code, out = self.run_cli('program-setup', 'init_workspace.py', ws, '--check', '--require', 'all')
        self.assertEqual(code, 0, out)

    def test_fresh_init_is_generic_and_non_destructive(self):
        ws = self.base / 'fresh'
        ws.mkdir()
        code, out = self.run_cli('program-setup', 'init_workspace.py', ws)
        self.assertEqual(code, 0, out)
        p = ws / 'program/program.md'
        self.assertIn('- Brand name:\n', p.read_text())
        self.assertNotIn('Cedar Lane', p.read_text())
        p.write_text(p.read_text().replace('- Brand name:\n', '- Brand name: Northline Studio [owner]\n'))
        before = p.read_bytes()
        code, out = self.run_cli('program-setup', 'init_workspace.py', ws)
        self.assertEqual(code, 0, out)
        self.assertEqual(p.read_bytes(), before)
        code, out = self.run_cli('program-setup', 'init_workspace.py', ws, '--check', '--require', 'all')
        self.assertEqual(code, 2, out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
