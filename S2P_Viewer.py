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

VERSION = "V0.2.1 [28 July 2022]"
HELP_LINE = "L to load S2P, G to view graph, D to view graph with deltas, ←→ to interact with items in the tree, ↑↓ to move on tree"
SELECTED_STYLE = Style(color="light_sky_blue1", bold=True )
MARKER_SIZE = 2
SPLIT_GRAPHS = True
FREQ_UNITS = {"ghz": 1000000000, "mhz": 1000000, "khz": 1000, "hz": 1}
FREQ_NAMES = {"ghz": "GHz", "mhz": "MHz", "khz": "kHz", "hz": "Hz"}
PARAMETER_LABELS = {"db": "Magnitude (dB)", "ma": "Magnitude (Absolute)", "ri": "Real"}
IMAGINARY_LABELS = {"db": "Angle (°)", "ma": "Angle (°)", "ri": "Imaginary"}
PLOT_FREQ_UNITS = "mhz"
PLOT_XLABEL = "Frequency (#)"

# Loaded Data
s2ps = []

graph_items = []
exit = False
# GUI nav vars
cursor_pos = 0
view_path = -1

# class for loading and storing 2-port touchstone files
class S2P:
  S_PARAMS = ["S11", "I11", "S21", "I21", "S12", "I12", "S22", "I22"]

  def __init__ (self):
    self.path = ""
    self.freq_units = ""
    self.parameter_units = ""
    self.freq = []
    # initialize the s_param array
    self.s_params = [[] for i in range(len(self.S_PARAMS))]
  
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
      self.freq.append(float(values[0]) * FREQ_UNITS[init_freq_units] / FREQ_UNITS[PLOT_FREQ_UNITS])
      for s in range(len(self.S_PARAMS)):
        self.s_params[s].append(float(values[s + 1]))
      i += 1
  
  def get_sparam (self, param: str):
    return (self.freq, self.s_params[self.S_PARAMS.index(param)])

def update_visuals() -> None:
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

  # Update the UI
  layout["s2p_tree"].update(Panel(tree, title="Loaded S2P Files", subtitle="Press 'L' to load a file"))
  # update the live
  # live.update()

def get_data(gi):
  # Grab the s2p
  s2p = [x for x in s2ps if x.path == gi[0]][0]
  # return the data
  return s2p.get_sparam(gi[1])
  
def generate_graph(delta: bool):
  # Display graph of all selected sparams
    fig = plt.figure()
    if delta or (SPLIT_GRAPHS and len([x for x in graph_items if "I" in x[1]]) > 0):
      ax: Axes = fig.add_subplot(211)
      de: Axes = fig.add_subplot(212)
    else:
      ax: Axes = fig.add_subplot(111)
    # Graph all items
    for gi in graph_items:
      data = get_data(gi)
      if "I" in gi[1] and SPLIT_GRAPHS:
        de.scatter(data[0], data[1], label=gi[0] + " [" + gi[1] + "]", s=MARKER_SIZE)
      else:
        ax.scatter(data[0], data[1], label=gi[0] + " [" + gi[1] + "]", s=MARKER_SIZE)
    
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
            if xit.peek()[0] == yit.peek()[0]:
              xd = next(xit)
              yd = next(yit)
              data[0].append(xd[0])
              data[1].append(xd[1] - yd[1])\
            # Otherwise get rid of the lower one
            else:
              if xit.peek()[0] < yit.peek()[0]:
                next(xit)
              else:
                next(yit)
          de.scatter(data[0], data[1], label="Δ " + graph_items[x][0] + " [" + graph_items[x][1] + "], " + graph_items[y][0] + " [" + graph_items[y][1] + "]", s=MARKER_SIZE)


    # Add stuff to ax
    ax.set_xlabel(PLOT_XLABEL.replace("#", FREQ_NAMES[PLOT_FREQ_UNITS]))
    ax.set_ylabel(PARAMETER_LABELS[s2ps[0].parameter_units])
    ax.legend()

    # Add delta stuff if it is enabled
    if delta or (SPLIT_GRAPHS and len([x for x in graph_items if "I" in x[1]]) > 0):
      de.set_xlabel(PLOT_XLABEL.replace("#", FREQ_NAMES[PLOT_FREQ_UNITS]))
      de.set_ylabel(PARAMETER_LABELS[s2ps[0].parameter_units])
      de.legend()

    # Show plot
    plt.show()

