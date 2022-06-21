############## Program Variables ##############
Continue = 'Continue'
Error = 'Error'
Channel = 'Channel'
SetPoint = 'SetPoint'
SetPoint1 = 'SetPoint1'
SetPoint2 = 'SetPoint2'
Kp = 'Kp'
Ki = 'Ki'
Kd = 'Kd'
Gain = 'Gain'
Offset = 'Offset'
HighVoltage = 'HighVoltage'
LowVoltage = 'LowVoltage'
DAC = 'DAC'
Voltage = 'Voltage'
WavelengthReading = 'WavelengthReading'
plotevent1, plotvalues1 = 'PlaceHolder', 'PlaceHolder'
plotevent2, plotvalues2 = 'PlaceHolder', 'PlaceHolder'
plotevent3, plotvalues3 = 'PlaceHolder', 'PlaceHolder'
plotevent4, plotvalues4 = 'PlaceHolder', 'PlaceHolder'
Show = 'Show'
Canvas = 'Canvas'

isShowing = 'isShowing'
Figure = 'Figure'
FigAgg = 'FigAgg'
WindowName = 'WindowName'
PlotEvent = 'PlotEvent'
PlotValues = 'PlotValues'
Pause = 'Pause'
axes = 'axes'
GHz = 'GHz'
c = 299792548

############## Laser Data ##############
Laser1 = {Continue:False, Error:[], WavelengthReading:[0.0], Voltage:0.0, SetPoint:369.52435}
Laser2 = {Continue:False, Error:[], WavelengthReading:[0.0], Voltage:0.0, SetPoint:398.911348}
Laser3 = {Continue:False, Error:[], WavelengthReading:[0.0], Voltage:0.0, SetPoint:760.0716}
Laser4 = {Continue:False, Error:[], WavelengthReading:[0.0], Voltage:0.0, SetPoint:935.18736}
Lasers = [Laser1, Laser2, Laser3, Laser4]

############## More stuff ##############
board_num = 0 # InstaCal board number
t = 1/50 #if the program is reading the incorrect wavelength after switching ports increase t.
stop_threads = False
run_loop = True #Used to pause the background thread

srfile = open("SampleRateDefault.txt")
SampleRate = float(srfile.read())

############## Pull Defaults From File  ##############
Laser1Default = {}
Laser2Default = {}
Laser3Default = {}
Laser4Default = {}
Defaults = [Laser1Default, Laser2Default, Laser3Default, Laser4Default]

for LaserDefault in Defaults:
    index = Defaults.index(LaserDefault)
    with open("Laser"+str(Defaults.index(LaserDefault)+1)+"Defaults.txt") as f:
        for line in f:
            (key, val) = line.split()
            try:
                LaserDefault[key] = float(val)
            except ValueError:
                LaserDefault[key] = val
    Lasers[index].update(LaserDefault)

############## Import Modules ##############
import threading
from pyBristolSCPI import *
from labjack import ljm
import time
from mcculw import ul
from mcculw.enums import DigitalIODirection
from digital import DigitalProps
import PySimpleGUI as sg
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime

############# PID FUNCTIONS ##############
def closestWL(wl):
    '''
    Takes a Wavelength polls the defaults and returns the index of the Laser in Lasers it should be assigned.
    Input: Float
    
    Output Int
    '''
    differences = []
    for LaserDefault in Defaults:
        differences.append(abs(wl-LaserDefault[SetPoint1]))
    index = differences.index(min(differences))
    return index
    
def proportional(Laser):
    '''
    Proportional Correction
    '''
    Proportional = Laser[Error][-1] * Laser[Kp]
    return Proportional

def integral(Laser, SampleRate):
    '''
    Integral Correction
    '''
    IntList = []
    if len(Laser[Error]) > 1:
        for i in range(0,len(Laser[Error])):
            IntList.append(Laser[Error][i]/SampleRate)
        Integral = Laser[Ki] * sum(IntList)
        return Integral
    else:
        return 0

def derivative(Laser, SampleRate):
    '''
    Derivative Correction
    '''
    if len(Laser[Error]) > 1:
        dE = Laser[Error][-1] - Laser[Error][-2]
        Derivative = Laser[Kd] * dE/SampleRate
        return Derivative
    else:
        return 0

def PID(Laser):
    '''
    PID algorithm
    returns: Correction
    '''
    P = proportional(Laser)
    I = integral(Laser, SampleRate)
    D = derivative(Laser, SampleRate)
    PID = sum([P,I,D]) * (-Laser[Gain])
    return PID

############## PROGRAM FUNCTIONS ##############
def ChangePort(NewPort):
    '''
    Changes port of switch
    '''
    port_value = NewPort
    ul.d_out(board_num, port.type, port_value)

