from msvcrt import getch
from os import path
from easygui import fileopenbox
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.style import Style
from rich.tree import Tree

VERSION = "V0.1 [25 July 2022]"
HELP_LINE = "L to load S2P, G to view graph, ←→ to interact with items in the tree, ↑↓ to move on tree"
SELECTED_STYLE = Style(color="light_sky_blue1", bold=True )
MARKER_SIZE = 2


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
    i += 1
    # read the s params
    while i < len(lines):
      values = lines[i].split()
      # Convert to MHz form kHz
      self.freq.append(float(values[0]) / 1000000)
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
    # Display graph of all selected sparams
    fig = plt.figure()
    ax: Axes = fig.add_subplot(111)
    for s2p in s2ps:
      # loop through all related graph items
      for s in [x for x in graph_items if x[0] == s2p.path]:
        # Grab data and add to plot
        data = s2p.get_sparam(s[1])
        ax.scatter(data[0], data[1], label=s2p.path + " [" + s[1] + "]", s=MARKER_SIZE)
    # Show legend / labels
    plt.xlabel("Frequency (MHz)")
    plt.ylabel("Response (dB)")
    ax.legend()
    # Show
    plt.show()

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
with Live(layout):
  while not exit:
    # Wait for Input
    parse_input(chr(ord(getch())))