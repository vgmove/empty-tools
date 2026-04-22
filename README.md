# Empty Tools
<div align="center">
  <img src=".meta/preview_1.png" width="800">
</div> <br>

Blender3D addon adds tools for working with Empty objects. <br>
Helps organize the model structure after exporting from CAD programs.

## Features
- Cleaning the scene from Empty objects
- Converting Empty objects into collections
- Creating an Empty object based on the active object
- Batch resizing Empty objects

## How it works
<h3>Remove Empty</h3>

- <b>Blank Hierarchy.</b><br>
Removes all Empty objects that have no child objects or whose children are all Empty objects, forming an empty branch of the hierarchy.
- <b>Excess Empties.</b><br>
Removes all Empty objects that have exactly one non-Empty child.
- <b>Keep Structure.</b><br>
A mode in which Empty objects are not removed if they have an Empty child, thereby leaving the scene structure untouched.
- <b>Used in Modifiers.</b><br>
A mode in which Empty objects are not removed if they are used in modifiers.

<div align="center">
  <img src=".meta/preview_2.png" height="500">
</div>

<h3>Convert to Collection</h3>

- <b>Current Collection.</b><br>
The new collection is created within the collection where the selected Empty objects are located. <br>
- <b>Keep Parent.</b><br>
The selected Empty object and all its children are moved into the new collection. <br>

<h3>Create by Active Object</h3>

- <b>Align Empty.</b><br>
The created Empty object inherits the orientation of the active object. <br>
- <b>Name from Object.</b><br>
The created Empty object takes the name of the active object. The default name is Group. <br>

<h3>Parameters</h3>

- <b>Empty Size.</b><br>
Changes the size of all selected Empty objects. <br>

## Installation
Download the .zip file and follow the [official instructions](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html) for installing addons (Install from Disk).

## Download
Link for download [last release](https://github.com/vgmove/empty-tools/releases/download/release_v1.0.0/empty_tools.zip).