def connectDevices():
    '''
    Attempts to connect switch, wavemeter, and DAC
    '''
    success = []
    try:
        global scpi
        scpi = pyBristolSCPI()
    except Exception as e:
        print('Cannot connect to wavemeter: {}'.format(e))
        success.append(0)
    else:
        print('Wavemeter connected')
        success.append(1)
    try:
        global handle
        handle = ljm.openS("T4", "ANY", "ANY")  # T4 device, Any connection, Any identifier
    except Exception as e:
        print('Cannot connect to DAC')
        scpi.closetn()
        success.append(0)
    else:
        print('DAC connected')
        success.append(1)
    try:
        global digital_props
        digital_props = DigitalProps(board_num)
        global port
        port = next(
            (port for port in digital_props.port_info
             if port.supports_output), None)
        ul.d_config_port(board_num, port.type, DigitalIODirection.OUT)
    except Exception as e:
        print('Cannot connect to switch')
        scpi.closetn()
        success.append(0)
    else:
        print('Switch connected')
        success.append(1)
    return success
    
def GetChannels():
    '''
    Scans through the different switch ports and reads which ones there are Lasers connected to. It assigns the port to "Channel" in the Laser.
    Uses ClosestWL to decide which Laser corresponds to which port.
    '''
    NewPort = 0
    for Laser in Lasers:
        if Channel in Laser:
            del Laser[Channel]
    while NewPort < 8:
        ChangePort(NewPort)
        time.sleep(1/30)
        wl = scpi.readWL()
        if wl != 0:
            Laser = closestWL(wl)
            Lasers[Laser][Channel] = NewPort
            NewPort += 1
        else:
            NewPort += 1

def ChangeContinue(Laser):
    '''
    Changes the Boolean Coninue value in Laser
    '''
    Laser[Continue] = not Laser[Continue]

def make_figure():
    '''
    Makes a graph
    '''
    fig = Figure()
    fig.set_size_inches(10, 5.6)
    ax = fig.add_subplot(111)
    ax.tick_params(
        axis='both',          
        which='both',      
        bottom=False,      
        top=False,
        left=False,
        right=False,
        labelbottom=False,
        labelleft=False) 
    ax.set_xlabel("\n\nSamples")
    ax.grid()
    return fig

def draw_figure(canvas, figure):
    '''
    Draws the Figure on the Canvas
    '''
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side="top", fill="both", expand=1)
    return figure_canvas_agg

############## Background Thread ##############
def LockLaser():
    '''
    Scans through the connected ports, if Continue is True it runs  PID on the Laser before switching to the next port, otherwise it reads the wavelength and saves it to the LAser wavelength data.
    '''
    while True:
        while run_loop:
            for Laser in Lasers:
                if Laser[Continue] == True:
                    try:    
                        ChangePort(Laser[Channel])
                        time.sleep(t)
                        wl = scpi.readWL()
                        Laser[WavelengthReading].append(wl)
                        e = Laser[SetPoint]-wl
                        Laser[Error].append(e)
                        #print(Laser[Error][-1])
                        pid = PID(Laser)
                        output = pid + Laser[Offset]
                        if Laser[LowVoltage] <= output <= Laser[HighVoltage]:
                            value = output
                        elif output < Laser[LowVoltage]:
                            value = Laser[LowVoltage]
                        else:
                            value = Laser[HighVoltage]
                        name = Laser[DAC]
                        ljm.eWriteName(handle, name, value)
                        Laser[Voltage] = value
                        time.sleep(1/SampleRate - t)
                    except KeyError:
                        pass
                else:
                    try:    
                        ChangePort(Laser[Channel])
                        time.sleep(t)
                        wl = scpi.readWL()
                        Laser[WavelengthReading].append(wl)
                        time.sleep(1/SampleRate - t)
                    except KeyError:
                        pass
            global stop_threads
            if stop_threads:
                break
        if stop_threads:
            break 
            
RunLaserLock = threading.Thread(target=LockLaser, daemon = True)

############## GUI ##############
#GUI Buttons
LockButton11 = sg.Button("Lock at Stp 1", key = '-Lock11-')
LockButton21 = sg.Button("Lock at Stp 1", key = '-Lock21-')
LockButton31 = sg.Button("Lock at Stp 1", key = '-Lock31-')
LockButton41 = sg.Button("Lock at Stp 1", key = '-Lock41-')
LockButtons1 = ['-Lock11-', '-Lock21-', '-Lock31-', '-Lock41-']
down1 = [True, True, True, True]

