from ast import Call
from enum import Enum
from math import inf
from msvcrt import getch
from os import path
from typing import Callable
from easygui import fileopenbox
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from more_itertools import peekable
from numpy import ndarray
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.tree import Tree
from yaml import YAMLError, safe_load

ESCAPE_CODE_CONVERSIONS = {"H": "↑", "P": "↓", "K": "←", "M": "→"}
SELECTED_STYLE = Style(color="light_sky_blue1", bold=True )
FREQ_UNITS = {"ghz": 1000000000, "mhz": 1000000, "khz": 1000, "hz": 1}
FREQ_NAMES = {"ghz": "GHz", "mhz": "MHz", "khz": "kHz", "hz": "Hz"}
PARAMETER_LABELS = {"db": "Magnitude (dB)", "ma": "Magnitude (Absolute)", "ri": "Real"}
IMAGINARY_LABELS = {"db": "Angle (°)", "ma": "Angle (°)", "ri": "Imaginary"}
PLOT_XLABEL = "Frequency (#)"

# class for loading and storing 2-port touchstone files
class S2P:
  S_PARAMS = ["S11", "I11", "S21", "I21", "S12", "I12", "S22", "I22"]

  def __init__ (self):
    self.path = ""
    self.freq_units = ""
    self.parameter_units = ""
    self.freq: list[float] = []
    # initialize the s_param array
    self.s_params: list[list[float]] = [[] for i in range(len(self.S_PARAMS))]
  
  def load_s2p (self, file: str) -> None:
    # grab the files name to use as "path"
    raw_path = path.basename(file)
    self.path = raw_path.split("\\")[-1].replace(".s2p","")
    # load the file as an array of lines
    data = open(file, "r")
    lines = data.readlines()
    i = 0
    # skip through all comments
    while "#" not in lines[i]:
        i += 1
    # read the option line
    options = lines[i].split()
    init_freq_units = options[1].lower()
    self.parameter_units = options[3].lower()
    # Check if the file is an S file
    if not options[2].lower() == "s":
      # Ahh panic
      quit()
    i += 1
    # read the s params
    while i < len(lines):
      values = lines[i].split()
      # Convert to Hz then to wahtever we are using in the settings
      self.freq.append(float(values[0]) * FREQ_UNITS[init_freq_units] / FREQ_UNITS[settings["plot_options"]["freq_units"]])
      for s in range(len(self.S_PARAMS)):
        self.s_params[s].append(float(values[s + 1]))
      i += 1
  
  def get_sparam (self, param: str):
    return (self.freq, self.s_params[self.S_PARAMS.index(param)])

# Loaded Data
s2ps: list[S2P] = []
graph_items: list[tuple[str, str]] = []
cursor_pos = 0
view_path = -1
exit = False

class Command:
  
  def __init__(self, keybind: str, description: str, include_tags: list[Enum], exclude_tags: list[Enum], function: Callable[... , None]):
    self.keybind = keybind
    self.description = description
    self.include_tags = include_tags
    self.exclude_tags = exclude_tags
    self.function = function

  class States(Enum):
    # Enum for representing the states that the program could be in for the purpose of filtering commands
    general_command = 1 # Command can be used anytime no mater what is highlighted
    dependent_command = 2 # Command can only be used if something specific is highlighted
    s2ps_loaded = 3
    s2p_highlighted = 101
    s2p_nopaths = 102
    s2p_allpaths = 103
    s2p_somepaths = 104
    s2p_allspaths = 105
    s2p_allipaths = 106
    param_highlighted = 201
    param_selected = 202
    param_unselected = 203
  
  def __str__(self):
    return settings["keybinds"][self.keybind].upper() + " " + self.description

  @staticmethod
  def get_current_states(base_state: Enum) -> list[Enum]:
    global cursor_pos, graph_items, s2ps, view_path
    # Add base state
    states = [base_state]

    # Check any s2ps are loaded
    if len(s2ps) > 0:
      states.append(Command.States.s2ps_loaded)

    # Check if we have a s2p highlighted
    if view_path == -1:
      states.append(Command.States.s2p_highlighted)
    # Check how many selected paths are for the s2p we are highlighting
    num_of_selected_paths = len([x for x in graph_items if x[0] == s2ps[cursor_pos].path])
    if Command.States.s2p_highlighted in states and num_of_selected_paths == 0:
      # If 0 then we no paths
      states.append(Command.States.s2p_nopaths)
    elif Command.States.s2p_highlighted in states and num_of_selected_paths == len(S2P.S_PARAMS):
      # If max then we have all paths
      states.append(Command.States.s2p_allpaths)
    elif Command.States.s2p_highlighted:
      # Otherwise we have some pathes
      states.append(Command.States.s2p_somepaths)
    # Check if all s params are loaded
    if Command.States.s2p_highlighted in states and len([x for x in graph_items if x[0] == s2ps[cursor_pos].path and "S" in x[1]]) == 4:
      states.append(Command.States.s2p_allspaths)
    # Check if all i params are loaded
    if Command.States.s2p_highlighted in states and len([x for x in graph_items if x[0] == s2ps[cursor_pos].path and "I" in x[1]]) == 4:
      states.append(Command.States.s2p_allipaths)
    
    # Check if we have a param highlighted
    if view_path != -1 and cursor_pos > 0:
      states.append(Command.States.param_highlighted)
    # Check if the param that we have highlighted is selected
    if Command.States.param_highlighted in states and (s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1]) in graph_items:
      states.append(Command.States.param_selected)
    elif Command.States.param_highlighted in states:
      states.append(Command.States.param_unselected)
    
    # Return the list
    return states

  def is_command_valid(self, base_state: Enum) -> bool:
    # Get a list of all current states
    states = Command.get_current_states(base_state)
    # Check that the include tags are met
    for tag in self.include_tags:
      if not tag in states:
        return False
    # Check that none of the exclude tags are met
    for tag in self.exclude_tags:
      if tag in states:
        return False
    
    # All checks passed, return true
    return True
  
  def is_command_executable(self, key_press: str) -> bool:
    # Check if the key pressed matches the keybind
    if key_press != self.keybind:
      return False
    # Check that the command is valid
    if not (self.is_command_valid(Command.States.general_command) or self.is_command_valid(Command.States.dependent_command)):
      return False
    
    # All checks passed, return true
    return True

  def get_funciton(self) -> Callable[..., None]:
    return self.function

