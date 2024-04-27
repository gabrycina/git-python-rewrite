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
