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

#subparser for ls-tree
argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object.")
argsp.add_argument("-r", dest="recursive", action="store_true", help="Recurse into sub-trees")
argsp.add_argument("tree", help="A tree-ish object.")

#subparser for ls-files
argsp = argsubparsers.add_parser("ls-files", help = "List all the stage files")
argsp.add_argument("--verbose", action="store_true", help="Show everything.")

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

def cmd_hash_object(args):
    """Bridge function to compute the hash-name of object and optionally create the blob"""
    if args.write:
        repo = repo_find()
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

def cmd_ls_tree(args):
    """Bridge function to list the contents of a tree object."""
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)