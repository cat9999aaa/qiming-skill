"""One collection membership rule for retrieval and structured writes."""
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from .scan import _root, _relative_path


def glob_match(path, pattern):
    parts=PurePosixPath(path).parts
    rules=PurePosixPath(pattern).parts
    def match(a,b):
        if not b: return not a
        if b[0]=='**': return match(a,b[1:]) or (bool(a) and match(a[1:],b))
        return bool(a) and fnmatchcase(a[0],b[0]) and match(a[1:],b[1:])
    return match(parts,rules)


def excluded(relative, rules):
    relative=PurePosixPath(relative)
    return any(glob_match(relative.as_posix(),rule) or relative.as_posix().startswith(rule.rstrip('/')+'/') or ('/' not in rule and any(fnmatchcase(p,rule) for p in relative.parts)) for rule in rules)


def contains(profile, collection, relative):
    path=Path(relative)
    directory=Path(collection.get('directory','.'))
    if path.is_absolute() or '..' in path.parts or not path.is_relative_to(directory): return False
    local=path.relative_to(directory).as_posix()
    return glob_match(local,collection.get('pattern','**/*.json')) and not excluded(path.as_posix(),profile.get('scope_rules',{}).get('exclude',[])) and not excluded(local,collection.get('exclude',[]))


def collection_paths(manifest_path, profile, collection):
    root=_root(manifest_path,collection['root'])
    directory=_relative_path(root,collection.get('directory','.'))
    if directory.is_symlink() or not directory.resolve().is_relative_to(root):
        raise ValueError('Collection directory escapes its registered root')
    for path in sorted(directory.glob(collection.get('pattern','**/*.json'))):
        relative=path.relative_to(root)
        if contains(profile,collection,relative) and not any((root/Path(*relative.parts[:n])).is_symlink() for n in range(1,len(relative.parts)+1)):
            if path.is_file(): yield root,path