# COMMANDS
commands: list[Command] = [
  Command("load_keybind", "to load a file", [Command.States.general_command], [], lambda: load_file()),
  Command("graph_keybind", "to view a graph", [Command.States.general_command],[], lambda: generate_graph(False)),
  Command("delta_keybind", "to view a graph with deltas", [Command.States.general_command],[], lambda: generate_graph(True)),
  Command("cursorup_keybind", "to move the cursor up", [Command.States.general_command], [], lambda: cursor_up()),
  Command("cursordown_keybind", "to move the cursor down", [Command.States.general_command], [], lambda: cursor_down()),
  Command("negative_item", "to select all items", [Command.States.s2ps_loaded, Command.States.dependent_command, Command.States.s2p_highlighted], [Command.States.s2p_allpaths], lambda: add_graph_item(s2ps[cursor_pos].path)),
  Command("negative_item", "to unselect all items", [Command.States.dependent_command, Command.States.s2p_allpaths], [], lambda: remove_graph_item(s2ps[cursor_pos].path)),
  Command("negative_item", "to unselect item", [Command.States.dependent_command, Command.States.param_selected], [], lambda: remove_graph_item(s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1])),
  Command("negative_item", "to go back to path view", [Command.States.dependent_command], [Command.States.s2p_highlighted, Command.States.param_highlighted], lambda: return_to_s2p_tree()),
  Command("positive_item", "to view path details", [Command.States.s2ps_loaded, Command.States.dependent_command, Command.States.s2p_highlighted], [], lambda: view_path_details()),
  Command("positive_item", "to select an item", [Command.States.dependent_command, Command.States.param_unselected], [], lambda: add_graph_item(s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1])),
  Command("positive_item", "to go back to path view", [Command.States.dependent_command], [Command.States.s2p_highlighted, Command.States.param_highlighted], lambda: return_to_s2p_tree()),
  Command("add_all_s", "to select all 'S' items", [Command.States.s2ps_loaded, Command.States.dependent_command, Command.States.s2p_highlighted], [Command.States.s2p_allspaths], lambda: add_graph_item(param_filter="S")),
  Command("add_all_s", "to remove all 'S' items", [Command.States.s2ps_loaded, Command.States.dependent_command, Command.States.s2p_allspaths], [], lambda: remove_graph_item(param_filter="S")),
  Command("add_all_i", "to select all 'S' items", [Command.States.s2ps_loaded, Command.States.dependent_command, Command.States.s2p_highlighted], [Command.States.s2p_allipaths], lambda: add_graph_item(param_filter="I")),
  Command("add_all_i", "to remove all 'S' items", [Command.States.s2ps_loaded, Command.States.dependent_command, Command.States.s2p_allipaths], [], lambda: remove_graph_item(param_filter="I"))
]

