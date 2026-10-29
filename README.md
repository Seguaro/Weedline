<p align="center">
  <img src="docs/icon.png" width="96" alt="Weed Lines icon">
</p>


# Weed Lines

**Smart weeding cuts for single-color vinyl.** Version 0.1.0-beta

Weed Lines is a free Windows program for anyone who cuts vinyl lettering on a Cricut or similar cutter. You give it the SVG file of your design, and it creates the negative (the waste around your letters) already broken into small, easy-to-weed pieces.

Most people do this by hand in Cricut Design Space: draw a rectangle over the design, slice it, and then slice the waste into a grid of 1-inch boxes. A grid works, but its lines fall wherever they fall, often in big open areas or running into the letters. Weed Lines places its cuts where the waste is already narrow, such as the gap between two letters or between the bottom of one line and the top of the next, so each cut is short and every piece lifts away cleanly.

It was made for cake toppers ("Happy Birthday" plus a name in a script font, with a few flourishes) but works for any single-color lettering or design.

![Example: each colored area is one waste piece, red lines are the weed cuts](docs/example_preview.png)

## What it does

1. Reads your SVG and merges the lettering into solid shapes, including script letters that overlap where they join.
2. Draws a rectangle around the design with a 1/4 inch margin and keeps everything except your lettering. That's the waste.
3. Closes off hairline openings first. Script fonts often leave a tiny gap at the top of an "a" or the bottom of a "p", which would tie the inside of the letter to the big outside piece. Weed Lines cuts across each of those so the inside of the letter weeds on its own.
4. Splits the rest of the waste with short cuts across the narrowest gaps until no piece is larger than about 1.5 square inches or longer than 2 inches on a side. It avoids cuts that would leave tiny slivers you'd have to pick out with a hook.
5. Saves two files next to your original:
   - `yourfile_weed_cut.svg`: the waste pieces as separate closed shapes, ready to upload to Design Space
   - `yourfile_weed_preview.png`: a picture of the result, with each waste piece in its own tint and the weed cuts in red, so you can check it before you cut

The Randy topper in the example took about 20 seconds and came out with 55 cuts and 61 pieces.

## Download and install

Download `WeedLines-0.1.0-beta-setup.exe` from the [Releases](../../releases) page and run it.

**About the "Windows protected your PC" warning.** The installer isn't code-signed (signing certificates cost hundreds of dollars a year, and this is a free hobby project), so Windows SmartScreen will show a blue warning the first time you run it. Click **More info**, then **Run anyway**. Your antivirus may also ask about it for the same reason. The full source code is in this repository if you'd like to see exactly what it does, or build it yourself.

During setup you can choose to add a desktop icon and an **Add weed lines** entry on the right-click menu for SVG files. No administrator rights are needed unless you choose to install it for all users. You can uninstall it any time from Windows Settings, under Apps.

## Using it

**Prepare your file first.** In Adobe Illustrator, convert all text to outlines (Type > Create Outlines) and save as SVG. Weed Lines reads shapes, not live text, and it will tell you if it finds nothing to work with. Everything in the file is treated as one color.

Then use any of these:

- **Double-click Weed Lines** and pick one or more SVG files. Hold Ctrl or Shift to select several and it'll do them one after another.
- **Drag SVG files** onto the Weed Lines icon.
- **Right-click an SVG** in File Explorer and choose **Add weed lines**. On Windows 11 it's under **Show more options**.

A progress window shows what it's doing. When it's finished, it lists the number of cuts and pieces and the finished size, with buttons to open the preview or show the files in their folder.

**If you run it again on the same file,** it asks before replacing anything: **Yes** replaces the old results, **No** saves new copies as `yourfile_weed_cut (2).svg`, and **Cancel** skips that file.

**In Design Space,** upload `yourfile_weed_cut.svg` and check that the size matches your design before you cut. Design Space sometimes rescales SVGs on import. Cut it as you normally would. Each piece is a separate shape, just like the result of a Slice.

