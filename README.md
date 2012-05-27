This is a FUSE interface to a time machine backup. It is very basic; it
supports read operations, and knows how to read the most recent
successful backup. 

## Motivation ##

My old macbook died one weekend. I used time machine to back it up. I
didn't have another mac to restore the backup onto, and didn't
particularly want to immediately buy another one to replace the dead
one. Linux has HFS+ support, but doesn't know how to interpret the
extensions associated with time machine; this means it's possible to
restore data from a time machine backup onto Linux, but also makes it a
bit of an ordeal. I thought that a FUSE interface would be an easy way
to bridge the gap between Linux's view of the HFS+ filesystem and what
one would expect to see on a Mac, so I wrote this.

## Requirements ##

The only dependencies that I'm aware of are fuse and fuse-python. Note
that I've only tested it on Linux; it's possible that it could work on
other unix-like operating systems, but that's not guaranteed and not
tested.

## Use ##

Assuming that you're running as the same uid as you had on your mac,
doing:

```
python fuse-tm.py <mountpoint> --hfs-path=<hfs-path> --hostname=<hostname>
```

should do it. mountpoint is the folder that you want FUSE to mount on.
hfs_path is the path to your mounted time machine. hostname is the hostname of
the Mac that you're restoring. You can then interact with mountpoint as if it
were your time machine on your mac.

## Limitations ##

You can't write to the time machine filesystem. I wanted the tool to
allow me to restore data from a time machine backup onto my new Linux
box, so I didn't have any use for write capabilities.

For it to work correctly, you'll probably need to run the FUSE process
with the same uid as your user on your mac. I haven't investigated
whether there's an easy and automatic way to do this.

As mentioned, it only knows how to interact with the most recent
available backup. This would be easy to change, but I don't really have
a use for that functionality so I didn't bother.

## Bugs ##

I'm not aware of any specific bugs. It's software that's undergone
limited testing (by me, restoring my backups), so it's very likely that
there are bugs. If you think you've found a bug, please open an issue on
github [1].

## Author ##

Kevan Carstensen <kacarstensen@csupomona.edu>

[1] https://github.com/isnotajoke/fuse-time-machine
