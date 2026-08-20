# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Lesser General Public License for more details.                   *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import FreeCAD
from FreeCAD import Units
import Path
import argparse
import datetime
import shlex
import Path.Base.Util as PathUtil
import Path.Post.Utils as PostUtils
import PathScripts.PathUtils as PathUtils
from builtins import open as pyopen

TOOLTIP = """
This is a postprocessor file for the Path workbench. It is used to
take a pseudo-G-code fragment outputted by a Path object, and output
real G-code suitable for a NUM 750 3-axis mill.
"""

now = datetime.datetime.now()

parser = argparse.ArgumentParser(prog="num750", add_help=False)
parser.add_argument("--no-header", action="store_true", help="suppress header output")
parser.add_argument("--no-comments", action="store_true", help="suppress comment output")
parser.add_argument("--line-numbers", action="store_true", help="prefix with line numbers")
parser.add_argument(
    "--no-show-editor",
    action="store_true",
    help="don't pop up editor before writing output",
)
parser.add_argument("--precision", default="3", help="number of digits of precision, default=3")
parser.add_argument(
    "--preamble",
    help='set commands to be issued before the first command, default="G17 G54 G40 G49 G80 G90\\n"',
)
parser.add_argument(
    "--postamble",
    help='set commands to be issued after the last command, default="M05\\nG17 G54 G90 G80 G40\\nM02\\n"',
)
parser.add_argument(
    "--inches", action="store_true", help="Convert output for US imperial mode (G20)"
)
parser.add_argument(
    "--modal",
    action="store_true",
    help="Output the Same G-command Name USE NonModal Mode",
)
parser.add_argument("--axis-modal", action="store_true", help="Output the Same Axis Value Mode")
parser.add_argument(
    "--no-tlo",
    action="store_true",
    help="suppress tool length offset (G43) following tool changes",
)

TOOLTIP_ARGS = parser.format_help()

# These globals set common customization preferences
OUTPUT_COMMENTS = False
OUTPUT_HEADER = True
OUTPUT_LINE_NUMBERS = False
SHOW_EDITOR = True
MODAL = True
USE_TLO = False
OUTPUT_DOUBLES = False
COMMAND_SPACE = " "
LINENR = 100

UNITS = ""
UNIT_SPEED_FORMAT = "mm/min"
UNIT_FORMAT = "mm"

MACHINE_NAME = "NUM750"
CORNER_MIN = {"x": 0, "y": 0, "z": 0}
CORNER_MAX = {"x": 500, "y": 300, "z": 300}
PRECISION = 3

PREAMBLE = """"""

POSTAMBLE = """M02
%
"""

PRE_OPERATION = """"""
POST_OPERATION = """"""

# Tool Change commands will be inserted before a tool change
TOOL_CHANGE = """M0M61
"""


def processArguments(argstring):
    global OUTPUT_HEADER, OUTPUT_COMMENTS, OUTPUT_LINE_NUMBERS, SHOW_EDITOR
    global PRECISION, PREAMBLE, POSTAMBLE, UNITS, UNIT_SPEED_FORMAT, UNIT_FORMAT
    global MODAL, USE_TLO, OUTPUT_DOUBLES

    try:
        args = parser.parse_args(shlex.split(argstring))
        if args.no_header:
            OUTPUT_HEADER = False
        if args.no_comments:
            OUTPUT_COMMENTS = False
        if args.line_numbers:
            OUTPUT_LINE_NUMBERS = True
        if args.no_show_editor:
            SHOW_EDITOR = False
        PRECISION = args.precision
        if args.preamble is not None:
            PREAMBLE = args.preamble.replace("\\n", "\n")
        if args.postamble is not None:
            POSTAMBLE = args.postamble.replace("\\n", "\n")
        if args.inches:
            UNITS = "G20"
            UNIT_SPEED_FORMAT = "in/min"
            UNIT_FORMAT = "in"
            PRECISION = 4
        if args.modal:
            MODAL = True
        if args.no_tlo:
            USE_TLO = False
        if args.axis_modal:
            OUTPUT_DOUBLES = False
    except Exception:
        return False
    return True


