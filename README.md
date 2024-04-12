
<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="">
      <img src="INSERT Logo" alt="Logo" width="130" height="130">
   </a>
  <h2 align="center"> TFT git python rewrite</h2>

  <p align="center">
    Best way to learn git....Write your own 
    <br />
    <a href="https://wyag.thb.lt/#intro"><strong>Explore the docs »</strong></a>
    <br />
    <br />
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project
<div align="center">
  <img src=" " alt="Video tutorial" > <!-- IMAGE 1 OR VIDEO TUTORIAL-->
  <img src="" alt="Project image"  > <!-- IMAGE 2 -->
</div>
Just rewriting Git in python. Why?

Here's why:
* Is fun
* To finally get it

## Classes


<p align="right">(<a href="#readme-top">back to top</a>)</p>

### GitRepository
1. **Description:** the repository object
2. **Attributes:**
   - worktree: the work tree is the path where the files that are meant to be in version control are
   - gitdir: the git directory is the path where git stores its own data. Usually is a child directory of the work tree, called .git
   - conf: is an instance of the class ConfigParser, from the external module configparser, used to read and write INI configuration files

### GitObject
1. **Description:** base class that abstracts the common features of different object types (e.g., blob, commit, tag or tree)
2. **Methods:**
   - init: will be used by the derived class to create a new empty object if needed (optional)
   - deserialize: will be used by the derived class to convert the data into an object (mandatory)
   - serialize: will be used by the derived class to convert the object into a meaningful representation (mandatory)
  
<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [![Python][Python]][Python-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started


### Prerequisites

  * Python version 3.10 or higher

### Installation


<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

Use this space to show useful examples of how a project can be used. Additional screenshots, code examples and demos work well in this space. You may also link to more resources.

_For more examples, please refer to the [Documentation](https://wyag.thb.lt/)_

<p align="right">(<a href="#readme-top">back to top</a>)</p>




<!-- LICENSE -->
## License



<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact



<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

A few of helpful link 

* [Choose an Open Source License](https://choosealicense.com)
* [Python](https://www.python.org/)
* [GIT](https://git-scm.com/doc)
* [WYAG](https://wyag.thb.lt/)



<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS -->

[Python]: https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[Python-url]: https://www.python.org/

