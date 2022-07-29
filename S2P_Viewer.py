from math import inf
from msvcrt import getch
from os import path
from easygui import fileopenbox
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
from more_itertools import peekable
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
      self.freq.append(float(values[0]) * FREQ_UNITS[init_freq_units] / FREQ_UNITS[settings["plot-options"]["freq-units"]])
      for s in range(len(self.S_PARAMS)):
        self.s_params[s].append(float(values[s + 1]))
      i += 1
  
  def get_sparam (self, param: str):
    return (self.freq, self.s_params[self.S_PARAMS.index(param)])

# Loaded Data
s2ps: list[S2P] = []

graph_items = []
exit = False
# GUI nav vars
cursor_pos = 0
view_path = -1


# COMMANDS
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

def generate_graph(delta: bool) -> None:
  # Display graph of all selected sparams
    fig = plt.figure()
    if delta or (settings["plot-options"]["split-by-data-type"] and len([x for x in graph_items if "I" in x[1]]) > 0):
      ax: Axes = fig.add_subplot(211)
      de: Axes = fig.add_subplot(212)
    else:
      ax: Axes = fig.add_subplot(111)
    # Graph all items
    for gi in graph_items:
      data = get_data(gi)
      if "I" in gi[1] and settings["plot-options"]["split-by-data-type"]:
        de.scatter(data[0], data[1], label=gi[0] + " [" + gi[1] + "]", s=settings["plot-options"]["marker-size"])
      else:
        ax.scatter(data[0], data[1], label=gi[0] + " [" + gi[1] + "]", s=settings["plot-options"]["marker-size"])
    
    # Graph all deltas (if we are in that mode)
    if delta:

      for x in range(len(graph_items)):
        for y in range(x + 1, len(graph_items)):
          # Create iterators
          xbd = list(zip(*get_data(graph_items[x])))
          xit = peekable(xbd)
          ybd = list(zip(*get_data(graph_items[y])))
          yit = peekable(ybd)
          # Some vars
          data = ([], [])
          # While loop
          while not(xit.peek(None) == None and yit.peek(None) == None):
            # If both are equal then add their delta
            if xit.peek([None])[0] == yit.peek([None])[0]:
              xd = next(xit)
              yd = next(yit)
              data[0].append(xd[0])
              data[1].append(xd[1] - yd[1])\
            # Otherwise get rid of the lower one
            else:
              if xit.peek([inf])[0] < yit.peek([inf])[0]:
                next(xit)
              else:
                next(yit)
          de.scatter(data[0], data[1], label="Δ " + graph_items[x][0] + " [" + graph_items[x][1] + "], " + graph_items[y][0] + " [" + graph_items[y][1] + "]", s=settings["plot-options"]["marker-size"])
    # Add stuff to ax
    ax.set_xlabel(PLOT_XLABEL.replace("#", FREQ_NAMES[settings["plot-options"]["freq-units"]]))
    ax.set_ylabel(PARAMETER_LABELS[s2ps[0].parameter_units])
    ax.legend()

    # Add delta stuff if it is enabled
    if delta or (settings["plot-options"]["split-by-data-type"] and len([x for x in graph_items if "I" in x[1]]) > 0):
      de.set_xlabel(PLOT_XLABEL.replace("#", FREQ_NAMES[settings["plot-options"]["freq-units"]]))
      de.set_ylabel(PARAMETER_LABELS[s2ps[0].parameter_units])
      de.legend()

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
  if len(s2ps) == 0:
    return
  # Move Cursor Down
  if view_path == -1:
    cursor_pos = min(cursor_pos + 1, len(s2ps) - 1)
  else:
    cursor_pos = min(cursor_pos + 1, len(S2P.S_PARAMS))
  # redraw
  update_visuals()

def add_graph_item() -> None:
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Add a specific item to the list with the path and sparam provided
  graph_items.append((s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1]))
  # redraw
  update_visuals()

def add_all_path_items(path: str) -> None:
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Add all items to the graph for the path provided
  for i in range(len(S2P.S_PARAMS)):
    if not (path, S2P.S_PARAMS[i]) in graph_items:
      graph_items.append((path, S2P.S_PARAMS[i]))
  # redraw
  update_visuals()

