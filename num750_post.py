# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *   Copyright (c) 2014 sliptonic <shopinthewoods@gmail.com>               *
# *   Postprocessor for NUM 750 CNC milling machine                         *
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
Postprocessor for NUM 750 3-axis milling machine.
"""

now = datetime.datetime.now()

parser = argparse.ArgumentParser(prog="num750", add_help=False)
parser.add_argument("--no-header", action="store_true", help="suppress header output")
parser.add_argument("--no-comments", action="store_true", help="suppress comment output")
parser.add_argument("--line-numbers", action="store_true", help="prefix with line numbers")
parser.add_argument("--no-show-editor", action="store_true", help="don't pop up editor")
parser.add_argument("--precision", default="3", help="number of digits of precision")
parser.add_argument("--preamble", help="preamble commands")
parser.add_argument("--postamble", help="postamble commands")
parser.add_argument("--inches", action="store_true", help="imperial mode (G20)")
parser.add_argument("--modal", action="store_true", help="modal mode")
parser.add_argument("--axis-modal", action="store_true", help="axis modal mode")
parser.add_argument("--no-tlo", action="store_true", help="suppress G43")

TOOLTIP_ARGS = parser.format_help()

# === НАСТРОЙКИ ДЛЯ NUM750 ===
OUTPUT_COMMENTS = False
OUTPUT_HEADER = True
OUTPUT_LINE_NUMBERS = False
SHOW_EDITOR = True
MODAL = True
USE_TLO = False
OUTPUT_DOUBLES = False
COMMAND_SPACE = " "
LINENR = 100
TOOL_COUNT = 0  # Счётчик инструментов
LINE_NUM = 0  # Счётчик номеров строк N1, N2, N3

UNITS = ""
UNIT_SPEED_FORMAT = "mm/min"
UNIT_FORMAT = "mm"

MACHINE_NAME = "NUM750"
CORNER_MIN = {"x": 0, "y": 0, "z": 0}
CORNER_MAX = {"x": 500, "y": 300, "z": 300}
PRECISION = 0  # Без знаков после запятой

PREAMBLE = """"""
POSTAMBLE = """M02
%
"""

PRE_OPERATION = """"""
POST_OPERATION = """"""

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
            print("the object " + obj.Name + " is not a path.")
            return None

    print("postprocessing...")
    gcode = ""

    # Заголовок NUM750
    if OUTPUT_HEADER:
        gcode += "%006 (PROGRAM_NAME;1)\n"
        gcode += "E60000=-070000\n"
        gcode += "E61000=-177000\n"
        gcode += "E62000=-150000\n"
        gcode += "E50001=040000 E52001=000000\n"
        gcode += "E50002=040000 E52002=000000\n"
        gcode += "E50003=040000 E52003=000000\n"

    # Preamble (пустой для NUM750)
    for line in PREAMBLE.splitlines():
        gcode += linenumber() + line + "\n"

    # UNITS добавляем только если не пустой
    if UNITS:
        gcode += linenumber() + UNITS + "\n"

    for obj in objectslist:
        if not PathUtil.activeForOp(obj):
            continue

        # Пропускаем операцию Fixture (G54)
        if obj.Label == "Fixture":
            continue

        if OUTPUT_COMMENTS:
            gcode += linenumber() + "(begin operation: %s)\n" % obj.Label

        for line in PRE_OPERATION.splitlines(True):
            gcode += linenumber() + line

        # Охлаждение
        coolantMode = PathUtil.coolantModeForOp(obj)
        if coolantMode == "Flood":
            gcode += linenumber() + "M8\n"
        elif coolantMode == "Mist":
            gcode += linenumber() + "M7\n"

        # Обработка операций
        gcode += parse(obj)

        if OUTPUT_COMMENTS:
            gcode += linenumber() + "(finish operation: %s)\n" % obj.Label

        for line in POST_OPERATION.splitlines(True):
            gcode += linenumber() + line

        # Выключение охлаждения
        if coolantMode != "None":
            gcode += linenumber() + "M9\n"

    # Postamble
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
    global LINE_NUM
    LINE_NUM += 1
    out += "N" + str(LINE_NUM) + " "
    command = "M41M3"
elif command == "M4":
    global LINE_NUM
    LINE_NUM += 1
    out += "N" + str(LINE_NUM) + " "
    command = "M41M4"

            outstring.append(command)

            if MODAL is True:
                if command == lastcommand:
                    outstring.pop(0)

            if c.Name.startswith("(") and not OUTPUT_COMMENTS:
                continue

            # Обработка параметров
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
    global TOOL_COUNT
    TOOL_COUNT += 1
    
    # M0M61 только для 2-го и последующих инструментов
    if TOOL_COUNT > 1:
        for line in TOOL_CHANGE.splitlines(True):
            out += linenumber() + line
    
    # Add tool number with offset (T1D1M6 format)
    if "T" in c.Parameters:
        tool_num = int(c.Parameters["T"])
        out += linenumber() + "T" + str(tool_num) + "D" + str(tool_num) + "M6\n"
    
    # Clear outstring so we don't print "M6" again at the end of the loop
    outstring = []

            if command == "message":
                if OUTPUT_COMMENTS is False:
                    outstring = []
                else:
                    outstring.pop(0)

            # Пропускаем пустые команды
            if len(outstring) >= 1:
                if outstring == ["G0"] or outstring == ["G1"]:
                    outstring = []

            if len(outstring) >= 1:
                if OUTPUT_LINE_NUMBERS:
                    outstring.insert(0, linenumber())
                for w in outstring:
                    out += w + COMMAND_SPACE
                out += "\n"

        return out
