# SublimeTerminal

SublimeTerminal is a basic terminal emulation plugin for Sublime Text 3. It relies on the python library `pyte` for most of the actual emulation.

At present it is severly limited, in that it only supports SublimeText's insert and delete modifications. I have no idea, for example, how it would behave if you try to undo a change to the view.

At present, SublimeTerminal is hard-coded to run `bash`. However, modifying this should be pretty easy if you prefer a different terminal.

## Installation

I haven't packaged this as a sublime text package. For now, it can be installed by cloning it into your ST packages
folder.
