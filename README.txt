----------------------READ ME---------------------
This program requires the use of a Bristol 871 wavemeter, Bristol fiber-optic switch, and LabJack T4 as a DAC. It will need to be edited to accomodate other equipment.
The Lasers must be first manually tuned to have a mode-hop free tuning range large enough to accomodate the correction voltage sent.  


HOW THE PROGRAM WORKS:
Once the program is run and the devices are connected, it scans through all the ports of the switch and polls the wavemeter.
If the wavemeter returns a signal then it assigns that port to a Laser field.
This assignment is dependent on the wavelngth of the Laser and the default wavelengths.
Then in the background the program switches between all the ports which have abeen assigned at the speed specified by the 'Sample Rate' setting.
The wavemeter is polled and the returned wavelength is saved.
When a Laser is Locked the background thread has an additional step of calculating a correction voltage and sending that to the DAC.
While the program is switching to a different laser port it maintains the last correction voltage sent to the laser being locked.
This allows for independent locking and unlocking of all lasers. It also allows for an independent trend graph to be generated for each laser.


REQUIRED INSTALLATIONS: (through Python package manager)
Numpy
Matplotlib
PySimpleGui
mcculw
labjack-ljm
---> Also navigate to \Python_LJM_2020_11_20\Examples\Basic\LabJack-2019-05-20.exe and run (ensure Python is closed)
---> Navigate to \FOSC\mccdaq.exe and run (ensure Python is closed)


REQUIRED FILES IN WORKING DIRECTORY:
digital.py
propsbase.py
pyBristolSCPI.py
Laser1Defaults.txt
Laser2Defaults.txt
Laser3Defaults.txt
Laser4Defaults.txt
SampleRateDefault.txt


RUNNING THE PROGRAM:
Open 'LaserLockProgram.py' and run the script
Ensure the wavemeter, switch, and DAC are connected
Click 'Connect Devices'
If the wavemeter immediately says it is not connected it must be power cycled. This happens when the telnet connection is forcibly closed and therefore cannot be reopened
If a device does not connect check USB connections
	Debug using \FOSC\FOSC.py for the switch
	Debug Using \Python_LJM_2020_11_20\Examples\Basic\eAddresses.py for the DAC
Click 'Scan Ports'
This scans through all the ports of the switch and chooses which ports belong to which laser based on the default wavelength setpoint in Laser_Defaults.txt

If no lasers are found, but they are on and coupled it could be because the wavemeter is still stabilizing check using NuView
	Debug by switching the switch to the port in which the laser light should be connected using FOSC.py and attempt to get the wavelength using NuView

Once the main window is opened you may lock the Lasers that are connected, but change the parameters for any laser. 
Pressing 'Submit', saves the PID parameters for this session, and updates them if a laser is being locked.
Pressing 'Lock laser' will automatically update the PID parameters.
Pressing 'Save to Default' will save the PID parameters to the default for that laser.
Presing 'Trend' will open/close a wavelength trend window.

Before the Laser is Locked the wavelength shoud be adjusted to within two decimal places of the setpoint. 
Otherwise, the PID will output the max/min voltage possible in order to adjust it to the setpoint.
When the Laser is unlocked the last voltage sent will continue to be sent until it is relocked. 
To reset this to 0V adjust the gain field to 0 and lock the laser briefly.

The trend windows may be moved by dragging any part of them. They may not be resized without editing the program.
---> To resize navigate to the 'make_figure' function and change the figure size. This will need to be adjusted if a different monitor is used.
Pausing the trend does not pause data collection. 
Cleating the trend does clear all collected data.
The wavelength data in nm may be downloaded to the working directory and is named 'Year-Month-Day--Hour-Minute-Second Laser_ Wavelength Readings.txt'
The data will be downloaded in nm even if the trend is showing GHz.


CONNECTING THE DAC TO LASER:
Plug a BNC into the labjack and change the 'DAC' label in the program to the port which it is connected. 
Connect the BNC to a FINE input on the front of the DLC Pro

On the DLC Pro:
Press the "chart" button
Press the "book" button
Select 'Anolog Remote Control'
Select 'PC'
Enable the ARC
Select the input (The port you connected the BNC to)
Select the factor for the voltage (probably 1)


POSSIBLE ISSUES:
Cannot find module/file:
	Ensure all modules/files are properly installed, and the correct files are in the working directory
Cannot connect to wavemeter:
	Check connections and/or power cycle the device.
	Sometimes it takes a minute to boot up so give it a few minutes when powering it on
Connot Connect to DAC.
	Check connections and/or power cycle the device.
	-----
	Power Cycle Device and Restart Computer
	-----
	Uninstall labjack-ljm from Python
	Uninstall \Python_LJM_2020_11_20\Examples\Basic\LabJack-2019-05-20.exe
	Restart Computer
	Reinstall labjack-ljm in Python
	Close Python and reinstall \Python_LJM_2020_11_20\Examples\Basic\LabJack-2019-05-20.exe

	If this is happening frequently update device firmware in kipling (You might have to follow the above procedure for kipling to recognize the device)
	If the issue persists see:
		https://labjack.com/support/app-notes/device-not-found
		https://labjack.com/support/app-notes/usb-communication-failure	 
Cannot Connect to Switch
	Check connections and/or power cycle the device.
	-----
	Uninstall mcculw
	Uninstall \FOSC\mccdaq.exe
	Restart Computer
	Reinstall mcculw
	Close Python and reinstall \FOSC\mccdaq.exe

Trend window too small/large:
	 Navigate to the 'make_figure' function and change the figure size

Laser not recognized:
	If the light is getting through the port (Check using \FOSC\FOSC.py) and the wavemeter is reading it (Check using NuView and ensure the detector is not saturated).
	Run LaserLock.py close the main window. 	
	In shell type Laser_[Channel] (Fill in _ with laser number)
	If Channel is incorect debug program
	You might try just increasing global variable t first

Wavelength reading incoorect after switching ports:
	Increase global variable t

Wavlength not changing after locking laser:
	Ensure the voltage is being sent to the proper channel using the instructions outlined in 'CONNECTING THE DAC TO LASER'
	Ensure the proper input is selected in the Laser Controller.
	Ensure the proper DAC is selescted in teh PID Program.
	Ensure the maximum/minimum voltage isn't being output by the DAC.

Max/Min voltage being sent:
	The laser wavelength was tuned too far from the setpoint, ensure the laser is tuned to within 2 decimal places of the setpoint.


	 

