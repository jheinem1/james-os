import pathlib
import runpy
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
HELPER = REPO / 'system/usr_bin__james-os-filter-flatpaks'
FILTER = runpy.run_path(str(HELPER))
ORIGINAL = 'https://raw.githubusercontent.com/ublue-os/bazzite/main/installer/${FLATPAKS} | tr'
RECIPE = 'FLATPAK_LIST="$(curl ' + ORIGINAL + " '\\n' ' ')\"\n"


class FlatpakDefaultsTest(unittest.TestCase):
    def test_exact_app_ids_and_refs_only(self):
        keep = '# comment\n\norg.mozilla.firefox\norg.freedesktop.Platform.VulkanLayer.MangoHud//23.08\norg.freedesktop.Piper\norg.kde.haruna\ncom.github.tchx84.Flatseal.extra\n'
        excluded = ''.join(
            f'{app}\napp/{app}/x86_64/stable\n {app}//stable \n'
            for app in sorted(FILTER['EXCLUDED'])
        )
        self.assertEqual(FILTER['filter_defaults'](keep + excluded), keep)
        self.assertEqual(FILTER['filter_defaults']('com.github.tchx84.Flatseal'), '')
        self.assertEqual(FILTER['filter_defaults']('org.example.Keep'), 'org.example.Keep')

    def fixture(self, recipe=RECIPE):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = pathlib.Path(temp.name)
        manifest = root / 'usr/share/ublue-os/bazzite/flatpak/install'
        justfile = root / 'usr/share/ublue-os/just/80-bazzite.just'
        for path in (manifest, justfile):
            path.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text('org.mozilla.firefox\norg.kde.haruna\ncom.github.tchx84.Flatseal\norg.freedesktop.Piper\n')
        justfile.write_text(recipe)
        return root, manifest, justfile

    def test_configure_filters_both_sources_and_is_idempotent(self):
        root, manifest, recipe = self.fixture()
        FILTER['configure_image'](root)
        expected = RECIPE.replace(ORIGINAL, ORIGINAL.replace(' | tr', ' | /usr/bin/james-os-filter-flatpaks | tr'))
        self.assertEqual(manifest.read_text(), 'org.mozilla.firefox\norg.kde.haruna\norg.freedesktop.Piper\n')
        self.assertEqual(recipe.read_text(), expected)
        FILTER['configure_image'](root)
        self.assertEqual(recipe.read_text(), expected)

    def test_upstream_changes_fail_before_writes(self):
        for content in ('changed upstream recipe\n', RECIPE * 2):
            with self.subTest(content=content):
                root, manifest, recipe = self.fixture(content)
                original = manifest.read_text()
                with self.assertRaises(RuntimeError):
                    FILTER['configure_image'](root)
                self.assertEqual(manifest.read_text(), original)
                self.assertEqual(recipe.read_text(), content)

    def test_missing_manifest_leaves_recipe_untouched(self):
        root, manifest, recipe = self.fixture()
        manifest.unlink()
        with self.assertRaises(FileNotFoundError):
            FILTER['configure_image'](root)
        self.assertEqual(recipe.read_text(), RECIPE)

    def test_cli_and_build_wiring(self):
        result = subprocess.run(['python3', str(HELPER)], input='com.github.tchx84.Flatseal\norg.mozilla.firefox\n', text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, 'org.mozilla.firefox\n')
        self.assertNotEqual(subprocess.run(['python3', str(HELPER), '--invalid'], capture_output=True).returncode, 0)
        self.assertIn('/usr/bin/james-os-filter-flatpaks --configure-image', (REPO / 'build.sh').read_text())
        self.assertIn('COPY --chmod=0755 system/usr_bin__james-os-filter-flatpaks /usr/bin/james-os-filter-flatpaks', (REPO / 'Containerfile').read_text())


if __name__ == '__main__':
    unittest.main()