def export(objectslist, filename, argstring):
    if not processArguments(argstring):
        return None
    global UNITS, UNIT_FORMAT, UNIT_SPEED_FORMAT

    for obj in objectslist:
        if not hasattr(obj, "Path"):
            print("the object " + obj.Name + " is not a path. Please select only path and Compounds.")
            return None

    print("postprocessing...")
    gcode = ""

    # write header for NUM750
    if OUTPUT_HEADER:
        gcode += "%001 (PROGRAM_NAME;1)\n"
        gcode += "E60000=-070000\n"
        gcode += "E61000=-177000\n"
        gcode += "E62000=-150000\n"
        gcode += "E50001=040000 E52001=000000\n"
        gcode += "E50002=040000 E52002=000000\n"
        gcode += "E50003=040000 E52003=000000\n"
  
    # Write the preamble
    if OUTPUT_COMMENTS:
        gcode += linenumber() + "(begin preamble)\n"
    for line in PREAMBLE.splitlines():
        gcode += linenumber() + line + "\n"
    gcode += linenumber() + UNITS + "\n"

    for obj in objectslist:
        if not PathUtil.activeForOp(obj):
            continue

        if OUTPUT_COMMENTS:
            gcode += linenumber() + "(begin operation: %s)\n" % obj.Label
            gcode += linenumber() + "(machine units: %s)\n" % (UNIT_SPEED_FORMAT)
        for line in PRE_OPERATION.splitlines(True):
            gcode += linenumber() + line

        coolantMode = PathUtil.coolantModeForOp(obj)

        if OUTPUT_COMMENTS:
            if not coolantMode == "None":
                gcode += linenumber() + "(Coolant On:" + coolantMode + ")\n"
        if coolantMode == "Flood":
            gcode += linenumber() + "M8\n"
        if coolantMode == "Mist":
            gcode += linenumber() + "M7\n"

        gcode += parse(obj)

        if OUTPUT_COMMENTS:
            gcode += linenumber() + "(finish operation: %s)\n" % obj.Label
        for line in POST_OPERATION.splitlines(True):
            gcode += linenumber() + line

        if not coolantMode == "None":
            if OUTPUT_COMMENTS:
                gcode += linenumber() + "(Coolant Off:" + coolantMode + ")\n"
            gcode += linenumber() + "M9\n"

    if OUTPUT_COMMENTS:
        gcode += "(begin postamble)\n"
    for line in POSTAMBLE.splitlines():
        gcode += linenumber() + line + "\n"

    if FreeCAD.GuiUp and SHOW_EDITOR:
        final = gcode
        if len(gcode) > 100000:
            print("Skipping editor since output is greater than 100kb")
        else:
            dia = PostUtils.GCodeEditorDialog()
            dia.editor.setText(gcode)
            result = dia.exec_()
            if result:
                final = dia.editor.toPlainText()
    else:
        final = gcode

    print("done postprocessing.")

    if not filename == "-":
        gfile = pyopen(filename, "w")
        gfile.write(final)
        gfile.close()

    return final


def linenumber():
    global LINENR
    if OUTPUT_LINE_NUMBERS is True:
        LINENR += 10
        return "N" + str(LINENR) + " "
    return ""