# COMMAND FUNCTIONS
def load_file() -> None:
  # Loads a file into the list of s2ps
  # Ask user for file
  paths = fileopenbox(title="Open a .s2p File", default="\\*.s2p", multiple=True)
  # Check if we got a valid file
  if paths == None or len(paths) == 0:
    return
  for path in paths:
    # Load s2p data
    s2p = S2P()
    s2p.load_s2p(path)

    # Check if we already have an s2p with the same name
    if len([s for s in s2ps if s.path == s2p.path]) == 0:
      # Add to list
      s2ps.append(s2p)
      # Update display
      update_visuals()

def get_data(gi: tuple[str, str]) -> tuple[list[float], list[float]]:
  # Grab the s2p
  s2p = [x for x in s2ps if x.path == gi[0]][0]
  # return the data
  return s2p.get_sparam(gi[1])

def generate_graph(delta: bool) -> None:
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Create figure
  fig = plt.figure()
  # Figure out how many graphs we need
  num_of_axs = 1
  if settings["plot_options"]["split_by_data_type"] and len([x for x in graph_items if "I" in x[1]]) > 0: num_of_axs *= 2
  if delta: num_of_axs *= 2
  # Create the graph and reference thing
  axs = [fig.add_subplot(2 if num_of_axs > 1 else 1, 2 if num_of_axs > 2 else 1, i + 1) for i in range(num_of_axs)]
  los = []
  los.append("SG" if settings["plot_options"]["split_by_data_type"] and len([x for x in graph_items if "I" in x[1]]) > 0 else "SGIG")
  if num_of_axs > 1:
    los.append("IG" if settings["plot_options"]["split_by_data_type"] and len([x for x in graph_items if "I" in x[1]]) > 0 else "SDID")
  if num_of_axs > 2:
    los.append("SD")
    los.append("ID")
  # Graph all items
  for gi in graph_items:
    data = get_data(gi)
    # Check if this is an I or S value
    param_type = "S" if "S" in gi[1] else "I"
    # Loop through all axes and add
    for ax, lo in zip(axs, los):
      if param_type + "G" in lo:
        ax.scatter(data[0], data[1], label=gi[0] + " [" + gi[1] + "]", s=settings["plot_options"]["marker_size"])

  # Graph all deltas (if we are in that mode)
  if delta:
    for p in ["S", "I"]:
      # sort the graph items depending on what we are currently owrking on
      gis = [x for x in graph_items if p in x[1]]
      # loop through all combos
      for x in range(len(gis)):
        for y in range(x + 1, len(gis)):
          # Create iterators
          xbd = list(zip(*get_data(gis[x])))
          xit = peekable(xbd)
          ybd = list(zip(*get_data(gis[y])))
          yit = peekable(ybd)
          # Some data var
          data: tuple[list[float], list[float]] = ([], [])
          # Loop till we run out of items in both lists
          while not(xit.peek(None) == None and yit.peek(None) == None):
            if xit.peek([inf])[0] == yit.peek([inf])[0]:
              # x == y
              xd = next(xit)
              yd = next(yit)
              data[0].append(xd[0])
              # If I and Degree param unit and > 180 then we invert and display
              if p == "I" and [s for s in s2ps if s.path == gis[x][0]][0].parameter_units != "ri" and yd[1] - xd[1] > 180:
                data[1].append(yd[1] - xd[1] - 360)
              else:
                data[1].append(yd[1] - xd[1])
            elif xit.peek([inf])[0] < yit.peek([inf])[0]:
              # x < y
              next(xit)
            else:
              # y < x
              next(yit)

          # Add to the proper plot
          for ax, lo in zip(axs, los):
            if p + "D" in lo:
              ax.scatter(data[0], data[1], label="Δ " + graph_items[x][0] + " [" + graph_items[x][1] + "], " + graph_items[y][0] + " [" + graph_items[y][1] + "]", s=settings["plot_options"]["marker_size"])

  # Add stuff to ax
  for ax, lo in zip(axs, los):
    ax.set_title(lo)
    ax.set_xlabel(PLOT_XLABEL.replace("#", FREQ_NAMES[settings["plot_options"]["freq_units"]]))
    ax.set_ylabel(PARAMETER_LABELS[s2ps[0].parameter_units])
    ax.legend()

  # Show plot
  plt.show()

def cursor_up() -> None:
  global cursor_pos
  # Move Cursor Up
  cursor_pos = max(cursor_pos - 1, 0)
  # redraw
  update_visuals()

def cursor_down() -> None:
  global cursor_pos, view_path
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Move Cursor Down
  if view_path == -1:
    cursor_pos = min(cursor_pos + 1, len(s2ps) - 1)
  else:
    cursor_pos = min(cursor_pos + 1, len(S2P.S_PARAMS))
  # redraw
  update_visuals()

