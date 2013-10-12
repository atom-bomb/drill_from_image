#!/usr/bin/python
#
# Hey, here's a thing:
#
# You can use this bit of python script to generate GCode to drill a PCB based on an image file that you used
# to etch the board.
#
# This script makes GCode to drill the center of sections of an image that are a given color or brightness.
#
# All you need to do is load the image file that you used to etch and color the things you want drilled.
# This should be easy since all of your drills are probably surrounded by traces and all of your traces are
# probably colored black. Just use your favorite graphic editor (such as gimp) to flood fill parts of the board
# that aren't traces or drills, leaving the drills as the only thing that are white.
#
# Run this script on your edited image and you'll get some GCode.
#
# Before you run the GCode, jog the spindle over where you want the topmost, leftmost hole to be drilled and
# zero your machine.
# The GCode will begin my moving over where the bottommost, rightmost hole would be drilled.
# Move your workpiece, return to zero rewind and restart the GCode until your machine lines up with both drills,
# then you can allow the machine to continue to drill your board.
#

from __future__ import print_function

import sys
import math
from PIL import Image
import subprocess
import re
import argparse

class BoundingBox:

  def __init__(self):
    self.coord = [[0, 0], [0, 0]]
    self.empty = 1 

  def intersects(self, box):
    return (((1 ^ self.empty) and (1 ^ box.empty)) and
        ((self.coord[0][0] < box.coord[1][0]) and
        (self.coord[0][1] < box.coord[1][1]) and
        (self.coord[1][0] > box.coord[0][0]) and
        (self.coord[1][1] > box.coord[0][1])))

  def center(self):
    return [self.coord[0][0] + ((self.coord[1][0] - self.coord[0][0]) / 2),
        self.coord[0][1] + ((self.coord[1][1] - self.coord[0][1]) / 2)]

  def boundCoord(self, coord):
    if (self.empty):
      self.coord[0][0] = coord[0]
      self.coord[0][1] = coord[1]
      self.coord[1][0] = coord[0]
      self.coord[1][1] = coord[1]
      self.empty = 0
    else:
      if (coord[0] < self.coord[0][0]):
        self.coord[0][0] = coord[0]
      if (coord[1] < self.coord[0][1]):
        self.coord[0][1] = coord[1]
      if (coord[0] > self.coord[1][0]):
        self.coord[1][0] = coord[0]
      if (coord[1] > self.coord[1][1]):
        self.coord[1][1] = coord[1]

class BoundingBoxList:

  def __init__(self):
    self.boxes = []

  def addBox(self, box):
    for oldBox in self.boxes:
      if (oldBox.intersects(box)):
        return
    self.boxes.append(box)

# use ImageMagick to figure out how many pixels per inch or cm in the image file
def getDensity(filename, units = "PixelsPerInch"):
  pipe = subprocess.Popen(["identify", "-format", "%x,%y", "-units", units, filename],
      stdout=subprocess.PIPE)
  res = re.sub('[\t\r\n"]', '', pipe.communicate()[0]).split(',')
  xres = float(res[0].split(' ')[0])
  yres = float(res[1].split(' ')[0])
  return [xres, yres]