def parse(pathobj):
    global PRECISION, MODAL, OUTPUT_DOUBLES, UNIT_FORMAT, UNIT_SPEED_FORMAT

    out = ""
    lastcommand = None
    precision_string = "." + str(PRECISION) + "f"
    currLocation = {}

    params = ["X", "Y", "Z", "A", "B", "C", "I", "J", "F", "S", "T", "Q", "R", "L", "H", "D", "P"]
    firstmove = Path.Command("G0", {"X": -1, "Y": -1, "Z": -1, "F": 0.0})
    currLocation.update(firstmove.Parameters)

    if hasattr(pathobj, "Group"):
        for p in pathobj.Group:
            out += parse(p)
        return out
    else:
        if not hasattr(pathobj, "Path"):
            return out

        for c in pathobj.Path.Commands:
            outstring = []
            command = c.Name
            
            # Добавляем M41 перед M3 или M4 для NUM750 (режим редуктора)
            if command == "M3":
                command = "M41M3"
            elif command == "M4":
                command = "M41M4"
                
            outstring.append(command)

            if MODAL is True:
                if command == lastcommand:
                    outstring.pop(0)

            if c.Name.startswith("(") and not OUTPUT_COMMENTS:
                continue

            if command in ("G84", "G74") and "F" in c.Parameters:
                pitch_mm = float(c.Parameters["F"])
                c.Parameters.pop("F")
                spindle_speed = None
                if "S" in c.Parameters:
                    spindle_speed = float(c.Parameters["S"])
                    c.Parameters.pop("S")
                if UNITS == "G20":
                    pitch = pitch_mm / 25.4
                else:
                    pitch = pitch_mm
                if spindle_speed is not None:
                    feed_rate = pitch * spindle_speed
                    speed = Units.Quantity(feed_rate, UNIT_SPEED_FORMAT)
                    outstring.append("F" + format(float(speed.getValueAs(UNIT_SPEED_FORMAT)), precision_string))
                else:
                    outstring.append("F" + format(pitch, precision_string))

            for param in params:
                if param in c.Parameters:
                    if param == "F" and (currLocation.get(param) != c.Parameters[param] or OUTPUT_DOUBLES):
                        if c.Name not in ["G0", "G00"]:
                            speed = Units.Quantity(c.Parameters["F"], FreeCAD.Units.Velocity)
                            if speed.getValueAs(UNIT_SPEED_FORMAT) > 0.0:
                                outstring.append(param + format(float(speed.getValueAs(UNIT_SPEED_FORMAT)), precision_string))
                        else:
                            continue
                    elif param == "T":
                        outstring.append(param + str(int(c.Parameters["T"])))
                    elif param == "H":
                        outstring.append(param + str(int(c.Parameters["H"])))
                    elif param == "D":
                        outstring.append(param + str(int(c.Parameters["D"])))
                    elif param == "S":
                        outstring.append(param + str(int(c.Parameters["S"])))
                    else:
                        if (not OUTPUT_DOUBLES) and (param in currLocation) and (currLocation[param] == c.Parameters[param]):
                            continue
                        else:
                            if param in ("A", "B", "C"):
                                outstring.append(param + format(float(c.Parameters[param]), precision_string))
                            else:
                                pos = Units.Quantity(c.Parameters[param], FreeCAD.Units.Length)
                                outstring.append(param + format(float(pos.getValueAs(UNIT_FORMAT)), precision_string))

            lastcommand = command
            currLocation.update(c.Parameters)

            # Check for Tool Change:
            if command == "M6":
                # stop the spindle
                for line in TOOL_CHANGE.splitlines(True):
                    out += linenumber() + line
                
                # Add tool number with offset (T2D2M6 format)
                if "T" in c.Parameters:
                    tool_num = int(c.Parameters["T"])
                    out += linenumber() + "T" + str(tool_num) + "D" + str(tool_num) + "M6\n"
                
                # Clear outstring so we don't print "M6" again at the end of the loop
                outstring = []

                if USE_TLO:
                    tool_height = "\nG43 H" + str(int(c.Parameters["T"]))
                    outstring.append(tool_height)

            if command == "message":
                if OUTPUT_COMMENTS is False:
                    outstring = []
                else:
                    outstring.pop(0)

            if len(outstring) >= 1:
                if OUTPUT_LINE_NUMBERS:
                    outstring.insert(0, linenumber())
                for w in outstring:
                    out += w + COMMAND_SPACE
                out += "\n"

        return out
