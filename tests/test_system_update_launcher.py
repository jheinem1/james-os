import configparser
from pathlib import Path
import shlex
import unittest


REPO = Path(__file__).resolve().parents[1]
LAUNCHER = 'system/usr_share_applications__system-update.desktop'


class SystemUpdateLauncherTest(unittest.TestCase):
    def setUp(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(REPO / LAUNCHER)
        self.entry = parser['Desktop Entry']

    def test_shortcut_opens_gui_without_starting_an_update(self):
        self.assertEqual(shlex.split(self.entry['Exec']), ['/usr/bin/bazzite-updater'])
        self.assertEqual(self.entry['Terminal'], 'false')
        self.assertEqual(self.entry['Type'], 'Application')

    def test_gui_icon_and_categories(self):
        self.assertEqual(self.entry['Icon'], 'io.github.rfrench3.bazzite-updater')
        categories = set(self.entry['Categories'].rstrip(';').split(';'))
        self.assertIn('System', categories)
        self.assertNotIn('ConsoleOnly', categories)

    def test_image_preserves_existing_shortcut_id_and_requires_gui(self):
        containerfile = (REPO / 'Containerfile').read_text()
        self.assertIn(f'COPY --chmod=0644 {LAUNCHER} /usr/share/applications/system-update.desktop', containerfile)
        self.assertIn('test -x /usr/bin/bazzite-updater', containerfile)


if __name__ == '__main__':
    unittest.main()
