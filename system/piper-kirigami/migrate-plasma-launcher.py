#!/usr/bin/env python3
"""Redirect only existing Piper taskbar pins through Plasma's live API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


QUERY = '''
var result = [];
panels().forEach(function(p) {
    p.widgets().forEach(function(w) {
        if (w.type === "org.kde.plasma.icontasks" || w.type === "org.kde.plasma.taskmanager") {
            w.currentConfigGroup = ["General"];
            result.push({panel:p.id, widget:w.id, launchers:String(w.readConfig("launchers", ""))});
        }
    });
});
print(JSON.stringify(result));
'''


def plan_changes(panels, data_home):
    old = {'applications:org.freedesktop.Piper.desktop'}
    for root in (data_home.absolute(), data_home.resolve()):
        for relative in ('applications', 'flatpak/exports/share/applications'):
            old.add((root / relative / 'org.freedesktop.Piper.desktop').as_uri())
    new = 'applications:io.github.jheinem1.PiperKirigami.desktop'
    changes = []
    for panel in panels:
        before = panel['launchers']
        after = ','.join(new if item in old else item for item in before.split(','))
        if before != after:
            changes.append(dict(panel=panel['panel'], widget=panel['widget'], before=before, after=after))
    return changes


def evaluate(command, script):
    return json.loads(subprocess.check_output(
        [command, 'org.kde.plasmashell', '/PlasmaShell',
         'org.kde.PlasmaShell.evaluateScript', script], text=True, timeout=15))


def main():
    command = shutil.which('qdbus6') or shutil.which('qdbus')
    if not command or 'KDE' not in os.environ.get('XDG_CURRENT_DESKTOP', '').split(':'):
        print('Direct-file taskbar pins may need to be repinned to Piper Kirigami.')
        return
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    changes = plan_changes(evaluate(command, QUERY), data)
    if not changes:
        return
    backup = Path(sys.argv[1]) / 'plasma-launchers.json'
    with backup.open('x') as stream:
        json.dump(changes, stream, indent=2)
        stream.write('\n')
    # Validate every target before changing any widget. Do not overwrite a pin
    # list that the user changed after the read above.
    script = 'var changes = ' + json.dumps(changes) + ';\n' + '''
var targets = [];
changes.forEach(function(c) {
    var p = panelById(c.panel);
    var w = p ? p.widgetById(c.widget) : null;
    if (!w || (w.type !== "org.kde.plasma.icontasks" && w.type !== "org.kde.plasma.taskmanager"))
        throw new Error("Piper taskbar widget changed; leave pins untouched.");
    w.currentConfigGroup = ["General"];
    if (String(w.readConfig("launchers", "")) !== c.before)
        throw new Error("Taskbar pins changed; leave them untouched.");
    targets.push(w);
});
changes.forEach(function(c, i) {
    targets[i].writeConfig("launchers", c.after.split(","));
    targets[i].reloadConfig();
});
print(JSON.stringify(changes.map(function(c) { return c.widget; })));
'''
    assert evaluate(command, script) == [c['widget'] for c in changes]
    current = {(p['panel'], p['widget']): p['launchers'] for p in evaluate(command, QUERY)}
    assert all(current[(c['panel'], c['widget'])] == c['after'] for c in changes)
    print(f'Updated Piper taskbar pins in {len(changes)} widget(s); previous values saved privately.')


if __name__ == '__main__':
    main()