def remove_graph_item() -> None:
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Remove a specific item matching the path and sparam provided
  graph_items.remove((s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1]))
  # redraw
  update_visuals()

def remove_all_path_items(path) -> None:
  global graph_items, view_path
  # Check that we actually have s2ps loaded
  if len(s2ps) == 0:
    return
  # Remove all items that match with the path provided
  graph_items = [x for x in graph_items if not x[0] == path]
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

COMMANDS = [
  ["load-keybind", "to load a file", ["common"], load_file],
  ["graph-keybind", "to view a graph", ["common"], lambda: generate_graph(False)],
  ["delta-keybind", "to view a graph with deltas", ["common"], lambda: generate_graph(True)],
  ["cursorup-keybind", "to move cursor up", ["list"], cursor_up],
  ["cursorup-keybind", "to move cursor up", ["list", "top_slot"], cursor_up],
  ["cursordown-keybind", "to move cursor down", ["list"], cursor_down],
  ["cursordown-keybind", "to move cursor down", ["list", "top_slot"], cursor_down],
  ["negative-item", "to add all items to graph", ["list", "s2p_tree", "unselected"], lambda: add_all_path_items(s2ps[cursor_pos].path)],
  ["negative-item", "to remove all items from graph", ["list", "s2p_tree", "selected"], lambda: remove_all_path_items(s2ps[cursor_pos].path)],
  ["negative-item", "to remove item from the graph", ["list", "param_tree", "selected"], remove_graph_item],
  ["negative-item", "to go back to tree view", ["list", "param_tree", "top_slot"], return_to_s2p_tree],
  ["positive-item", "to view path details", ["list", "s2p_tree"], view_path_details],
  ["positive-item", "to add item to the graph", ["list", "param_tree", "unselected"], add_graph_item],
  ["positive-item", "to go back to tree view", ["list", "param_tree", "top_slot"], return_to_s2p_tree]
  
]

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
  subtitle = ", ".join([settings["keybinds"][x[0]].upper() + " " + x[1] for x in get_valid_commands() if not "common" in x[2]])
  # Update the UI
  layout["s2p_tree"].update(Panel(tree, title="Loaded S2P Files", subtitle=subtitle))

def get_data(gi) -> tuple[list[float], list[float]]:
  # Grab the s2p
  s2p = [x for x in s2ps if x.path == gi[0]][0]
  # return the data
  return s2p.get_sparam(gi[1])

def get_valid_commands() -> list:
  global cursor_pos, graph_items
  # Get states
  states = ["common", "list"]
  # If we are on the top slot, mention that
  if cursor_pos == 0:
    states.append("top_slot")
  # Check if we are looking at the s2p tree or a tree of sparams
  if view_path == -1:
    states.append("s2p_tree")
    # Check the status of our selected item
    gis = len([x for x in graph_items if x[0] == s2ps[cursor_pos].path])
    if gis == 0: states.append("unselected")
    elif gis == len(S2P.S_PARAMS): states.append("selected")
    else: states.append("partialselected")
  else:
    states.append("param_tree")
    # Check the status of our selected item
    if (s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1]) in graph_items:
      states.append("selected")
    else:
      states.append("unselected")
  commands = COMMANDS
  # If not in top slot and not in param tree then strictly sort only commands with top slot
  if view_path == -1 or cursor_pos != 0:
    commands = [x for x in COMMANDS if not "top_slot" in x[2]]
  else:
    commands = [x for x in COMMANDS if "top_slot" in x[2] or "common" in x[2]]
  # Filter by states
  return [x for x in commands if all(item in states for item in x[2])]

def parse_input(char: str) -> None:
  
  # ANSI Escape Codes
  if char == chr(0):
    char = ESCAPE_CODE_CONVERSIONS[chr(ord(getch()))]
  # Filter by state
  valid_commands = get_valid_commands()
  # Filter by keybind
  valid_commands = [x for x in valid_commands if char.lower() == settings["keybinds"][x[0]]]
  # Loop through commands
  for command in valid_commands:
    # Execute
    command[3]()
  
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
HELP_LINE = ", ".join([settings["keybinds"][x[0]].upper() + " " + x[1] for x in COMMANDS if "common" in x[2]])

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