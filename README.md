MeasureTrackPlugin.py
When started reads NetClasses and will test length of a certain Netclass. So make sure that all signal you want length matched are assigned to the same class.
Reads csv file in Kicad project directory called ViaDelays.csv in the format
	    F.Cu	In2.Cu	    In5.Cu	    B.Cu
F.Cu	6	    8	        12	        16
In2.Cu	8	    6	        12	        12
In5.Cu	12	    12	        6	        8
B.Cu	16	    12	        8	        6

Here you define the delay in picoSeconds of each layer transistion. 
Script also takes into account pin package lengths. And converts them to picoSeconds to calculate delay





bga_to_excel.py
Takes whatever part you have highlighted in the PCB and converts it's BGA ball grid to a spreadsheet in the current rotation.
Helpful for planning DDR layouts and Power plane layouts.