# make a list of drill points from an image map
class DrillMap:

  def __init__(self, filename, units = 'Inches', density = [], rgbThresh = 127 * 3):
    self.image = Image.open(filename)
    self.pixmap = self.image.load()
    if (len(density) == 0):
      if (units == 'Inches'):
        self.density = getDensity(filename)
      else:
        cmDensity = getDensity(filename, units = 'PixelsPerCentimeter')
        self.density = [float(cmDensity[0]) / 10, float(cmDensity[1]) / 10]
    else:
      self.density = density ;
    self.rgbThresh = rgbThresh ;
    self.boxlist = BoundingBoxList()
    self.drillList = []
    self.findBoxes()
    self.makeDrillList()

  def coordOffset(self, coord):
    return [float(coord[0]) / float(self.density[0]), float(coord[1]) / float(self.density[1])]

  def isCoordOn(self, coord):
    pixel = self.pixmap[coord[0], coord[1]]
    if (self.image.mode == "RGB"):
      sum = pixel[0] + pixel[1] + pixel[2]
      return (sum > self.rgbThresh)
    if (self.image.mode == "1"):
      return pixel

  def scanLeftToBox(self, coord, box):
    y = coord[1]
    x = coord[0]
    while ((x >= 0) and self.isCoordOn([x, y])):
      box.boundCoord([x, y])
      x = x - 1
    return (x != coord[0])

  def scanRightToBox(self, coord, box):
    y = coord[1]
    x = coord[0]
    while ((x <= self.image.size[1] - 1) and self.isCoordOn([x, y])):
      box.boundCoord([x, y])
      x = x + 1
    return (x != coord[0])

  def scanLineToBox(self, coord, box):
    return (self.scanLeftToBox(coord, box) or self.scanRightToBox(coord, box))

  def scanUpperLineToBox(self, coord, box):
    if (coord[1] > 0):
      upperCoord = [int(box.center()[0]), coord[1] - 1]
      if (self.scanLineToBox(upperCoord, box)):
        self.scanUpperLineToBox(upperCoord, box)

  def scanLowerLineToBox(self, coord, box):
    if (coord[1] < self.image.size[1] - 1):
      lowerCoord = [box.center()[0], coord[1] + 1]
      if (self.scanLineToBox(lowerCoord, box)):
        self.scanLowerLineToBox(lowerCoord, box)

  def scanToBox(self, coord):
    box = BoundingBox() 
    if (self.scanRightToBox(coord, box)):
      self.scanUpperLineToBox(coord, box)
      self.scanLowerLineToBox(coord, box)
    return box

  def findBoxes(self):
    y = 0
    while (y < self.image.size[1] - 1):
      x = 0
      while (x < self.image.size[0] - 1):
        if (self.isCoordOn([x, y])):
          newBox = self.scanToBox([x, y])
          if (not newBox.empty):
            self.boxlist.addBox(newBox)
            x = newBox.coord[1][0] + 1
          else:
            x += 1
        else:
          x += 1
      y += 1

  def makeDrillList(self):
    for eachBox in self.boxlist.boxes:
      self.drillList.append(self.coordOffset(eachBox.center()))

class GCode:
  GCodeCommands = {'Mach3': { 
               'Message': '(', 
               'Stop': 'M0',
               'Sleep': 'M01',
               'SpindleCW': 'M03',
               'SpindleCCW': 'M04',
               'SpindleStop': 'M05',
               'ToolChange': 'M06',
               'Pause': 'M60',
               'FastMove': 'G0',
               'SlowMove': 'G1',
               'Dwell': 'G4',
               'InchesMode': 'G20',
               'MillimetersMode': 'G21',
               'MoveToOrigin': 'G28',
               'ClearToolOffet': 'G49',
               'Drill': 'G81',
               'DrillWithDwell': 'G82',
               'AbsoluteMode': 'G90',
               'RelativeMode': 'G91',
               'SetPosition': 'G92',
               },
      'EMC': { 
               'Message': '(MSG,', 
               'Stop': 'M0',
               'Sleep': 'M01',
               'SpindleCW': 'M03',
               'SpindleCCW': 'M04',
               'SpindleStop': 'M05',
               'ToolChange': 'M06',
               'Pause': 'M60',
               'FastMove': 'G0',
               'SlowMove': 'G1',
               'Dwell': 'G4',
               'InchesMode': 'G20',
               'MillimetersMode': 'G21',
               'MoveToOrigin': 'G28',
               'ClearToolOffet': 'G49',
               'Drill': 'G81',
               'DrillWithDwell': 'G82',
               'AbsoluteMode': 'G90',
               'RelativeMode': 'G91',
               'SetPosition': 'G92',
               }}

  def __init__(self, theGCodeType):
    self.variant = theGCodeType

  def Comment(self, string):
    return " ; " + string 

  def Message(self, string):
    return self.GCodeCommands[self.variant]['Message'] + string + " )"

  def Pause(self):
    return self.GCodeCommands[self.variant]['Pause']

  def Spindle(self, Mode):
    SpindleModes = {'Stop': 'SpindleStop', 'CW': 'SpindleCW', 'CCW': 'SpindleCCW'}
    return self.GCodeCommands[self.variant][SpindleModes[Mode]]

  def Units(self, theUnits):
    if (theUnits == 'Inches'):
      return self.GCodeCommands[self.variant]['InchesMode']
    else:
      return self.GCodeCommands[self.variant]['MillimetersMode']

  def Absolute(self, isAbsolute = True):
    if (isAbsolute):
      return self.GCodeCommands[self.variant]['AbsoluteMode']
    else:
      return self.GCodeCommands[self.variant]['RelativeMode']

  def _CommonArgs(self, X = None, Y = None, Z = None, rate = None):
    OutStr = ''
    if (X != None):
      OutStr += ' X' + format(X, ".4f")
    if (Y != None):
      OutStr += ' Y' + format(Y, ".4f")
    if (Z != None):
      OutStr += ' Z' + format(Z, ".4f")
    if (rate != None):
      OutStr += ' F' + format(rate, ".4f")
    return OutStr

  def Move(self, X = None, Y = None, Z = None, rate = None, speed='Fast'):
    OutStr = self.GCodeCommands[self.variant][speed + 'Move']
    OutStr += self._CommonArgs(X = X, Y = Y, Z = Z, rate = rate)
    return OutStr

  def Dwell(self, seconds = 1):
    OutStr = self.GCodeCommands[self.variant]['Dwell'] + ' P' + `seconds`
    return OutStr

  def Drill(self, X = None, Y = None, Z = None, retract = None, seconds = None, rate = None):
    if (seconds != None):
      OutStr = self.GCodeCommands[self.variant]['DrillWithDwell']
      OutStr += ' P' + `seconds`
    else:
      OutStr = self.GCodeCommands[self.variant]['Drill']
    OutStr += self._CommonArgs(X = X, Y = Y, Z = Z, rate = rate)
    if (retract != None):
      OutStr += ' R' + `retract`
    return OutStr


