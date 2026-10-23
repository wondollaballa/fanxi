"""Check a retail FINAL FANTASY XI install, and what changed when it was patched.

  python tools/verify_install.py <FINAL FANTASY XI folder> [--baseline <folder>] [--json out.json]

The folder is what PlayOnline keeps under SquareEnix/FINAL FANTASY XI: VTABLE.DAT, FTABLE.DAT,
the FFXi*.dll programs and the ROM folders. PlayOnline is the only thing that patches it, so this
reads the result rather than doing the patching: is the tree complete, which build are its
programs (against meta/builds.json), and -- with --baseline, a copy of the tree from before the
patch -- exactly which files the patch added, rewrote or left alone.

Exit codes: 0 complete and a build builds.json knows, 2 structurally incomplete, 3 complete but a
build builds.json does not know yet (README: add it with tools/newbuild.py).

The ROM files are read, never written. Nothing here needs the network or the venv's packages.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDS = os.path.join(ROOT, 'meta', 'builds.json')

PROGRAMS = ('FFXiMain.dll', 'FFXi.dll')
TABLES = ('VTABLE.DAT', 'FTABLE.DAT')
ROM_PREFIX = 'ROM'
CHUNK = 1 << 20


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def pe_timestamp(path):
    """A PE's TimeDateStamp, or None if the file does not start like a PE."""
    try:
        with open(path, 'rb') as f:
            head = f.read(0x40)
            if len(head) < 0x40 or head[:2] != b'MZ':
                return None
            offset = struct.unpack_from('<I', head, 0x3c)[0]
            f.seek(offset)
            coff = f.read(0x18)
            if len(coff) < 0x18 or coff[:4] != b'PE\0\0':
                return None
            return struct.unpack_from('<I', coff, 8)[0]
    except OSError:
        return None


def build_label(timestamp):
    """New labels are the UTC date of FFXiMain.dll's PE timestamp (README, Rules)."""
    import datetime
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime('%Y-%m-%d')


def known_builds():
    with open(BUILDS) as f:
        return json.load(f)['builds']


def known_for(sha, module, builds):
    for label, b in builds.items():
        if b.get(module, {}).get('sha256') == sha:
            return label
    return None


def rom_sets(game):
    """{rom folder name: [dat paths]}, ROM first then ROM2.. in numeric order."""
    found = {}
    try:
        entries = os.listdir(game)
    except OSError:
        return found
    for name in entries:
        if not name.startswith(ROM_PREFIX):
            continue
        rest = name[len(ROM_PREFIX):]
        if rest and not rest.isdigit():
            continue
        folder = os.path.join(game, name)
        if not os.path.isdir(folder):
            continue
        dats = []
        for dirpath, _dirs, files in os.walk(folder):
            for f in files:
                if f.upper().endswith('.DAT'):
                    dats.append(os.path.join(dirpath, f))
        found[name] = sorted(dats)
    return dict(sorted(found.items(), key=lambda kv: (len(kv[0]), kv[0])))


def scan(tree, jobs=None):
    """(relative path -> (size, sha256)) for every file under tree."""
    paths = []
    for dirpath, _dirs, files in os.walk(tree):
        for name in files:
            full = os.path.join(dirpath, name)
            try:
                if os.path.islink(full) or not os.path.isfile(full):
                    continue
            except OSError:
                continue
            paths.append(full)

    def one(full):
        rel = os.path.relpath(full, tree)
        try:
            return rel, (os.path.getsize(full), sha256(full))
        except OSError:
            return rel, (0, '')

    out = {}
    jobs = jobs or min(32, (os.cpu_count() or 4))
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for rel, info in pool.map(one, paths):
            out[rel] = info
    return out


def compare(base, newer):
    """(added, removed, changed) relative paths, sorted."""
    added = sorted(set(newer) - set(base))
    removed = sorted(set(base) - set(newer))
    changed = sorted(p for p in set(base) & set(newer) if base[p] != newer[p])
    return added, removed, changed


