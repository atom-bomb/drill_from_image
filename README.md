drill_from_image
================

Hey, here's a thing:

You can use this bit of python script to generate GCode to drill a PCB based on
an image file that you used to etch the board.

This script makes GCode to drill the center of sections of an image that are a
given color or brightness.

All you need to do is load the image file that you used to etch and color the
things you want drilled. This should be easy since all of your drills are
probably surrounded by traces and all of your traces are probably colored black.
Just use your favorite graphic editor (such as gimp) to flood fill parts of the
board that aren't traces or drills, leaving the drills as the only thing that
are white.

Run this script on your edited image and you'll get some GCode.

Before you run the GCode, jog the spindle over where you want the topmost,
leftmost hole to be drilled and zero your machine. The GCode will begin my
moving over where the bottommost, rightmost hole would be drilled.

Move your workpiece, return to zero rewind and restart the GCode until your
machine lines up with both drills, then you can allow the machine to continue to
drill your board.

