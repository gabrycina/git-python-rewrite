import argparse
import collections
import configparser
from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib
from pathlib import Path

argparser = argparse.ArgumentParser(description="The stupidest version control")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True

#subparser for init
argsp = argsubparsers.add_parser("init", help="Initialize a new empty tft repository.")
argsp.add_argument("path", metavar="directory", nargs="?", default=".", help="Where to create the repository.")

#subparser for hash-object
argsp = argsubparsers.add_parser("hash-object", help="Compute object ID and optionally creates a blob from a file")
argsp.add_argument("-t", metavar="type", dest="type", choices=["blob", "commit", "tag", "tree"], default="blob", help="Specify the type")
argsp.add_argument("-w", dest="write", action="store_true", help="Actually write the object into the database")
argsp.add_argument("path", help="Read object from <file>")

#subparser for ls-files
argsp = argsubparsers.add_parser("ls-files", help = "List all the stage files")
argsp.add_argument("--verbose", action="store_true", help="Show everything.")

#subparser for rev-parse
argsp = argsubparsers.add_parser("rev-parse", help="Parse revision (or other objects) identifiers")
argsp.add_argument("--wyag-type", metavar="type", dest="type", 
                   choices=["blob", "commit", "tag", "tree"], 
                   default=None, help="Specify the expected type")
argsp.add_argument("name", help="The name to parse")

#subparser for tag
argsp = argsubparsers.add_parser("tag",help="List and create tags")
argsp.add_argument("-a",action="store_true",dest="create_tag_object",help="Whether to create a tag object")
argsp.add_argument("name",nargs="?",help="The new tag's name")
argsp.add_argument("object",default="HEAD",nargs="?",help="The object the new tag will point to")

#subparser for show-ref
argsp = argsubparsers.add_parser("show-ref", help="List references in the current repository.")

#subparser for ls-tree
argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object.")
argsp.add_argument("-r", dest="recursive", action="store_true", help="Recurse into sub-trees")
argsp.add_argument("tree", help="A tree-ish object.")

#subparser for log command
argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

#subparser for check-ignore command
argsp = argsubparsers.add_parser("check-ignore", help = "Check path(s) against ignore rules.")
argsp.add_argument("path", nargs="+", help="Paths to check")

def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)
    match args.command:
        case "add"          : cmd_add(args)
        case "cat-file"     : cmd_cat_file(args)
        case "check-ignore" : cmd_check_ignore(args)
        case "checkout"     : cmd_checkout(args)
        case "commit"       : cmd_commit(args)
        case "hash-object"  : cmd_hash_object(args)
        case "init"         : cmd_init(args)
        case "log"          : cmd_log(args)
        case "ls-files"     : cmd_ls_files(args)
        case "ls-tree"      : cmd_ls_tree(args)
        case "rev-parse"    : cmd_rev_parse(args)
        case "rm"           : cmd_rm(args)
        case "show-ref"     : cmd_show_ref(args)
        case "status"       : cmd_status(args)
        case "tag"          : cmd_tag(args)
        case _              : print("Bad command.")\
        
class GitRepository(object):
    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")
        
        if not (force or os.path.isdir(self.gitdir)):
            raise Exception("Not a Git repository %s" % path)
        
        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repositoryformatversion %s" % vers)
                
                
class GitObject (object):

    def __init__(self, data=None):
        if data != None:
            self.deserialize(data)
        else:
            self.init()

    def serialize(self, repo):
        raise Exception("Unimplemented!")
    
    def deserialize(self, data):
        raise Exception("Unimplemented!")
    
    def init(self):
        pass
      

class GitCommit(GitObject):
    # Specify the object format as 'commit'
    fmt = b'commit'

    def __init__(self):
        # Initialize the commit object with an empty key-value list map (KVL)
        self.kvlm = {}

    def read_data(self, data):
        """Deserialize the data into a key-value list map (KVL)."""
        self.kvlm = kvlm_parse(data)

    def write_data(self):
        """Serialize the commit's key-value list map (KVL) back into bytes."""
        return kvlm_serialize(self.kvlm)

      