# --------  execution starts here
# parse parameters
# TODO: add density parameter & drill color parameter & check for ImageMagick
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_true', help='spew possibly useless output')
parser.add_argument('-m', '--millimeters',
    action='store_const', dest='units', const='Millimeters', help='set units to millimeters')
parser.add_argument('-i', '--inches',
    action='store_const', dest='units', const='Inches', help='set units to inches')
parser.add_argument('-a', '--mach3',
    action='store_const', dest='gcode', const='Mach3', help='set gcode type to mach3')
parser.add_argument('-e', '--emc',
    action='store_const', dest='gcode', const='EMC', help='set gcode type to emc')
parser.add_argument('-s', '--safe',
    nargs=1, default='0.25', type=float, help='safe height')
parser.add_argument('-d', '--drill',
    nargs=1, default='-0.2', type=float, help='drill depth')
parser.add_argument('-p', '--dwell',
    nargs=1, default='0.5', type=float, help='drill dwell')
parser.add_argument('-f', '--feed',
    nargs=1, default='100', type=float, help='feed rate')
parser.add_argument('input')
args = parser.parse_args()

if (args.gcode == None):
  args.gcode = 'Mach3'

if (args.units == None):
  args.units = 'Inches'

theMap = DrillMap(args.input, args.units)

# make drill coordinates relative to first drill
if (theMap.drillList):
  firstCoord = theMap.drillList[0]
  relativeDrillList = []
  for drill in theMap.drillList:
    newCoord = [drill[0] - firstCoord[0], drill[1] - firstCoord[1]]
    relativeDrillList.append(newCoord)

# output gcode for the list of drills

# init machine, set units, zero axes
gc = GCode(args.gcode)
print(gc.Spindle('Stop'))
print(gc.Units(args.units))
print(gc.Absolute())
print(gc.Pause(), gc.Comment('Check that tool is aligned with first drill'))
print(gc.Move(Z = args.safe))

# move to last drill position and pause
lastDrill = len(relativeDrillList) - 1
print(gc.Move(X = relativeDrillList[lastDrill][0], Y = relativeDrillList[lastDrill][1]))
print(gc.Pause())
print(gc.Pause(), gc.Comment('Check that tool is aligned with last drill'))
print(gc.Spindle('CW'))
print(gc.Dwell(3))

print(gc.Message('Drilling'))

# move to each drill position and drill
for eachDrill in relativeDrillList:
  print(gc.Drill(X = eachDrill[0], Y = eachDrill[1], Z = args.drill, retract = args.safe, seconds = args.dwell))

# end of GCode program
print(gc.Spindle('Stop'))
print(gc.Pause())