LockButton12 = sg.Button("Lock at Stp 2", key = '-Lock12-')
LockButton22 = sg.Button("Lock at Stp 2", key = '-Lock22-')
LockButton32 = sg.Button("Lock at Stp 2", key = '-Lock32-')
LockButton42 = sg.Button("Lock at Stp 2", key = '-Lock42-')
LockButtons2 = ['-Lock12-', '-Lock22-', '-Lock32-', '-Lock42-']
down2 = [True, True, True, True]

SubmitButton1 = sg.Button("Submit PID", key = '-Submit1-')
SubmitButton2 = sg.Button("Submit PID", key = '-Submit2-')
SubmitButton3 = sg.Button("Submit PID", key = '-Submit3-')
SubmitButton4 = sg.Button("Submit PID", key = '-Submit4-')
SubmitButtons = ['-Submit1-', '-Submit2-', '-Submit3-', '-Submit4-']

PlotButton1 = sg.Button("Trend", key = '-plot1-')
PlotButton2 = sg.Button("Trend", key = '-plot2-')
PlotButton3 = sg.Button("Trend", key = '-plot3-')
PlotButton4 = sg.Button("Trend", key = '-plot4-')
PlotButtons = ['-plot1-','-plot2-','-plot3-','-plot4-']

VoltageButton1 = sg.Button("Reset Voltage", key = '-RV1-')
VoltageButton2 = sg.Button("Reset Voltage", key = '-RV2-')
VoltageButton3 = sg.Button("Reset Voltage", key = '-RV3-')
VoltageButton4 = sg.Button("Reset Voltage", key = '-RV4-')
VoltageButtons = ['-RV1-', '-RV2-', '-RV3-', '-RV4-']

DefaultButton1 = sg.Button("Save to Default", key = '-Default1-')
DefaultButton2= sg.Button("Save to Default", key = '-Default2-')
DefaultButton3 = sg.Button("Save to Default", key = '-Default3-')
DefaultButton4 = sg.Button("Save to Default", key = '-Default4-')
DefaultButtons =['-Default1-','-Default2-','-Default3-','-Default4-']

ConnectDevices = sg.Button("Connect Devices")
ChannelScan = sg.Button("Scan Ports", key = '-scan1-')
ChannelScan2 = sg.Button("Scan Ports", key = '-scan2-')


#First Window Layout
layout1 = [[ConnectDevices]]
window1 = sg.Window("PID", layout1)