class GitBlob(GitObject):
    # Blob format type
    fmt = b'blob'

    def serialize(self):
        """Returns the blob data."""
        return self.blobdata

    def deserialize(self, data):
        """Stores the data in the blob."""
        self.blobdata = data

class GitTag(GitCommit):
    fmt = b'tag'    

class GitIndexEntry(object):
    def __init__(self, ctime=None, mtime=None, dev=None, ino=None,
                 mode_type=None, mode_perms=None, uid=None, gid=None,
                 fsize=None, sha=None, flag_assume_valid=None,
                 flag_stage=None, name=None):
        # Last modification of metadata
        self.ctime = ctime
        # Last modification of data
        self.mtime = mtime
        # Device ID
        self.dev = dev
        # The file's inode number
        self.ino = ino
        # File mode
        self.mode_type = mode_type
        # Permissions as integer
        self.mode_perms = mode_perms
        # Owner user ID
        self.uid = uid
        # Owner group ID
        self.gid = gid
        # Size of the file
        self.fsize = fsize
        # SHA-1 of the file
        self.sha = sha
        # The file is assumed to be valid
        self.flag_assume_valid = flag_assume_valid
        # The file is staged
        self.flag_stage = flag_stage
        # The file name
        self.name = name

class GitIndex(object):
    version = None
    entries = []
    def __init__(self, version=2, entries=list()):
        self.version = version
        self.entries = entries

class GitTree(GitObject):
    fmt = b'tree'
    def serialize(self):
        return tree_serialize(self)

    def deserialize(self, data):
        self.items = tree_parse(data)
    
    def init(self):
        self.items = list()

class GitTreeLeaf(object):
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha

def tree_parse_one(raw, start=0):
    # Find the first space
    x = raw.find(b' ', start)
    assert x - start == 5 or x - start == 6
    # Read the mode
    mode = raw[start:x]
    if len(mode):
        mode = b' ' + mode
    # Find the NULL value
    y = raw.find(b'\x00', x)
    # Read the path
    path = raw[x + 1:y]

    # Read the sha
    sha = format(int.from_bytes(raw[y + 1:], 'big'), '040x')
    return y + 21, GitTreeLeaf(mode, path.decode('utf-8'), sha)

def tree_parse(raw):
    pos = 0
    max = len(raw)
    ret = list()
    while pos < max:
        pos, leaf = tree_parse_one(raw, pos)
        ret.append(leaf)

    return ret

def tree_serialize(obj):
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b''
    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path.encode('utf-8')
        ret += b'\x00'
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, 'big')
        
    return ret

def tree_leaf_sort_key(leaf):
    return leaf.path + ('' if leaf.path.startswith(b'10') else '/')

