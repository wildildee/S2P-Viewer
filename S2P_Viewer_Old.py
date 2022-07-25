import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from os import path
from tkinter import BOTH, Button, E, Frame, LEFT, Label, LabelFrame, N, OptionMenu, RIGHT, S, StringVar, TRUE, W, X, Y, filedialog
from tkinter import Tk

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
      self.freq.append(float(values[0]))
      for s in range(len(self.S_PARAMS)):
        self.s_params[s].append(float(values[s + 1]))
      i += 1
  
  def get_sparam (self, param: str):
    return (self.freq, self.s_params[self.S_PARAMS.index(param)])

class Table:
    # Controls a Tkinter table object with the options to add or remove rows
    def __init__(self, cols):
        self.cols = cols
        self.rows = {}
        self.currow = 0
        
    def add_row (self, name, cols):
        # add to names
        self.rows[name] = []
        # Create row of cols
        for col in range(len(cols)):
            self.rows[name].append(cols[col])
            if cols[col] == None: continue
            # Calculate colspan
            colspan = 1
            if col < len(cols) - 1:
                for peek in range(col+1, len(cols)):
                    if cols[peek] == None:
                        colspan += 1
                    else:
                        break
            # Calculate padx
            padx = (1, 1)
            if col == 0:
                padx = (10, 1)
            if col + colspan == self.cols:
                padx = (1, 10)
            cols[col].grid(row=self.currow, column=col, padx = padx, pady=1, columnspan=colspan, sticky=N+E+S+W)
            
        # Increment currow
        self.currow += 1
        
    def remove_rows (self, search):
        # do all rows with a name that contains our search word
        keys = list(self.rows.keys())
        for key in keys:
            if search not in key: continue
            # Remove all cols in row
            for col in self.rows[key]:
                if col == None: continue
                col.grid_forget()
            # remove row
            self.rows.pop(key)

class Graph:
  def __init__(self, parent):
    self.datas = [[], [], [], []]
    self.axes = [None]*4
    self.figure = Figure(figsize=(1, 1), dpi=100)
    self.figure.patch.set_alpha(0.0)
    self.canvas = FigureCanvasTkAgg(self.figure, parent)
    self.canvas.get_tk_widget().configure(bg="cornsilk4")
    self.canvas.get_tk_widget().pack(fill=BOTH, expand=TRUE, padx=10, pady=(5,10))

  def drawdata(self, data, graph_num):
    # add to graph
    self.datas[graph_num].append(data)
    # adjust graph layout if nessesary
    if len(self.datas[graph_num]) == 1:
      self.adjust_graph_layout()
    # add to axis
    self.axes[graph_num].scatter(data[0], data[1])
    # redraw
    self.canvas.draw()

  def adjust_graph_layout(self):
    enabled_graphs = sum([1 if len(x) > 0 else 0 for x in self.datas])
    
    for axis in self.axes:
      if axis == None:
        continue
      axis.clear()
      self.axes.remove(axis)
    
    nrows = 2 if enabled_graphs > 1 else 1
    ncols = 2 if enabled_graphs > 2 else 1
    for x in range(len(self.axes)):
      if len(self.datas[x]) == 0:
        return
      axes = self.figure.add_subplot(nrows, ncols, x + 1)
      axes.set_title("Graph " + str(x + 1))
      self.axes[x] = axes
      



class Controller:
  GRAPHS = {"": -1, "Graph 1": 0, "Graph 2": 1, "Graph 3": 2, "Graph 4": 3}

  def __init__(self):
    self.S2Ps = []
    self.vars = []

  def _line_UI_change(self, path, sp, graph_str):
    # get s2p
    s2p = [s for s in self.S2Ps if s.path == path][0]
    # get data
    data = s2p.get_sparam(sp)
    # draw data
    graph.drawdata(data, self.GRAPHS[graph_str])

  def _remove_s2p (self, path):
    # Remove from all graphs
    for sp in self.SPARAM:
        self._line_UI_change(path, sp, "")
    # Remove all rows on table with path
    view_table.remove_rows(path)

  def load_s2p(self):
    # Grab file path
    path = filedialog.askopenfilename(filetypes=[("s2p files", "*.s2p")])
    # Load s2p
    s2p = S2P()
    s2p.load_s2p(path)
    # TODO: Check that the s2p isnt a duplicate path
    # Save to list
    self.S2Ps.append(s2p)
    self.vars.append([])
    # Add to table
    view_table.add_row(s2p.path, [Button(files, text="X", bg="firebrick3", command=lambda: self._remove_s2p(s2p.path)), Label(files, text=s2p.path), None])
    for sp in [s for s in S2P.S_PARAMS if "S" in s]:
        self.vars[-1].append(StringVar(root))
        view_table.add_row(s2p.path + sp, [Label(files, text="↳", anchor="e"), Label(files, text=sp, anchor="e"), OptionMenu(files, self.vars[-1][-1], *self.GRAPHS, command=lambda e, sp=sp: self._line_UI_change(s2p.path, sp, e))])

# main code
# create controller
controller = Controller()

# Init matplotlib
mpl.use("TkAgg")

# create the root window
root = Tk()
root.title("S2P viewer")
root.geometry("1024x768")

# Create the files frame
files = LabelFrame(root, text="Files", bg="cornsilk3")
files.pack(side=LEFT, padx=10, pady=10, fill=Y)

# Create the load s2p button
load = Button(files, text="  Load s2p File  ", command=lambda: controller.load_s2p())
load.grid(row=0, columnspan=6, padx=10, pady=(2, 1), sticky=E+W)

# Create the view table
view_table = Table(3)
view_table.currow = 1

# Create header for the table
view_table.add_row("Header", [Label(files, text="Line"), None, Label(files, text="Graph")])

# Create the graphs frame
graph_frame = LabelFrame(root, text="Graphs", bg="cornsilk4")
graph_frame.pack(side=RIGHT, padx=(0, 10), pady=10, fill=BOTH, expand=TRUE)

# Create the graph canvas
graph = Graph(graph_frame)

# Enter the tkinter main loop
root.mainloop()