def verify(game, baseline=None, jobs=None):
    problems = []
    report = {'game': os.path.abspath(game)}

    if not os.path.isdir(game):
        report['problems'] = ['not a directory: %s' % game]
        return report, 2

    for name in TABLES + PROGRAMS:
        if not os.path.isfile(os.path.join(game, name)):
            problems.append('missing %s' % name)

    sets = rom_sets(game)
    dats = [p for paths in sets.values() for p in paths]
    if not dats:
        problems.append('no ROM*/**/*.DAT files')
    report['rom_sets'] = {name: len(paths) for name, paths in sets.items()}
    report['dat_count'] = len(dats)

    sizes = 0
    empty = []
    for p in dats:
        try:
            size = os.path.getsize(p)
        except OSError:
            continue
        sizes += size
        if size < 4:
            empty.append(os.path.relpath(p, game))
    if empty:
        problems.append('%d DAT files smaller than 4 bytes (first: %s)' % (len(empty), empty[0]))
    report['dat_bytes'] = sizes

    for name in TABLES:
        path = os.path.join(game, name)
        report.setdefault('tables', {})[name] = os.path.getsize(path) if os.path.isfile(path) else None

    builds = known_builds()
    report['programs'] = {}
    for name in PROGRAMS:
        path = os.path.join(game, name)
        if not os.path.isfile(path):
            continue
        sha = sha256(path)
        ts = pe_timestamp(path)
        report['programs'][name] = {
            'sha256': sha,
            'pe_timestamp': ts,
            'pe_date': build_label(ts) if ts else None,
            'known_build': known_for(sha, name, builds),
        }
    report['known_build'] = report['programs'].get('FFXiMain.dll', {}).get('known_build')

    if baseline:
        if not os.path.isdir(baseline):
            problems.append('baseline is not a directory: %s' % baseline)
        else:
            base = scan(baseline, jobs)
            newer = scan(game, jobs)
            added, removed, changed = compare(base, newer)
            report['diff'] = {
                'baseline': os.path.abspath(baseline),
                'same': len(set(base) & set(newer)) - len(changed),
                'added': len(added),
                'removed': len(removed),
                'changed': len(changed),
                'added_examples': added[:10],
                'removed_examples': removed[:10],
                'changed_examples': changed[:10],
            }

    report['problems'] = problems
    if problems:
        return report, 2
    return report, 0 if report['known_build'] else 3


def human(report):
    out = []
    out.append('install  %s' % report['game'])
    if report.get('problems'):
        out.append('')
        out.append('PROBLEMS')
        for p in report['problems']:
            out.append('  %s' % p)
    out.append('')
    out.append('  %d files in ROM sets, %d DAT, %.1f GB'
               % (sum(report['rom_sets'].values()) if report.get('rom_sets') else 0,
                  report.get('dat_count', 0),
                  report.get('dat_bytes', 0) / (1 << 30)))
    if report.get('rom_sets'):
        out.append('  ' + '  '.join('%s(%d)' % (k, v) for k, v in report['rom_sets'].items()))
    for name, size in (report.get('tables') or {}).items():
        out.append('  %-10s %s' % (name, '%d bytes' % size if size is not None else 'MISSING'))
    for name, info in (report.get('programs') or {}).items():
        out.append('  %-12s %s  PE %s  build %s'
                   % (name, info['sha256'][:16] + '...',
                      info['pe_date'] or '-', info['known_build'] or 'unknown'))
    if report.get('diff'):
        d = report['diff']
        out.append('')
        out.append('patched against %s' % d['baseline'])
        out.append('  same %d   added %d   removed %d   changed %d'
                   % (d['same'], d['added'], d['removed'], d['changed']))
        for key in ('added', 'removed', 'changed'):
            for path in d[key + '_examples'][:5]:
                out.append('    %-8s %s' % (key[:-1] if key != 'changed' else 'changed', path))
    out.append('')
    if report['problems']:
        out.append('verdict: incomplete')
    elif report['known_build']:
        out.append('verdict: complete; build %s is in meta/builds.json' % report['known_build'])
    else:
        out.append('verdict: complete; build is not in meta/builds.json')
        out.append('         python tools/newbuild.py identify --game "%s"' % report['game'])
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('game', help='the FINAL FANTASY XI folder (holds VTABLE.DAT and ROM*)')
    ap.add_argument('--baseline', help='a copy of the tree from before patching, to diff against')
    ap.add_argument('--json', help='also write the report here')
    ap.add_argument('--jobs', type=int, help='hashing threads (default: CPU count, up to 32)')
    ap.add_argument('--quiet', action='store_true', help='write nothing except the JSON report')
    args = ap.parse_args(argv)

    report, code = verify(args.game, args.baseline, args.jobs)
    if not args.quiet:
        print(human(report))
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(report, f, indent=2)
            f.write('\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
