#!/usr/bin/python

# This program provides the user interface to the precision sample dispenser 
# control software executing on an arduino. The commands that are understood
# by the arduino system are stored in a json file, named psdCommands, and 
# located in the same directory as this script. 
#
# The user-interface is divided up and encapsulated among a set of classes.
#
# ArduinoLink encapsulates the serial connection with the arduino, and a
# trace window for echoing commands and responses to and from the arduino.
#
# The TraceControl is a member of ArduinoLink. It is only accessed from within
# ArduinoLink. It provides a scrolling trace window that echoes commands sent 
# to, and responses received from the arduino. From the user's perspective, 
# the trace window is read-only. However, there is a button labeled clear for 
# clearing the contents of the window.
#
# Classes M1Control, and M2Control each provide control of the two stepper 
# motors in the system. Each class provides UI controls to home, limit, 
# step forward, and step reverse. Both M1Control and M2Control are derived 
# from class MotorControl.
#
# LoaderControl encapsulates the widgets used to execute sample loading 
# functions.
#
# The AppControl class provides UI mechanisms for executing Reset, Status,
# Find Needle, selecting a profile, uploading a profile, and executing a 
# profile.
# 
# The AppControl class includes a pair of buttons; one for stopping the arduino, 
# and one for exiting the application.

from Tkinter import *
import tkFileDialog
import ttk

import serial
import json
import time

# ArduinoLink encapsulates the serial port connection and the 
# trace control.
class ArduinoLink( object ):
	def __init__( self, root, arduinoCmds, debug ):
		self._root = root
		self._debug = debug
		try:
			if( debug == False ):
				self._conn = serial.Serial( 
					arduinoCmds["com"]["port"], 
					int( arduinoCmds["com"]["baud"]), 
					timeout=float( arduinoCmds["com"]["timeout"]))
			self._trace = TraceControl( root )
		except:
			print "Error opening com port:", sys.exc_info()[0]
			raise 
	
	def Tick( self ):
		if self._debug == True:
			self._trace._textwidget.config( state='normal' )
			self._trace._textwidget.insert( END, '...tick...\n' )
			self._trace._textwidget.see( END )
			self._trace._textwidget.config( state='disabled' )

			# reset the idle event timer
			self._root.after( 500, self.Tick )
			return

		readBuffer = ''

		# see if the arduino has written anything to the serial port
		bytesToRead = ser.in_waiting()
		if bytesToRead > 0:
			# the arduino wrote some characters...
			# read the serial port in a loop until 
			# the end-of-message character is read
			while True:
				# read the characters sent from the arduino
				readBuffer += this._conn.read( bytesToRead )

				# see if the arduino sent the last character
				if readBuffer.endswith( '=' ):
					break;

				# if the end-of-message character was 
				# not received, wait for more characters
				bytesToRead = ser.in_waiting()
				while bytesToRead <= 0:
					# wait 50 milliseconds
					sleep( 0.5 )
					# see if more characters arrived
					bytesToRead = ser.in_waiting()

			# enable writing to the textwidget
			self._trace._textwidget.config( state='normal' )

			# write the message received from 
			# the arduino to the textwidget
			self._trace._textwidget.insert( END, readBuffer )

			# write a newline to end the message
			self._trace._textwidget.insert( END, '\n' )
			# scroll the textwidget to the end so you can see it
			self._trace._textwidget.see( END )
			# disable the text widget so it's read-only
			self._trace._textwidget.config( state='disabled' )

		# reset the idle event timer
		self._root.after( 250, self.Tick )

	def Send( self, cmd ):
		# enable the trace window for writing
		self._trace._textwidget.config( state='normal' )

		# write the command to the trace window
		self._trace._textwidget.insert( END, cmd + '\n' )

		if( self._debug == False ):
			# write the command to the arduino
			self._conn.write( cmd + '=' )

			# give the arduino time to respond
			time.sleep( 0.025 )

			# read and echo the response from the arduino
			response = self.Read()

			self._trace._textwidget.insert( END, response + '\n' )
			self._trace._textwidget.insert( END, str( len( response )) + ' chars read\n' )
			#self._trace._textwidget.see( END )
		else:
			self._trace._textwidget.insert( END, "debug mode\n" )
			#self._trace._textwidget.see( END )

		self._trace._textwidget.see( END )
		# disable user input to the trace window
		self._trace._textwidget.config( state='disabled' )

	def Read( self ):
		responseStr = ''
		if( self._debug == true ):
			responseStr = 'debug mode'
		else:
			while True:
				responseChar = self._conn.read( 1 )
				responseStr += responseChar
				if responseChar == '=': break
		return responseStr