def add_graph_item(path_filter: str = "", param_filter: str = ""):
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Loop through all the s2ps that match the path filter
  for s2p in [x for x in s2ps if path_filter in x.path]:
    # Loop through all the sparams that match the param filter
    for param in [x for x in S2P.S_PARAMS if param_filter in x]:
      # prevent duplicates
      if (s2p.path, param) in graph_items:
        continue
      # Add to graph items
      graph_items.append((s2p.path, param))
  # redraw
  update_visuals()

def remove_graph_item(path_filter: str = "", param_filter: str = "") -> None:
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Loop through all the s2ps that match the path filter
  for s2p in [x for x in s2ps if path_filter in x.path]:
    # Loop through all the sparams that match the param filter
    for param in [x for x in S2P.S_PARAMS if param_filter in x]:
      # Remove from graph items
      graph_items.remove((s2p.path, param))
  # redraw
  update_visuals()

def view_path_details() -> None:
  # Shows the param view of the path
  global cursor_pos, view_path
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  view_path = cursor_pos
  cursor_pos = 0
  # redraw
  update_visuals()

def return_to_s2p_tree() -> None:
  # Go back from a detailed view to the s2p tree view
  global cursor_pos, view_path
  cursor_pos = view_path
  view_path = -1
  # redraw
  update_visuals()

def update_visuals() -> None:
  global cursor_pos
  if view_path == -1:
    # Update the s2p tree
    tree = Tree("Loaded S2P Files")
    # Add all the elements to the tree
    for i in range(len(s2ps)):
      # Do text
      t = ""
      for s in range(len(S2P.S_PARAMS)):
        if len([x for x in graph_items if x == (s2ps[i].path, S2P.S_PARAMS[s])]) > 0:
          t += "☒ "
        else:
          t += "☐ "
      t += " | " + s2ps[i].path
      # Set style
      style = SELECTED_STYLE if i == cursor_pos else "white"
      # Add to table
      tree.add(t, style= style)
  else:
    # Update the s2p tree
    tree = Tree(s2ps[view_path].path)
    style = SELECTED_STYLE if 0 == cursor_pos else "white"
    tree.add("← Go Back", style= style)
    # add all s2ps
    for i in range(len(S2P.S_PARAMS)):
      # Do text
      t = ""
      if len([x for x in graph_items if x == (s2ps[view_path].path, S2P.S_PARAMS[i])]) > 0:
        t += "☒ "
      else:
        t += "☐ "
      t += S2P.S_PARAMS[i]
      # Set style
      style = SELECTED_STYLE if i == cursor_pos - 1 else "white"
      # Add to table
      tree.add(t, style= style)

  #Update the subtitle line depending on what is selected
  valid_commands = [str(x) for x in commands if x.is_command_valid(Command.States.dependent_command)]
  subtitle = ", ".join([str(x) for x in commands if x.is_command_valid(Command.States.dependent_command)])
  # Update the UI
  layout["s2p_tree"].update(Panel(tree, title="Loaded S2P Files", subtitle=subtitle))

def get_keybind_from_char(char: str) -> str:
  return [x for x in settings["keybinds"].keys() if settings["keybinds"][x] == char][0]

def parse_input(char: str) -> None:
  
  # ANSI Escape Codes
  if char == chr(0):
    char = ESCAPE_CODE_CONVERSIONS[chr(ord(getch()))]
  # Filter the valid commands
  valid_commands = [x for x in commands if x.is_command_executable(get_keybind_from_char(char))]
  # Loop through commands
  for command in valid_commands:
    # Execute
    command.get_funciton()()
  
# Main Code

# Load options
settings = {}
with open("settings.yaml", "r", encoding="utf8") as stream:
  try:
    # Parse file into object
    settings = safe_load(stream)
  except YAMLError as exc:
    # Error TODO some sort of better error handling
    print(exc)
    quit()

# Dynamically generate the help line
HELP_LINE = ", ".join([str(x) for x in commands if x.is_command_valid(Command.States.general_command)])

# Create Console + layout
console = Console()
layout = Layout()

# Create the header / S2P Area
layout.split_column(Layout(Panel(Align("S2P Viewer " + settings["version"], align="center"), ), name="header", size=3), Layout(Panel("", title="Loaded S2P Files"), name="s2p_tree"), Layout(Align(HELP_LINE, align="center"), name="help_line", size=1))

# Draw Everything
update_visuals()

# Main Loop
with Live(layout, auto_refresh=False) as live:
  while not exit:
    # Wait for Input
    parse_input(chr(ord(getch())))
    live.refresh()