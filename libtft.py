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

#subparser for rev-parse
argsp = argsubparsers.add_parser("rev-parse", help="Parse revision (or other objects) identifiers")
argsp.add_argument("--wyag-type", metavar="type", dest="type", 
                   choices=["blob", "commit", "tag", "tree"], 
                   default=None, help="Specify the expected type")
argsp.add_argument("name", help="The name to parse")

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

def cmd_rev_parse(args):
    """Bridge function to parse a revision."""
    fmt = args.type.encode() if args.type else None

    repo = repo_find()
    print(object_find(repo, args.name, fmt, follow=True))