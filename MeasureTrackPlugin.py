import pcbnew
import os
import wx
import wx.html2
import wx.grid as gridlib
from pcbnew import *
import csv
import math

#tracks = dict()

log_file_path = 'C:/Users/samwi/Documents/Kicad_Projects/script_testing/logfile.txt'

class TrackTable(gridlib.Grid):
    def __init__(self, parent, tracks):
        gridlib.Grid.__init__(self, parent)

        # Create the grid with the number of rows based on the tracks count
        self.CreateGrid(len(tracks), 5)

        # Set column labels
        self.SetColLabelValue(0, "Net Name")
        self.SetColLabelValue(1, "Total Delay")
        self.SetColLabelValue(2, "Total Length")
        self.SetColLabelValue(3, "Length per Layer")
        self.SetColLabelValue(4, "Die Length")  # New column

        # Fill the grid with data
        for i, track in enumerate(sorted(tracks, key=lambda x: x.get_total_delay(), reverse=True)):
            self.SetCellValue(i, 0, track.netname)
            self.SetCellValue(i, 1, str(track.get_total_delay()))  # Convert total delay to string for display
            self.SetCellValue(i, 2, str(track.get_total_length()))  # Convert total length to string for display
            self.SetCellValue(i, 3, str(track.length_per_layer))  # Convert dict to string for display
            self.SetCellValue(i, 4, str(track.die_length))  # Display the die_length

        self.AutoSizeColumns()

class TableFrame(wx.Frame):
    def __init__(self, tracks):
        wx.Frame.__init__(self, None, -1, "Track Details", size=(600, 400))

        # Add TrackTable to the frame
        self.grid = TrackTable(self, tracks)

        # Layout management
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.grid, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

        self.Center()



class Track:
    def __init__(self, netname, netclass):
        self.netname = netname
        self.netclass = netclass
        self.length_per_layer = dict()
        self.segments = []
        self.vias = []
        self.trace_delay = 0
        self.die_length = 0

    def add_length(self, layer, length):
        if layer not in self.length_per_layer:
            self.length_per_layer[layer] = 0
        self.length_per_layer[layer] += round(length,4)
        self.length_per_layer[layer] = round(self.length_per_layer[layer],4)
    def add_segment(self, segment):
        self.segments.append(segment)

    def add_via(self, via):
        self.vias.append(via)

    def get_total_length(self):
        # Compute the total length of all tracks on all layers.
        return round(sum(self.length_per_layer.values()) + self.die_length,4)
    
    
    def calculate_total_delay(self, delay_matrix):
    # Compute the total length of all tracks on all layers.
        for layer, length in self.length_per_layer.items():
            if layer == "F.Cu" or layer == "B.Cu":
                self.trace_delay += round(length * 6.08,4)
            else:
                self.trace_delay += round(length * 7.17,4)
        
        # Compute delay for each via
        via_connections = self.analyze_vias()
        for via, connections in via_connections.items():
            if len(connections) < 2:
                log_debug_info(f"Warning: Less than 2 connections for via {via}")
                continue
            
            from_layer = connections[0]['layer']
            to_layer = connections[1]['layer']
            self.trace_delay += delay_matrix[from_layer][to_layer]

        self.trace_delay += round(self.die_length * 6.08,4)
        
        return self.trace_delay
    
    def get_total_delay(self):
        return self.trace_delay 
    
    def analyze_vias(self):
        """
        For each via in the track, find the segments that touch this via and identify their respective layers.
        """
        via_connections = {}
        acceptable_distance = 100000  # 0.1mm in KiCad units

        for via in self.vias:
            via_start = via.GetStart()
            via_end = via.GetEnd()
            connected_segments = []
            log_debug_info(f"via start {via_start}")

            for segment in self.segments:
                segment_start = segment.GetStart()
                segment_end = segment.GetEnd()

                # Check if the segment touches the via
                if (distance_between_points(via_start, segment_start) <= acceptable_distance or
                    distance_between_points(via_start, segment_end) <= acceptable_distance or
                    distance_between_points(via_end, segment_start) <= acceptable_distance or
                    distance_between_points(via_end, segment_end) <= acceptable_distance):
                    connected_segments.append({
                        'segment': segment,
                        'layer': segment.GetLayerName(),
                    })

                # Check if the segment touches the via
                if via_start == segment_start or via_start == segment_end or via_end == segment_start or via_end == segment_end:
                    connected_segments.append({
                        'segment': segment,
                        'layer': segment.GetLayerName(),
                    })

            via_connections[via] = connected_segments

        return via_connections
    
def distance_between_points(point1, point2):
    """
    Calculate the distance between two wxPoints.
    """
    dx = point1.x - point2.x
    dy = point1.y - point2.y
    return math.sqrt(dx**2 + dy**2)


def log_debug_info(debug_info):
    """Write debug information to a log file."""
    with open(log_file_path, 'a') as f:
        f.write(f"Debug info: {debug_info}\n")

class MeasureTrackPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Measure all nets"
        self.category = "Measurement"
        self.description = "Measure the length of all nets in the printed circuit board and the selected track"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'track_length.png')

        #tracks.clear()
        self.tracks = {}

    def Run(self):
        # Clear the log file at the start of the run.
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
        self.tracks.clear()
        board = GetBoard()
        project_path = board.GetFileName()
        log_debug_info(f"project path: {project_path}")
        net_classes = [str(net_class) for net_class in board.GetNetClasses()]
        log_debug_info(f" " + str(net_classes))
        log_debug_info(f" " + str(board.GetDesignSettings().GetStackupDescriptor()))
        log_debug_info(f" what")
        numSelectedSegments = 0
        selectedLength = 0
        lengthPerNet = dict()
        numSegmentsPerNet = dict()
        totalLength = 0

       # Get the current project path
        board_file_path = board.GetFileName()
        project_path = os.path.dirname(board_file_path)

        # Load the CSV file
        csv_file_path = os.path.join(project_path, 'Via Delays.csv')
        with open(csv_file_path, 'r') as f:
            reader = csv.reader(f)
            layers = [layer for layer in next(reader) if layer]  # Get the first row which contains layer names, excluding any empty strings
            delay_matrix = {layer: {} for layer in layers}
            for row in reader:
                from_layer = row[0]
                for to_layer, delay in zip(layers, row[1:]):
                    delay_matrix[from_layer][to_layer] = int(delay)

        # Get names of all layers in the board
        layer_names = [board.GetLayerName(i) for i in range(board.GetCopperLayerCount())]

        # Get IDs of all layers in the board
        layer_ids = {name: board.GetLayerID(name) for name in layer_names}

        #print(layer_ids)
        log_debug_info(f"layer ids: {delay_matrix}")
        
        design_settings = board.GetDesignSettings()
        stackup = design_settings.GetStackupDescriptor()
        #board_thickness = stackup.GetLayerDistance(0,3)
        log_debug_info(f"Stackup: {stackup}")
        #log_debug_info(f"board thickness: {board_thickness}")

        # Create a dialog box with a drop-down menu of net classes.
        dialog = wx.SingleChoiceDialog(None, "Please select a net class:", "Input needed", net_classes)
        if dialog.ShowModal() == wx.ID_OK:
            specific_netclass = dialog.GetStringSelection()
        else:
            return  # User cancelled the dialog.
        dialog.Destroy()
        die_lengths = {}
        pads = board.FindFootprintByReference("U1").Pads()

        for pad in pads:
            name = pad.GetNetname()
            log_debug_info(f"pad net name {name}" )
            length = pcbnew.ToMM(pad.GetPadToDieLength())
            die_lengths[name] = length

        # Create a Track instance for each unique net name and net class pair.
        for pcb_track in board.GetTracks():
            netname = pcb_track.GetNetname()
            netclass = pcb_track.GetNetClassName()
            #log_debug_info(f"Net name: {netname}, Net class: {netclass}")
            # Only process tracks that match the selected net class.
            if netclass != specific_netclass:
                #log_debug_info(f"Different net class")
                
                continue
            #log_debug_info(f"stll running Different net class")
            # If a Track instance for this net name and net class doesn't exist yet, create one.
            if (netname, netclass) not in self.tracks:
                log_debug_info(f"Adding Track")
                log_debug_info(f"Net name: {netname}, Net class: {netclass}")
                self.tracks[netname, netclass] = Track(netname, netclass)

            if netname in die_lengths and self.tracks[netname, netclass].die_length == 0 :
                    # Now you might want to do something with total_length_with_die
                    # For instance, you might want to store it as an attribute of the track:
                    self.tracks[netname, netclass].die_length = die_lengths[netname]
                    log_debug_info(f"Die length: {self.tracks[netname, netclass].die_length}")

            if pcb_track.Type() == pcbnew.PCB_VIA_T:
                self.tracks[netname, netclass].add_via(pcb_track)

            else:
                layer = pcb_track.GetLayerName()
                #layerID = pcb_track.GetLayerID()
                #layer_name = pcb_track.GetLayerName() 
                #log_debug_info(f"Layer name: {layer_name}")
                length = round(pcb_track.GetLength() / 1000000,4)  # convert from nm to mm

                # Add the length and segment of this pcb_track to the Track instance.
                self.tracks[netname, netclass].add_length(layer, length)
                self.tracks[netname, netclass].add_segment(pcb_track)
        report = ''
        for (netname, netclass), track in self.tracks.items():
                # ... existing code ...
                via_connections = track.analyze_vias()
                for via, connections in via_connections.items():
                    log_debug_info(f"  Via: {via}")
                    for connection in connections:
                        log_debug_info(f"    Connected segment {netname}: {connection['segment']}, Layer: {connection['layer']}")
        #for (netname, netclass), track in self.tracks.items():
            #log_debug_info(f"Net name: {netname}, Net class: {netclass}")
            #for layer, length in track.length_per_layer.items():
                #log_debug_info(f"  Layer: {layer}, Length: {length} mm")
            #for via in track.vias:
                #log_debug_info(f"  Via: {via} " + str(via.GetDrillValue()))
                #log_debug_info(f" Layer Pair " + str(via.LayerPair()))
       # To use the above classes in your script, create an instance of TableFrame with your track list as argument:
       # tracks = [Track1, Track2, Track3]  # Replace with your actual list of Track objects

        for (netname, netclass), track in self.tracks.items():
            track.calculate_total_delay(delay_matrix)
        frame = TableFrame([track for track in self.tracks.values()])
        #frame = TableFrame(self.tracks)
        frame.Show(True)




        #wx.MessageBox(report, 'Measure of length of tracks', wx.OK | wx.ICON_INFORMATION)
        
MeasureTrackPlugin().register()
