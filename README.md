# LeetFS

A simple in-memory filesystem that mirrors accepted submissions on LeetCode.
LeetFS has been implemented using FUSE - note this means that this won't work on Windows.

## Installation

LeetFS requires `retry`, and `requests`, which can be installed by running the following command:
```
pip3 install retry requests
```

LeetFS also needs a cookies file populated with the login cookies for the user. One way of creating the cookies file is to login to LeetCode on the browser and then copying the contents of the cookie header into a text file.

Create an empty directory to be used as the mount point for the filesystem (e.g. `mkdir ~/leetcode_submissions`)

## Use

Once a mount point is ready and a cookies file has been created, the following command starts the filesystem.

```
 python3 leetfs.py --mount_point=$HOME/leetcode_submissions --cookies_file=cookies.txt
```

The first run may take a while to fetch all the submissions from the website. It will write out the data into a local json file so that subsequent runs start faster and only fetch any newer submissions.
