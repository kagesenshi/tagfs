Tag based FUSE filesystem utilizing Tracker
============================================

Dependencies (Fedora)
---------------------

Install the following deps::

   dnf install python3-fusepy zenity -y

Using
------

Mount the filesystem using::

  mkdir ~/Tags
  python3 tagfs.py ~/Tags


Nautilus script
----------------

Install the provided Nautilus script to easily tag your documents::

   cp nautilus-scripts/Tag ~/.local/share/nautilus/scripts/
   chmod +x ~/.local/share/nautilus/scripts/Tag


Features
---------

* Top level directory consist of tags, creating a directory will create a tag
  in tracker.

* 2nd level directories consist of symlinks to tagged files/directories.
  Symlinking a file into these directories will tag the file

* Deleting directories/symlinks will delete tag metadata

 
Limitations
------------

* Filenames are appended with the internal tracker UUID to handle cases where if there are 
  2 files tagged with the same tag. So filenames might be a bit messy.