# LoaderControl encapsulates a label frame, five buttons, and a combo box.
# The combo box lets you select one of the profiles defined in the json file, 
# psdProfiles. The Load button sends the selected profile to the arduino. 
# The Go button sends the go command to the arduino, instructing it to execute
# the most recent profile. the reset button issues a reset command to the arduino.
# The status button reads the arduino status output and displays it in the trace
# window.
class LoaderControl( object ):
	# set up the layout of the buttons relative to the loader function label frame
	def __init__( self, root, arduinoCmds, arduinoLink ):
		self._arduinoCmds = arduinoCmds
		self._arduinoLink = arduinoLink
		self._profiles = None

		lfrm = LabelFrame( root, text='Load Functions', padx=10, pady=10, borderwidth=0 )
		btnReset      = Button( lfrm, text='Reset',       width=12, command=lambda: self.btnReset_click( ))
		btnFindNeedle = Button( lfrm, text='Find Needle', width=12, command=lambda: self.btnFindNeedle_click( ))
		btnStatus     = Button( lfrm, text='Status',      width=12, command=lambda: self.btnStatus_click( ))

		try:
			with open('psdProfiles') as pfile:
				self._profiles = json.load(pfile)
		except:
			# json file with profile definitions was not found
			print "Error opening motor profiles"
			raise

		profTuples = ()
		for p in self._profiles['profile']:
			profTuples += (p['label'],)

		self._box_value = StringVar()

		self._cbox = ttk.Combobox( lfrm, textvariable=self._box_value, width=13 )
		self._cbox['values'] = profTuples
		self._cbox.current(0)
		self._cbox.state(['readonly'])

		btnLoad = Button( lfrm, text='Load', width=12, command=lambda: self.btnLoad_click( ))
		btnGo   = Button( lfrm, text='Go',   width=12, command=lambda: self.btnGo_click( ))

		lfrm.grid         ( row=0, column=0, sticky='nw' )
		btnReset.grid     ( row=0, column=0 )
		btnFindNeedle.grid( row=1, column=0 )
		btnStatus.grid    ( row=0, column=1 )
		self._cbox.grid   ( row=2, column=0 )
		btnLoad.grid      ( row=2, column=1 )
		btnGo.grid        ( row=3, column=1 )

	def btnFindNeedle_click( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["findneedle"] )

	def btnGo_click( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["go"] )

	def btnLoad_click( self ):
		# get the profile label selected in the combo box
		if( self._cbox.current() > -1 ):
			selectedLabel = self._cbox['values'][self._cbox.current()]

			# find the profile array entry that corresponds to the profile selected in the combo box
			selectedProfile = [ p for p in self._profiles["profile"] if p["label"] == selectedLabel ]

			if( selectedProfile[0]["m1"] != None ):
				self._arduinoLink.Send( selectedProfile[0]["m1"] )

			if( selectedProfile[0]["m2"] != None ):
				# give the arduino time to respond
				#time.sleep( 1.0 )
				self._arduinoLink.Send( selectedProfile[0]["m2"] )

	def btnReset_click( self ):
		self._arduinoLink.Send( self._arduinoCmds["m1"]["reverse"]["movelong"] )
		#time.sleep( 1.0 )
		self._arduinoLink.Send( self._arduinoCmds["m2"]["reverse"]["movelong"] )

	def btnStatus_click( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["status"] )