def parse_input(char: str) -> None:
  global cursor_pos, view_path, graph_items
  # Parse our input
  if char == 'l' or char == 'L':
    # Load a s2p file (open dialog, read, add to the list)
    path = fileopenbox(title="Open a .s2p File", default="\\*.s2p")
    # Check if we got a valid file
    if path == None:
      return
    # Load s2p data
    s2p = S2P()
    s2p.load_s2p(path)

    # Check if we already have an s2p with the same name
    if len([s for s in s2ps if s.path == s2p]) == 0:
      # Add to list
      s2ps.append(s2p)
      # Update display
      update_visuals()

  elif char == 'g' or char == "G":
    # Generate a grpah without deltas
    generate_graph(False)

  elif char == 'd' or char == 'D':
    # Create a graph with deltas
    generate_graph(True)

  elif char == chr(0):
    
    # ANSI Escape Code
    # Grab 2nd Char to decode
    char2 = chr(ord(getch()))
    
    if char2 == 'H':
      # Move our selector up
      if view_path == -1:
        cursor_pos = max(cursor_pos - 1, 0)
      else:
        cursor_pos = max(cursor_pos - 1, 0)
      # redraw
      update_visuals()
    elif char2 == 'P':
      # Move our selector down
      if view_path == -1:
        cursor_pos = min(cursor_pos + 1, len(s2ps) - 1)
      else:
        cursor_pos = min(cursor_pos + 1, len(S2P.S_PARAMS))
      # redraw
      update_visuals()
    elif char2 == 'K':
      # Check if we are in general or on a specific path
      if view_path == -1:
        # Check if there are any items relating to the path
        if len([x for x in graph_items if x[0] == s2ps[view_path].path]) > 0:
          # Remove all graph items relating to the path
          graph_items = [x for x in graph_items if not x[0] == s2ps[view_path].path]
        else:
          # Add all non existant path items to graph items
          for i in range(len(S2P.S_PARAMS)):
            if not (s2ps[view_path].path, S2P.S_PARAMS[i]) in graph_items:
              graph_items.append((s2ps[view_path].path, S2P.S_PARAMS[i]))
      else:
        if not cursor_pos == 0:
          # Remove the specific graph items relating to the s2p
          graph_items.remove((s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1]))
      # redraw
      update_visuals()
    elif char2 == 'M':
      # Check if we are in general or on a specific path
      if view_path == -1 :
        # View the current path the cursor is over (if there are any pathes loaded)
        if len(s2ps) > 0:
          view_path = cursor_pos
          cursor_pos = 0
      else:
        if cursor_pos == 0:
          # Go Back
          cursor_pos = view_path
          view_path = -1
        else:
          # Add the current s2p to the thing
          graph_items.append((s2ps[view_path].path, S2P.S_PARAMS[cursor_pos - 1]))
      # redraw
      update_visuals()
  
# Main Code

# Create Console + layout
console = Console()
layout = Layout()

# Create the header / S2P Area
layout.split_column(Layout(Panel(Align("S2P Viewer " + VERSION, align="center"), ), name="header", size=3), Layout(Panel("", title="Loaded S2P Files"), name="s2p_tree"), Layout(Align(HELP_LINE, align="center"), name="help_line", size=1))

# Draw Everything
update_visuals()

# Main Loop
with Live(layout, auto_refresh=False) as live:
  while not exit:
    # Wait for Input
    parse_input(chr(ord(getch())))
    live.refresh()