## Command line options

You can also run it from a command prompt, which lets you change the settings.

```
weedlines topper.svg
weedlines "D:\Cake Toppers\topper.svg" --margin 0.375
weedlines topper.svg --amax 1.0 --emax 1.75 --amin 0.08
```

| Option         | Default | What it does                                                 |
| -------------- | ------- | ------------------------------------------------------------ |
| `--margin`     | 0.25    | Space between the design and the edge of the rectangle, in inches |
| `--amax`       | 1.5     | Largest waste piece allowed, in square inches. Smaller means more cuts. |
| `--emax`       | 2.0     | Longest side a waste piece may have, in inches               |
| `--amin`       | 0.12    | Smallest piece a cut is allowed to create, in square inches. This keeps it from making slivers. |
| `--lmax`       | 0.6     | Preferred longest cut, in inches. It only goes longer if it has to. |
| `--overwrite`  |         | Replace earlier results without asking                       |
| `--no-preview` |         | Don't make the preview PNG                                   |
| `--console`    |         | Use text output in the command prompt even when no file is given |
| `--help`       |         | List all options                                             |

For finer pieces, try `--amax 1.0 --emax 1.75 --amin 0.08`. On the Randy example that gives about 76 cuts instead of 55.

If you give it a file name in a command prompt, it shows a text progress bar there and asks about overwriting in the prompt. Double-clicking, dragging, or using the right-click menu uses the window instead.

## Running from source

Weed Lines is a single Python script. It needs Python 3.10 or newer.

```
py -m pip install -r requirements.txt
py weedlines.py
```

`weedlines.bat` is a small helper for running the script from a command prompt or dragging files onto it. It keeps the window open at the end so you can read the results.

### Building the Windows program and installer

1. Install PyInstaller: `py -m pip install pyinstaller`

2. From this folder, with `weedlines.ico` and `splash.png` alongside `weedlines.py`, run:

   ```
   py -m PyInstaller --onedir --noconsole --icon=weedlines.ico --splash=splash.png weedlines.py
   ```

   The program is built in `dist\weedlines\`. The `build` folder is PyInstaller's scratch space and can be deleted.

3. Install [Inno Setup](https://jrsoftware.org/isinfo.php), open `installer\weedlines.iss`, and click **Compile**. The installer is created in `installer\Output\`.

Tip: building inside a fresh virtual environment with only the packages in `requirements.txt` keeps the program much smaller, because PyInstaller won't pick up unrelated packages from your main Python install.

## How it works

For those curious about the details: the outlines are sampled into polygons and merged with the nonzero fill rule using [Shapely](https://shapely.readthedocs.io/). Possible cuts come from a Delaunay triangulation of points along every edge of the waste: the short triangle edges that stay inside the waste are exactly the places where it's narrow. Weed Lines first cuts any very narrow neck that has a real pocket behind it, which closes hairline openings into letters. Then it repeatedly takes the largest piece that's still too big and splits it with the cut that scores best on length divided by the square root of the smaller resulting piece. That favors short cuts that leave reasonably balanced pieces.

## Limitations

This is a beta. It handles one color at a time, and so far it has only been tested with SVG files saved from Adobe Illustrator. It reads outlined paths and the simple clipping masks Illustrator adds. Files from other programs, such as Inkscape or Affinity, may use different units or other shape types and might not come out right yet. The installer is for 64-bit Windows, but the script itself runs anywhere Python and the libraries run. Very large or very detailed designs take longer.

If something doesn't work, please open an issue on this page and attach the SVG if you can.

## License

Weed Lines is free and open source under the [MIT License](LICENSE). You can use it, share it, and change it. It's provided as is, without any warranty, and the author isn't liable for any problems that come from using it. Please check your results before cutting expensive material.

Copyright (c) 2026 George Sladic, [Studio 57 Design](https://studio57design.com)