class MotorControl( object ):
	def __init__( self, root, arduinoCmds, arduinoLink, motorNo ):
		self._arduinoCmds = arduinoCmds
		self._arduinoLink = arduinoLink

		self._motorNo = motorNo
		if ( motorNo == 1 ):
			self._frameText = 'M1 Control'
			self._motorName= 'm1'
		else:
			self._frameText = 'M2 Control'
			self._motorName= 'm2'

		lfrm = LabelFrame( root, text=self._frameText, padx=10, pady=10, borderwidth=0 )
		btnHome    = Button( lfrm, text='Home',     width=12, command=lambda: self.btnHome_click   ( ))
		btnLimit   = Button( lfrm, text='Limit',    width=12, command=lambda: self.btnLimit_click  ( ))
		btnStepFwd = Button( lfrm, text='Step fwd', width=12, command=lambda: self.btnStepFwd_click( )) 
		btnStepRvs = Button( lfrm, text='Step rvs', width=12, command=lambda: self.btnStepRvs_click( )) 

		lfrm.grid( row=self._motorNo, column=0, sticky='nw' )
		btnHome.grid   ( row=0, column=0 )
		btnLimit.grid  ( row=0, column=1 )
		btnStepRvs.grid( row=1, column=0 )
		btnStepFwd.grid( row=1, column=1 )

	def btnHome_click( self ):
		self._arduinoLink.Send( self._arduinoCmds[self._motorName]["reverse"]["movelong"] )

	def btnLimit_click( self ):
		self._arduinoLink.Send( self._arduinoCmds[self._motorName]["forward"]["movelong"] )

	def btnStepFwd_click( self ):
		self._arduinoLink.Send( self._arduinoCmds[self._motorName]["forward"]["moveshort"] )

	def btnStepRvs_click( self ):
		self._arduinoLink.Send( self._arduinoCmds[self._motorName]["reverse"]["moveshort"] )

class AppControl( object ):
	def __init__( self, root, arduinoCmds, arduinoLink ):
		self._arduinoCmds = arduinoCmds
		self._arduinoLink = arduinoLink

		lfrm = LabelFrame( root, padx=10, pady=10, borderwidth=0 )
		btnStop  = Button( lfrm, text='Stop', width=12, command=lambda: self.btnStop_click( ))
		btnExit  = Button( lfrm, text='Exit', width=12, command=exit )

		lfrm.grid( row=4, column=0, sticky=SW )
		btnExit.grid ( row=0, column=0 )
		btnStop.grid ( row=0, column=1 )

	def btnStop_click( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["stop"] )

class TraceControl( object ):
	def __init__( self, root ):
		lfrm = LabelFrame( root, text='Trace', padx=10, pady=10 )
		self._textwidget = Text( lfrm, borderwidth=1 )
		self._textwidget.config( state='disabled' )

		sbTrace = Scrollbar( lfrm )
		self._textwidget.config( yscrollcommand=sbTrace.set )
		sbTrace.config( command=self._textwidget.yview )

		btnClear = Button( lfrm, text='Clear', width=12, command=lambda: self.btnClear_click( ))

		lfrm.grid( row=0, column=1, rowspan=4, sticky='nsew' )
		lfrm.grid_rowconfigure( 0, weight=1 )
		lfrm.grid_columnconfigure( 0, weight=1 )

		self._textwidget.grid( row=0, column=0, sticky='nsw' )
		sbTrace.grid( row=0, column=1, sticky='nse' )

		btnClear.grid( row=1, column=0, sticky='sw' )

	def btnClear_click( self ):
		self._textwidget.config( state='normal' )
		self._textwidget.delete( '1.0', END )
		self._textwidget.config( state='disabled' )

def BuildUI( tkRoot, arduinoCmds, debug ):
	frm = Frame( tkRoot, padx=10, pady=10 )

	arduinoLink = ArduinoLink( frm, arduinoCmds, debug )

	loaderControl = LoaderControl( frm, arduinoCmds, arduinoLink )
	m1Control   = MotorControl( frm, arduinoCmds, arduinoLink, 1 )
	m2Control   = MotorControl( frm, arduinoCmds, arduinoLink, 2 )
	appControl  = AppControl( frm, arduinoCmds, arduinoLink )

	frm.grid( row=0, column=0, sticky=W )

	arduinoLink.Tick( )
	return frm

def LoadArduinoCommands( ):
	pdata = None
	try:
		with open('psdCommands') as pfile:
			pdata = json.load(pfile)
	except:
		print "Error opening arduinoCmds command file"
		raise
	return pdata

def RunningInDebugMode( ):
	for arg in sys.argv:
		if( arg == '--debug' ) or ( arg == '-d' ):
			return True
	return False

debug = RunningInDebugMode()
root = BuildUI( Tk( ), LoadArduinoCommands(), debug )
root.mainloop()