def repo_path(repo, *path): 
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
    """Same as repo_path, but create dirname(*path) if absent.  For
example, repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\") will create
.git/refs/remotes/origin."""

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path, but mkdir *path if absent if mkdir."""

    path = repo_path(repo, *path)

    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception("Not a directory %s" % path)

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None
    

def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")

    return ret


def repo_create(path):
    """Create a new repository at path."""

    repo = GitRepository(path, True)

    # First, we make sure the path either doesn't exist or is an
    # empty dir.

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception ("%s is not a directory!" % path)
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception("%s is not empty!" % path)
    else:
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

def repo_find(path=".", required=True):
    """"
    Finds the root of the current repository.
    """
    #gets the real path resolving symlinks
    path = Path(path).resolve()

    #check if the path contains the .git directory
    path_to_check = path.joinpath(".git")
    if path_to_check.is_dir():
        return GitObject(path)

    #if it doesn't try to get the parent directory of path
    parent = path.joinpath("..").resolve()

    #if parent directory corresponds to the path it means we've reached the base directory. Git repository isn't found
    if parent == path:
        if required:
            raise Exception("No tft Repository found.")
        else:
            return None

    #otherwise we'll do this again with the parent directory
    return repo_find(parent, required)

  
def object_read(repo, sha):

    #read file .git/objects where first two are the directory name, the rest as the file name 
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    with open (path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type "commit", "tree", "blob", "tag"
        x = raw.find(b' ')
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("Malformed object {0}: bad length".format(sha))

        # Pick the correct constructor depending on the type read above
        match fmt:
            case b'commit' : c=GitCommit
            case b'tree'   : c=GitTree
            case b'tag'    : c=GitTag
            case b'blob'   : c=GitBlob
            case _:
                raise Exception("Unknown type {0} for object {1}".format(fmt.decode("ascii"), sha))

        # Construct and return an instance of the corresponding Git object type
        return c(raw[y+1:])

def object_hash(fd, fmt, repo=None):
    """Hash object, writing it to repo if provided."""
    data = fd.read()

    # Choose constructor according to fmt argument
    match fmt:
        case b'commit' : obj=GitCommit(data)
        case b'tree'   : obj=GitTree(data)
        case b'tag'    : obj=GitTag(data)
        case b'blob'   : obj=GitBlob(data)
        case _: raise Exception("Unknown type %s!" % fmt)

    return object_write(obj, repo)
      
def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # Add header to serialized data
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # Compute path
        path=repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        #Extra check before writing
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                # Compress and write
                f.write(zlib.compress(result))
    return sha
 
def object_find(repo, name, fmt=None, follow=True):
    """Just temporary, will implement this fully soon"""
    return name
  

def cmd_ls_files(args):
    repo = repo_find()
    index = index_read(repo)

    if args.verbose:
        print("Index file format v{}, containing {} entries.".format(index.version, len(index.entries)))
    
    for entry in index.entries:
        print(entry.name)
        if args.verbose:
            print("  {} with perms: {:o}".format(
            {0b1000: "regular file",
            0b1010: "symlink",
            0b1110: "git link"}[entry.mode_type],
        entry.mode_perms))
        print("  on blob: {}".format(entry.sha))
        print("  created: {}.{}, modified: {}.{}".format(
            datetime.fromtimestamp(entry.ctime[0]),
            entry.ctime[1], 
            datetime.fromtimestamp(entry.mtime[0]), 
            entry.mtime[1]))
        print("  device: {}, inode: {}".format(entry.dev, entry.ino))
        print("  user: {} ({})  group: {} ({})".format(
            pwd.getpwuid(entry.uid).pw_name,
            entry.uid,
            grp.getgrgid(entry.gid).gr_name,
            entry.gid))
        print("  flags: stage={} assume_valid={}".format(
        entry.flag_stage,
        entry.flag_assume_valid))

    sha = object_resolve(repo, name)

    if not sha:
        raise Exception("No such reference {0}.".format(name))

    if len(sha) > 1:
        raise Exception("Ambiguous reference {0}: Candidates are:\n - {1}.".format(name,  "\n - ".join(sha)))
    
    sha = sha[0]

    if not fmt:
        return sha

    while True:
        obj = object_read(repo, sha)
        if obj.fmt == fmt:
            return sha
        if not follow:
            return None
        sha = obj.oid

        if obj.fmt == b'tag':
            sha = obj.kvlm[b'object'].decode("ascii")
        elif obj.fmt == b'commit' and fmt == b'tree':
            sha = obj.kvlm[b'tree'].decode("ascii")
        else:
            return None

def index_read(repo):
    index_file = repo_file(repo, "index")

    if not os.path.exists(index_file):
        return GitIndex()
    
    with open(index_file, "rb") as f:
        raw = f.read()
    
    # First 12 bytes are the header
    header = raw[:12]
    signature = header[:4]
    assert signature == b"DIRC" # DirCache
    version = int.from_bytes(header[4:8], 'big')
    # Tft only supports index file version 2
    assert version == 2
    count = int.from_bytes(header[8:12], "big")

    entries = list()

    content = raw[12:]
    index = 0
    for i in range(count):
        
        ctime_s =  int.from_bytes(content[idx: idx+4], "big")
        ctime_ns = int.from_bytes(content[idx+4: idx+8], "big")
        mtime_s = int.from_bytes(content[idx+8: idx+12], "big")
        mtime_ns = int.from_bytes(content[idx+12: idx+16], "big")
        dev = int.from_bytes(content[idx+16: idx+20], "big")
        ino = int.from_bytes(content[idx+20: idx+24], "big")
        unused = int.from_bytes(content[idx+24: idx+26], "big")
        assert 0 == unused
        mode = int.from_bytes(content[idx+26: idx+28], "big")
        mode_type = mode >> 12
        assert mode_type in [0b1000, 0b1010, 0b1110]
        mode_perms = mode & 0b0000000111111111
        uid = int.from_bytes(content[idx+28: idx+32], "big")
        gid = int.from_bytes(content[idx+32: idx+36], "big")
        fsize = int.from_bytes(content[idx+36: idx+40], "big")
        sha = format(int.from_bytes(content[idx+40: idx+60], "big"), "040x")
        flags = int.from_bytes(content[idx+60: idx+62], "big")
        flag_assume_valid = (flags & 0b1000000000000000) != 0
        flag_extended = (flags & 0b0100000000000000) != 0
        assert not flag_extended
        flag_stage =  flags & 0b0011000000000000
        name_length = flags & 0b0000111111111111
        
        idx += 62

        if name_length < 0xFFF:
            assert content[idx + name_length] == 0x00
            raw_name = content[idx:idx+name_length]
            idx += name_length + 1
        else:
            print("Notice: Name is 0x{:X} bytes long.".format(name_length))
            null_idx = content.find(b'\x00', idx + 0xFFF)
            raw_name = content[idx: null_idx]
            idx = null_idx + 1

        # Just parse the name as utf8.
        name = raw_name.decode("utf8")

        idx = 8 * ceil(idx / 8)

        # And we add this entry to our list.
        entries.append(GitIndexEntry(ctime=(ctime_s, ctime_ns),
                                     mtime=(mtime_s,  mtime_ns),
                                     dev=dev,
                                     ino=ino,
                                     mode_type=mode_type,
                                     mode_perms=mode_perms,
                                     uid=uid,
                                     gid=gid,
                                     fsize=fsize,
                                     sha=sha,
                                     flag_assume_valid=flag_assume_valid,
                                     flag_stage=flag_stage,
                                     name=name))

    return GitIndex(version=version, entries=entries)

def object_resolve(repo, name):
    candidates = list()
    hashRe = re.compile(b'^[0-9A-Fa-f]{4,40}$') # Hex string matcher
  
    if not name.strip(): # Empty string
        return None
    
    if name == "HEAD": # HEAD case
        return [ ref_resolve(repo, "HEAD") ]

    if hashRe.match(name):# Short or long hash
        name = name.lower()
        prefix = name[0:2]
        path = repo_dir(repo, "objects", prefix)

        if path:
            rem = name[2:]
            for f in os.listdir(path):
                if f.startswith(rem):
                    candidates.append(prefix + f)

    as_tag = ref_resolve(repo, "refs/tags/" + name)
    if as_tag: # Ref case
        candidates.append(as_tag)
    
    as_branch = ref_resolve(repo, "refs/heads/" + name)
    if as_branch: # Branch case
        candidates.append(as_branch)
    return candidates

def kvlm_parse(raw, start=0, dct=None):
    # dct initialization
    if not dct:
        dct = collections.OrderedDict()

    # Find the next space and the next newline
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)

    # BASE CASE : newline appears before a space or there is no space
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start+1:]
        return dct

    # RECURSIVE CASE : we read a key-value pair and then recurse for the next   
    key = raw[start:spc]

    # Find the end of the value
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): 
            break

    # Grab the value and drop the leading space on continuation lines
    value = raw[spc+1:end].replace(b'\n ', b'\n')

    # Don't overwrite existing data contents
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key]=value

    # Recursive call to parse the rest of the data
    return kvlm_parse(raw, start=end+1, dct=dct)

def ref_resolve(repo, ref):
    path = repo_file(repo, ref)

    if not os.path.isfile(path):
        return None

    with open(path, 'r') as fp:
        data = fp.read()[:-1]

    if data.startswith("ref: "):
        return ref_resolve(repo, data[5:])
    else:
        return data

def ref_list(repo, path=None):
    if not path:
        path = repo_dir(repo, "refs")
    ret = collections.OrderedDict()

    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)
        if os.path.isdir(can):
            ret[f] = ref_list(repo, can)
        else:
            ret[f] = ref_resolve(repo, can)

    return ret

def show_ref(repo, refs, with_hash=True, prefix=''):
    for name, val in refs.items():
        if type(val) == str:
            print("{0}{1}{2}".format(
                val + " " if with_hash else "",
                prefix + "/" if prefix else "",
                name))
        else:
            show_ref(repo, val, with_hash, prefix=f"{prefix}{"/" if prefix else ""}{name}")

def kvlm_serialize(kvlm):
    res = b''

    # Output fields
    for key in kvlm.keys():
        # Skip the message itself
        if key == None: continue

        val = kvlm[key]
        # Normalize to a list
        if type(val) != list:
            val = [ val ]

        # Serialize each value
        for v in val:
            res += key + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'

    # Append message
    res += b'\n' + kvlm[None] + b'\n'

    return res
  
def ls_tree(repo, ref, recursive=None, prefix=''):
    obj = object_read(repo, object_find(repo, ref, fmt=b'tree'))
    for item in obj.items:
        type = item.mode[0:(1 if len(item.mode) == 5 else 2)]
        match (type):
            case '04': type = 'tree'
            case '10': type = 'blob'
            case '12': type = 'blob'
            case '16': type = 'blob'
            case _: raise Exception("Unknown type %s!" % type)
        if not (recursive and type == 'tree'):
            print("{0} {1} {2}\t{3}".format(
                "0" * (6 - len(item.mode)) + item.mode.decode("ascii"), type,
                item.sha,
                os.path.join(prefix, item.path)))
        else:
            ls_tree(repo, item.sha, recursive, prefix=os.path.join(prefix, item.path))

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())
     
#Bride functions
def cmd_init(args):
    """Bridge function to initialize a new repository."""
    repo_create(args.path)

def cmd_log(args):
    repo = repo_find()

    print("digraph wyaglog{")
    print("  node[shape=rect]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")

def log_graphviz(repo, sha, seen):

    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    short_hash = sha[0:8]
    message = commit.kvlm[None].decode("utf8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"", "\\\"")

    if "\n" in message: # Keep only the first line
        message = message[:message.index("\n")]

    print("  c_{0} [label=\"{1}: {2}\"]".format(sha, sha[0:7], message))
    assert commit.fmt==b'commit'

    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        return

    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [ parents ]

    for p in parents:
        p = p.decode("ascii")
        print ("  c_{0} -> c_{1};".format(sha, p))
        log_graphviz(repo, p, seen)

def cmd_hash_object(args):
    """Bridge function to compute the hash-name of object and optionally create the blob"""
    if args.write:
        repo = repo_find()
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

#Check-ignore function
def cmd_check_ignore(args):
  repo = repo_find()
  rules = gitignore_read(repo)
  for path in args.path:
      if check_ignore(rules, path):
        print(path)

def gitignore_parse1(raw):
    raw = raw.strip() #remove space

    if not raw or raw[0] == "#":
        return None
    elif raw[0] == "!":
        return (raw[1:], False)
    elif raw[0] == "\\":
        return (raw[1:], True)
    else:
        return (raw, True)

def gitignore_parse(lines):
    ret = list() #rules list

    for line in lines:
        parsed = gitignore_parse1(line)
        if parsed:
            ret.append(parsed)

    return ret

class GitIgnore(object):
    absolute = None
    scoped = None

    def __init__(self, absolute, scoped):
        self.absolute = absolute
        self.scoped = scoped

def gitignore_read(repo):
    ret = GitIgnore(absolute=list(), scoped=dict())

    #read local configuration: .git/info/exclude
    repo_file = os.path.join(repo.gitfir, "info/exclude")
    if os.path.exists(repo_file):
        with open(repo_file, "r") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))
    
    #global configuration
    if "XDG_CONFIG_HOME" in os.environ:
        config_home = os.environ["XDG_CONFIG_HOME"]
    else:
        config_home = os.path.expanduser("~/.config")
    global_file = os.path.join(config_home,"git/ignore")

    if os.path.exists(global_file):
        with open(global_file, "r") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))
    
    # .gitignore files in the index
    index = index_read(repo)
    for entry in index.entries:
        if entry.name == ".gitignore" or entry.name.endswitch("/.gitignore"):
            dir_name = os.path.dirname(entry.name)
            contents = object_read(repo, entry.sha)
            lines = contents.blobdata.decode("utf8").splitlines()
            ret.scoped[dir_name] = gitignore_parse(lines)
    return ret

#function check match with rules
def check_ignore1(rules, path):
    result = None # nothing matched
    for(pattern, value) in rules:
        if fnmatch(path, pattern):
            result = value
    return result #true or false

def check_ignore_scoped(rules, path):
    #Check ignore rules in parent directories
    parent = os.path.dirname(path)
    while True:
        if parent in rules:
            result = check_ignore1(rules[parent], path)
            if result != None:
                return result
        if parent == "":
            break
        parent = os.path.dirname(parent)
    return None

def check_ignore_absolute(rules, path):
    #Check ignore rules in absolute paths
    parent = os.path.dirname(path)
    for ruleset in rules:
        result = check_ignore1(ruleset, path)
        if result != None:
            return result
    return False # This is a reasonable default at this point.

def check_ignore(rules, path):
    #Check if a given path is ignored based on the provided ignore rules
    if os.path.isabs(path):
        raise Exception("This function requires path to be relative to the repository's root")

    result = check_ignore_scoped(rules.scoped, path)
    if result != None:
        return result

    return check_ignore_absolute(rules.absolute, path)

def cmd_rev_parse(args):
    """Bridge function to parse a revision."""
    fmt = args.type.encode() if args.type else None

    repo = repo_find()
    print(object_find(repo, args.name, fmt, follow=True))

def cmd_tag(args):
    repo = repo_find()
    # If the user provided a name for a new tag
    if args.name:
        # Call tag_create function to create the new tag in the repository
        tag_create(repo,args.name, args.object, type="object" if args.create_tag_object else "ref")  
    # If the user did not provide a name for a new tag
    else:
        # Get the list of references (refs) in the repository
        refs = ref_list(repo)
        # Show the list of tags without their respective hashes
        show_ref(repo, refs["tags"], with_hash=False)

def tag_create(repo, name, ref, create_tag_object=False):
    # get the GitObject from the object reference
    sha = object_find(repo, ref)
    if create_tag_object:
        # create tag object (commit)
        tag = GitTag(repo)
        # Initialize the key-value list map for the tag object
        tag.kvlm = collections.OrderedDict()
        tag.kvlm[b'object'] = sha.encode()
        tag.kvlm[b'type'] = b'commit'
        tag.kvlm[b'tag'] = name.encode() #the user give the name
        tag.kvlm[b'tagger'] = b'Wyag <tft@example.com>'
        tag.kvlm[None] = b"A tag generated by tft, which won't let you customize the message!"
        tag_sha = object_write(tag)
        # Create a reference to the tag object in the repository
        ref_create(repo, "tags/" + name, tag_sha)
    else:
        # create lightweight tag (ref)
        ref_create(repo, "tags/" + name, sha)

def ref_create(repo, ref_name, sha):
    with open(repo_file(repo, "refs/" + ref_name), 'w') as fp:
        fp.write(sha + "\n")

def cmd_show_ref(args):
    """Bridge function to show a reference."""
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="refs")

def cmd_ls_tree(args):
    """Bridge function to list the contents of a tree object."""
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)

