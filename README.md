# Write your own Git

Just rewriting Git in python. Why?

1. Is fun
2. To finally get it

## Classes:

### GitRepository:
1. Description: the repository object
2. Attributes: 
   - worktree: the work tree is the path where the files that are meant to be in version control are
   - gitdir: the git directory is the path where git stores its own data. Usually is a child directory of the work tree, called .git
   - conf: is an instance of the class ConfigParser, from the external module configparser, used to read and write INI configuration files