#Start GUI
while True:
    event1, values1 = window1.read()
    if event1 == "Exit" or event1 == sg.WIN_CLOSED:
        break
    elif event1 == 'Connect Devices':
        success = connectDevices()
        if success == [0,1,1]:
            sg.Popup('Cannot Connect to Wavemeter')
        elif success == [1,0,1]:
            sg.Popup('Cannot Connect to DAC')
        elif success == [1,1,0]:
            sg.Popup('Cannot Connect to Switch')
        elif success == [0,0,1]:
            sg.Popup('Cannot Connect to Wavemeter\nCannot Connect to DAC')
        elif success == [0,1,0]:
            sg.Popup('Cannot Connect to Wavemeter \n CannotConnect to Switch')
        elif success == [1,0,0]:
            sg.Popup('Cannot Connect to DAC \n CannotConnect to Switch')
        elif success == [0,0,0]:
            sg.Popup('No Devices Connected')
        else:
            window1.close()
            #Second Window Layout
            layout2 = [[ChannelScan]]
            window2 = sg.Window("PID", layout2)
            while True:
                event2, values2 = window2.read()
                if event2 == "Exit" or event2 == sg.WIN_CLOSED:
                    break
                elif event2 == '-scan1-':
                    GetChannels()
                    window2.close()
                    RunLaserLock.start()
                    
                    #Third Window Layout
                    Laser_1_Quadrant = [[sg.Text("Laser 1")],
                        [sg.Text("SetPoint 1 (nm): "), sg.InputText(str(Laser1Default[SetPoint1]), size = (10,1), key = '-L1SP1-'), sg.Text(' '*13), sg.Text("Kp: "), sg.InputText(str(Laser1Default[Kp]), size = (7,1), key = '-L1Kp-'), sg.Text(' '*10), sg.Text("DAC: "), sg.InputText(str(Laser1Default[DAC]), size = (7,1), key = '-L1DAC-')],
                        [sg.Text("SetPoint 2 (nm): "), sg.InputText(str(Laser1Default[SetPoint2]), size = (10,1), key = '-L1SP2-'), sg.Text(' '*13), sg.Text("Ki:  "), sg.InputText(str(Laser1Default[Ki]), size = (7,1), key = '-L1Ki-'), sg.Text(' '*10), sg.Text("High Voltage (V): "), sg.InputText(str(Laser1Default[HighVoltage]), size = (7,1), key = '-L1HV-')],
                        [sg.Text('Laser 1 Wavelength '), sg.Text(str(Laser1[WavelengthReading][-1]), size = (10,1), key = '-L1WL-'), sg.Text(' nm'), sg.Text("Kd: "), sg.InputText(str(Laser1Default[Kd]), size = (7,1), key = '-L1Kd-'), sg.Text(' '*10), sg.Text("Low Voltage (V):  "), sg.InputText(str(Laser1Default[LowVoltage]), size = (7,1), key = '-L1LV-')],
                        [sg.Text('Voltage Output '), sg.Text(str(Laser1[Voltage]), size = (5,1), key = '-L1V-'), sg.Text('V'), sg.Text(' '*17), sg.Text("Gain (V/nm): "), sg.InputText(str(Laser1Default[Gain]), size = (7,1), key = '-L1G-'), sg.Text("Offset (V):   "), sg.Text(' '*4), sg.InputText(str(Laser1Default[Offset]), size = (7,1), key = '-L1O-')],
                        [LockButton11, LockButton12, PlotButton1, SubmitButton1, DefaultButton1, VoltageButton1] ]

                    Laser_2_Quadrant = [[sg.Text("Laser 2")],
                        [sg.Text("SetPoint 1 (nm): "), sg.InputText(str(Laser2Default[SetPoint1]), size = (10,1), key = '-L2SP1-'), sg.Text(' '*13), sg.Text("Kp: "), sg.InputText(str(Laser2Default[Kp]), size = (7,1), key = '-L2Kp-'), sg.Text(' '*10), sg.Text("DAC: "), sg.InputText(str(Laser2Default[DAC]), size = (7,1), key = '-L2DAC-')],
                        [sg.Text("SetPoint 2 (nm): "), sg.InputText(str(Laser2Default[SetPoint2]), size = (10,1), key = '-L2SP2-'), sg.Text(' '*13), sg.Text("Ki:  "), sg.InputText(str(Laser2Default[Ki]), size = (7,1), key = '-L2Ki-'), sg.Text(' '*10), sg.Text("High Voltage (V): "), sg.InputText(str(Laser2Default[HighVoltage]), size = (7,1), key = '-L2HV-')],
                        [sg.Text('Laser 2 Wavelength '), sg.Text(str(Laser2[WavelengthReading][-1]), size = (10,1), key = '-L2WL-'), sg.Text(' nm'), sg.Text("Kd: "), sg.InputText(str(Laser2Default[Kd]), size = (7,1), key = '-L2Kd-'), sg.Text(' '*10), sg.Text("Low Voltage (V):  "), sg.InputText(str(Laser2Default[LowVoltage]), size = (7,1), key = '-L2LV-')],
                        [sg.Text('Voltage Output '), sg.Text(str(Laser2[Voltage]), size = (5,1), key = '-L2V-'), sg.Text('V'), sg.Text(' '*17), sg.Text("Gain (V/nm): "), sg.InputText(str(Laser2Default[Gain]), size = (7,1), key = '-L2G-'), sg.Text("Offset (V):   "), sg.Text(' '*4), sg.InputText(str(Laser2Default[Offset]), size = (7,1), key = '-L2O-')],
                        [LockButton21, LockButton22, PlotButton2, SubmitButton2, DefaultButton2, VoltageButton2] ]
                    
                    Laser_3_Quadrant = [[sg.Text("Laser 3")],
                        [sg.Text("SetPoint 1 (nm): "), sg.InputText(str(Laser3Default[SetPoint1]), size = (10,1), key = '-L3SP1-'), sg.Text(' '*13), sg.Text("Kp: "), sg.InputText(str(Laser3Default[Kp]), size = (7,1), key = '-L3Kp-'), sg.Text(' '*10), sg.Text("DAC: "), sg.InputText(str(Laser3Default[DAC]), size = (7,1), key = '-L3DAC-')],
                        [sg.Text("SetPoint 2 (nm): "), sg.InputText(str(Laser3Default[SetPoint2]), size = (10,1), key = '-L3SP2-'), sg.Text(' '*13), sg.Text("Ki:  "), sg.InputText(str(Laser3Default[Ki]), size = (7,1), key = '-L3Ki-'), sg.Text(' '*10), sg.Text("High Voltage (V): "), sg.InputText(str(Laser3Default[HighVoltage]), size = (7,1), key = '-L3HV-')],
                        [sg.Text('Laser 3 Wavelength '), sg.Text(str(Laser3[WavelengthReading][-1]), size = (10,1), key = '-L3WL-'), sg.Text(' nm'), sg.Text("Kd: "), sg.InputText(str(Laser3Default[Kd]), size = (7,1), key = '-L3Kd-'), sg.Text(' '*10), sg.Text("Low Voltage (V):  "), sg.InputText(str(Laser3Default[LowVoltage]), size = (7,1), key = '-L3LV-')],
                        [sg.Text('Voltage Output '), sg.Text(str(Laser3[Voltage]), size = (5,1), key = '-L3V-'), sg.Text('V'), sg.Text(' '*17), sg.Text("Gain (V/nm): "), sg.InputText(str(Laser3Default[Gain]), size = (7,1), key = '-L3G-'), sg.Text("Offset (V):   "), sg.Text(' '*4), sg.InputText(str(Laser3Default[Offset]), size = (7,1), key = '-L3O-')],
                        [LockButton31, LockButton32, PlotButton3, SubmitButton3, DefaultButton3, VoltageButton3] ]
                    
                    Laser_4_Quadrant = [[sg.Text("Laser 4")],
                        [sg.Text("SetPoint 1 (nm): "), sg.InputText(str(Laser4Default[SetPoint1]), size = (10,1), key = '-L4SP1-'), sg.Text(' '*13), sg.Text("Kp: "), sg.InputText(str(Laser4Default[Kp]), size = (7,1), key = '-L4Kp-'), sg.Text(' '*10), sg.Text("DAC: "), sg.InputText(str(Laser4Default[DAC]), size = (7,1), key = '-L4DAC-')],
                        [sg.Text("SetPoint 2 (nm): "), sg.InputText(str(Laser4Default[SetPoint2]), size = (10,1), key = '-L4SP2-'), sg.Text(' '*13), sg.Text("Ki:  "), sg.InputText(str(Laser4Default[Ki]), size = (7,1), key = '-L4Ki-'), sg.Text(' '*10), sg.Text("High Voltage (V): "), sg.InputText(str(Laser4Default[HighVoltage]), size = (7,1), key = '-L4HV-')],
                        [sg.Text('Laser 4 Wavelength '), sg.Text(str(Laser4[WavelengthReading][-1]), size = (10,1), key = '-L4WL-'), sg.Text(' nm'), sg.Text("Kd: "), sg.InputText(str(Laser4Default[Kd]), size = (7,1), key = '-L4Kd-'), sg.Text(' '*10), sg.Text("Low Voltage (V):  "), sg.InputText(str(Laser4Default[LowVoltage]), size = (7,1), key = '-L4LV-')],
                        [sg.Text('Voltage Output '), sg.Text(str(Laser4[Voltage]), size = (5,1), key = '-L4V-'), sg.Text('V'), sg.Text(' '*17), sg.Text("Gain (V/nm): "), sg.InputText(str(Laser4Default[Gain]), size = (7,1), key = '-L4G-'), sg.Text("Offset (V):   "), sg.Text(' '*4), sg.InputText(str(Laser4Default[Offset]), size = (7,1), key = '-L4O-')],
                        [LockButton41, LockButton42, PlotButton4, SubmitButton4, DefaultButton4, VoltageButton4] ]
                    
                    layout3 = [
                        [sg.Text("Sample Rate (Hz): "), sg.InputText(str(SampleRate), size = (5,1), key = '-SR-'), sg.Button('Save To Default', key = 'SampleRateDefault'), ChannelScan2],
                        [sg.Text(' ')],
                        [Laser_1_Quadrant, [[sg.Text(' ')]], Laser_2_Quadrant, [[sg.Text(' ')]], Laser_3_Quadrant, [[sg.Text(' ')]], Laser_4_Quadrant]]
                        
                    window3 = sg.Window("PID", layout3, resizable = True)
                    
                    #Plot Window Layouts
                    plotlayout1 = [
                        [sg.Text("Laser 1 Trend")],
                        [sg.Canvas(key="-CANVAS1-")],
                        [sg.Text('Mean:'), sg.Text(str(np.mean(Laser1[WavelengthReading])), size = (10,1), key = '-L1WLM-'), sg.Text('    StDev:'), sg.Text(str(np.std(Laser1[WavelengthReading])), size = (10,1), key = '-L1STD-')],
                        [sg.Button("Clear"), sg.Button("Close"), sg.Button("Download"), sg.Button("Pause"), sg.Button("GHz")] ]
                         
                    plotwindow1 = sg.Window(
                            "Laser 1 Trend",
                            plotlayout1,
                            location=(0, 0),
                            element_justification="center",
                            modal = False,
                            finalize = True,
                            no_titlebar  = True,
                            grab_anywhere = True,
                            )
                    fig1 = make_figure()
                    fig_agg1 = draw_figure(plotwindow1["-CANVAS1-"].TKCanvas, fig1)


                    plotlayout2 = [
                        [sg.Text("Laser 2 Trend")],
                        [sg.Canvas(key="-CANVAS2-")],
                        [sg.Text('Mean:'), sg.Text(str(np.mean(Laser2[WavelengthReading])), size = (10,1), key = '-L2WLM-'), sg.Text('    StDev:'), sg.Text(str(np.std(Laser2[WavelengthReading])), size = (10,1), key = '-L2STD-')],
                        [sg.Button("Clear"), sg.Button("Close"), sg.Button("Download"), sg.Button("Pause"), sg.Button("GHz")] ]
                         
                    plotwindow2 = sg.Window(
                            "Laser 2 Trend",
                            plotlayout2,
                            location=(0, 0),
                            element_justification="center",
                            modal = False,
                            finalize = True,
                            no_titlebar  = True,
                            grab_anywhere = True,
                            )
                    fig2 = make_figure()
                    fig_agg2 = draw_figure(plotwindow2["-CANVAS2-"].TKCanvas, fig2)
                    
                        
                    plotlayout3 = [
                        [sg.Text("Laser 3 Trend")],
                        [sg.Canvas(key="-CANVAS3-")],
                        [sg.Text('Mean:'), sg.Text(str(np.mean(Laser3[WavelengthReading])), size = (10,1), key = '-L3WLM-'), sg.Text('    StDev:'), sg.Text(str(np.std(Laser3[WavelengthReading])), size = (10,1), key = '-L3STD-')],
                        [sg.Button("Clear"), sg.Button("Close"), sg.Button("Download"), sg.Button("Pause"), sg.Button("GHz")] ]
                         
                    plotwindow3 = sg.Window(
                            "Laser 3 Trend",
                            plotlayout3,
                            location=(0, 0),
                            element_justification="center",
                            modal = False,
                            finalize = True,
                            no_titlebar  = True,
                            grab_anywhere = True,
                            )
                    fig3 = make_figure()
                    fig_agg3 = draw_figure(plotwindow3["-CANVAS3-"].TKCanvas, fig3)
                    
                    
                    plotlayout4 = [
                        [sg.Text("Laser 4 Trend")],
                        [sg.Canvas(key="-CANVAS4-")],
                        [sg.Text('Mean:'), sg.Text(str(np.mean(Laser4[WavelengthReading])), size = (10,1), key = '-L4WLM-'), sg.Text('    StDev:'), sg.Text(str(np.std(Laser4[WavelengthReading])), size = (10,1), key = '-L4STD-')],
                        [sg.Button("Clear"), sg.Button("Close"), sg.Button("Download"), sg.Button("Pause"), sg.Button("GHz")] ]
                         
                    plotwindow4 = sg.Window(
                            "Laser 4 Trend",
                            plotlayout4,
                            location=(0, 0),
                            element_justification="center",
                            modal = False,
                            finalize = True,
                            no_titlebar  = True,
                            grab_anywhere = True,
                            )
                    fig4 = make_figure()
                    fig_agg4 = draw_figure(plotwindow4["-CANVAS4-"].TKCanvas, fig4)
                    
                    #Plot Window Data
                    PlotWindows = [{Show:False, isShowing:False, Pause: False, WindowName:plotwindow1, PlotEvent:plotevent1, PlotValues:plotvalues1, Figure:fig1, FigAgg:fig_agg1, axes:fig1.add_subplot(111), GHz:False},
                                   {Show:False, isShowing:False, Pause: False, WindowName:plotwindow2, PlotEvent:plotevent2, PlotValues:plotvalues2, Figure:fig2, FigAgg:fig_agg2, axes:fig2.add_subplot(111), GHz:False},
                                   {Show:False, isShowing:False, Pause: False, WindowName:plotwindow3, PlotEvent:plotevent3, PlotValues:plotvalues3, Figure:fig3, FigAgg:fig_agg3, axes:fig3.add_subplot(111), GHz:False},
                                   {Show:False, isShowing:False, Pause: False, WindowName:plotwindow4, PlotEvent:plotevent4, PlotValues:plotvalues4, Figure:fig4, FigAgg:fig_agg4, axes:fig4.add_subplot(111), GHz:False}]
                    #Hide the Plots
                    for window in PlotWindows:
                        window[WindowName].Hide()
                    
                    while True:
                        event, values = window3.read(timeout=10)
                        if event == "Exit" or event == sg.WIN_CLOSED:
                            for Laser in Lasers:
                                Laser[DAC] = 0
                            break
                        
                        #Show Plots if "Show" is True
                        for window in PlotWindows:
                            if window[Show] == True:
                                window[WindowName].UnHide()
                                window[isShowing] = True
                            else:
                                window[WindowName].Hide()
                                window[isShowing] = False
                        
                        #Plot Wavelength and Read Button Presses
                        for window in PlotWindows:
                            plotevent, plotvalues = window[PlotEvent], window[PlotValues]
                            if window[isShowing] == True:
                                plotevent, plotvalues = window[WindowName].read(timeout = 10)
                                if window[Pause] == False:
                                    ax = window[axes]
                                    ax.cla()
                                    ax.grid()
                                    if window[GHz]:
                                        FrequencyReading = [c/elem for elem in Lasers[PlotWindows.index(window)][WavelengthReading][1::]]
                                        y = np.array(FrequencyReading)
                                        x = np.arange(start = 0, stop = len(FrequencyReading), step = 1)
                                        ax.set_ylabel("Frequency (GHz)\n")
                                        window[WindowName]['-L'+str(PlotWindows.index(window)+1)+'WLM-'].update(str(round(np.mean(FrequencyReading),5)))
                                        window[WindowName]['-L'+str(PlotWindows.index(window)+1)+'STD-'].update(str(round(np.std(FrequencyReading),6)))
                                    else:
                                        Laser = Lasers[PlotWindows.index(window)]
                                        y = np.array(Laser[WavelengthReading][1::])
                                        x = np.arange(start = 0, stop = len(y), step = 1)
                                        ax.set_ylabel("Wavelngth (nm)\n")
                                        window[WindowName]['-L'+str(PlotWindows.index(window)+1)+'WLM-'].update(str(round(np.mean(Laser[WavelengthReading][1::]),8)))
                                        window[WindowName]['-L'+str(PlotWindows.index(window)+1)+'STD-'].update(str(round(np.std(Laser[WavelengthReading][1::]),10)))
                                    ax.plot(x,y)
                                    window[FigAgg].draw()
                            
                            if plotevent in ("Close", None):
                                window[WindowName].Hide()
                                window[Show] = False
                                window[isShowing] = False
                            elif plotevent == "Clear":
                                index = PlotWindows.index(window)
                                Lasers[index][WavelengthReading] = [Lasers[index][WavelengthReading][-1]]
                            elif plotevent == "Download":
                                index = PlotWindows.index(window)
                                filename = datetime.now().strftime("%Y-%m-%d--%H-%M-%S")+" Laser "+str(index+1)+" Wavelength Readings"
                                with open(filename+".txt", "w") as output:
                                    output.write(str(Lasers[index][WavelengthReading]))
                            elif plotevent == "Pause":
                                window[Pause] = not window[Pause]
                                window[WindowName].Element(plotevent).Update(('Pause', 'Run')[window[Pause]])
                            elif plotevent == "GHz":
                                window[GHz] = not window[GHz]
                                window[WindowName].Element(plotevent).Update(('GHz', 'nm')[window[GHz]])
                                
                        
                        #Diable Lock and Plot Buttons if Laser not Connected
                        for Laser in Lasers:
                            try:
                                Laser[Channel]
                                window3.FindElement(LockButtons1[Lasers.index(Laser)]).Update(disabled=False)
                                window3.FindElement(LockButtons2[Lasers.index(Laser)]).Update(disabled=False)
                                window3.FindElement(PlotButtons[Lasers.index(Laser)]).Update(disabled=False)
                            except KeyError:
                                window3.FindElement(LockButtons1[Lasers.index(Laser)]).Update(disabled=True)
                                window3.FindElement(LockButtons2[Lasers.index(Laser)]).Update(disabled=True)
                                window3.FindElement(PlotButtons[Lasers.index(Laser)]).Update(disabled=True)
                        
                        #Main Window Button Reads
                        if event == '-scan2-':
                            run_loop = False
                            GetChannels()
                            run_loop = True                          
                        elif event in LockButtons1:
                            index = LockButtons1.index(event)
                            Laser = Lasers[index]
                            if Laser[SetPoint] != float(values['-L'+str(Lasers.index(Laser)+1)+'SP1-']):
                                Laser[Error] = []
                                Laser[SetPoint] = float(values['-L'+str(Lasers.index(Laser)+1)+'SP1-'])
                            if (down1[index] and down2[index]) or not down1[index]:
                                ChangeContinue(Laser)
                            down1[index] = not down1[index]
                            window3.Element(event).Update(('Unlock at Stp 1', 'Lock at Stp 1 ')[down1[index]])
                            if not down2[index]:
                                down2[index] = not down2[index]
                                window3.Element(LockButtons2[index]).Update(('Unlock at Stp 2', 'Lock at Stp 2 ')[down2[index]])
                        elif event in LockButtons2:
                            index = LockButtons2.index(event)
                            Laser = Lasers[index]
                            if Laser[SetPoint] != float(values['-L'+str(Lasers.index(Laser)+1)+'SP2-']):
                                Laser[Error] = []
                                Laser[SetPoint] = float(values['-L'+str(Lasers.index(Laser)+1)+'SP2-'])
                            if (down1[index] and down2[index]) or not down2[index]:
                                ChangeContinue(Laser)
                            down2[index] = not down2[index]
                            window3.Element(event).Update(('Unlock at Stp 2', 'Lock at Stp 2 ')[down2[index]])
                            if not down1[index]:
                                down1[index] = not down1[index]
                                window3.Element(LockButtons1[index]).Update(('Unlock at Stp 1', 'Lock at Stp 1 ')[down1[index]])
                        elif event in DefaultButtons:
                            index = DefaultButtons.index(event)
                            Laser = Lasers[index]
                            Laser[SetPoint1] = float(values['-L'+str(Lasers.index(Laser)+1)+'SP1-'])
                            Laser[SetPoint2] = float(values['-L'+str(Lasers.index(Laser)+1)+'SP2-'])
                            Laser[Kp] = float(values['-L'+str(Lasers.index(Laser)+1)+'Kp-'])
                            Laser[HighVoltage] = float(values['-L'+str(Lasers.index(Laser)+1)+'HV-'])
                            Laser[Gain] = float(values['-L'+str(Lasers.index(Laser)+1)+'G-'])
                            Laser[Ki] = float(values['-L'+str(Lasers.index(Laser)+1)+'Ki-'])
                            Laser[LowVoltage] = float(values['-L'+str(Lasers.index(Laser)+1)+'LV-'])
                            Laser[DAC] = values['-L'+str(Lasers.index(Laser)+1)+'DAC-']
                            Laser[Kd] = float(values['-L'+str(Lasers.index(Laser)+1)+'Kd-'])
                            Laser[Offset] = float(values['-L'+str(Lasers.index(Laser)+1)+'O-'])
                            lines = ['SetPoint1 ' + str(Laser[SetPoint1])+'\n', 'SetPoint2 ' + str(Laser[SetPoint2])+'\n', 'Kp '+ str(Laser[Kp])+'\n', 'Ki '+ str(Laser[Ki])+'\n'
                                     'Kd '+ str(Laser[Kd])+'\n', 'Gain '+ str(Laser[Gain])+'\n', 'Offset '+ str(Laser[Offset])+'\n',
                                     'HighVoltage '+ str(Laser[HighVoltage])+'\n', 'LowVoltage '+ str(Laser[LowVoltage])+'\n', 'DAC '+ str(Laser[DAC])+'\n']
                            f = open("Laser"+str(index+1)+"Defaults.txt", "w")
                            f.writelines(lines)
                            f.close()                          
                        elif event == 'SampleRateDefault':
                            SampleRate = float(values['-SR-'])
                            f = open(event+".txt", "w")
                            f.write(str(SampleRate))
                            f.close()                            
                        elif event in SubmitButtons:
                            index = SubmitButtons.index(event)
                            Laser = Lasers[index]
                            Laser[Kp] = float(values['-L'+str(Lasers.index(Laser)+1)+'Kp-'])
                            Laser[HighVoltage] = float(values['-L'+str(Lasers.index(Laser)+1)+'HV-'])
                            Laser[Gain] = float(values['-L'+str(Lasers.index(Laser)+1)+'G-'])
                            Laser[Ki] = float(values['-L'+str(Lasers.index(Laser)+1)+'Ki-'])
                            Laser[LowVoltage] = float(values['-L'+str(Lasers.index(Laser)+1)+'LV-'])
                            Laser[DAC] = values['-L'+str(Lasers.index(Laser)+1)+'DAC-']
                            Laser[Kd] = float(values['-L'+str(Lasers.index(Laser)+1)+'Kd-'])
                            Laser[Offset] = float(values['-L'+str(Lasers.index(Laser)+1)+'O-'])                            
                        elif event in PlotButtons:
                            index = PlotButtons.index(event)
                            PlotWindows[index][Show] = not PlotWindows[index][Show]
                        elif event in VoltageButtons:
                            index = VoltageButtons.index(event)
                            name = Lasers[index][DAC]
                            ljm.eWriteName(handle, name, 0)
                            Lasers[index][Voltage] = 0

                        #Continually update Wavelength and Voltage every "Timeout"
                        for Laser in Lasers:
                            window3['-L'+str(Lasers.index(Laser)+1)+'WL-'].update(str(Laser[WavelengthReading][-1]))
                            window3['-L'+str(Lasers.index(Laser)+1)+'V-'].update(str(Laser[Voltage]))
                            
                    #Close all Windows When Loops are Broken        
                    window3.close()
                    plotwindow1.close()
                    plotwindow2.close()
                    plotwindow3.close()
                    plotwindow4.close()
                    #Stop Background Thread
                    stop_threads = True
                    ljm.close(handle)
            window2.close()
window1.close()



    