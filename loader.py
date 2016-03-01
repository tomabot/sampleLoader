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
# The AppControl class provides UI mechanisms for executing Status, Find
# Needle, selecting a profile, uploading a profile, and executing a 
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
import timeit
import datetime

from optparse import OptionParser

class AppControl( object ):
	def __init__( self, root, arduinoCmds, arduinoLink ):
		self._arduinoCmds = arduinoCmds
		self._arduinoLink = arduinoLink

		lfrm = LabelFrame( root, padx=10, pady=10, borderwidth=0 )
		btnStop  = Button( lfrm, text='Stop', height=2, width=18, command=lambda: self.onStopButtonClick( ))
		btnExit  = Button( lfrm, text='Exit', height=2, width=18, command=exit )

		lfrm.grid( row=3, column=0, sticky=SW )
		btnExit.grid ( row=0, column=0 )
		btnStop.grid ( row=0, column=1 )

	def onStopButtonClick( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["stop"] )
		self._arduinoLink.EnableUiControls()

# ArduinoLink encapsulates the serial port connection and the 
# trace control.
class ArduinoLink( object ):
	def __init__( self, root, arduinoCmds, logFileName, debug ): 
		self._root = root
		self._debug = debug
		self._conn = None
		self._logFileName = logFileName

		self._loaderControl = None
		self._m1Control = None
		self._m2Control = None

		self._timer = 0
		self._timerActive = False
		
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

	def DisableUiControls( self ):
		self._loaderControl.Disable()
		self._m1Control.Disable()
		self._m2Control.Disable()

	def EnableUiControls( self ):
		self._loaderControl.Enable()
		self._m1Control.Enable()
		self._m2Control.Enable()

	def InitializeUiStateControl( self, loaderControl, m1Control, m2Control ):
		self._loaderControl = loaderControl
		self._m1Control = m1Control
		self._m2Control = m2Control

		self.Tick( )

	def Tick( self ):
		# see if the arduino has written anything to the serial port
		if( self._debug == False ):
			bytesToRead = self._conn.inWaiting()
			if bytesToRead > 0:
				# enable writing to the textwidget
				self._trace._textwidget.config( state='normal' )

				# write the message received from the arduino to the textwidget
				arduinoStr = self._conn.read( bytesToRead )
				self._trace._textwidget.insert( END, '<<<' + arduinoStr + '\n' )

				# write a newline to end the message
				#self._trace._textwidget.insert( END, '\n' )

				# scroll the textwidget to the end so you can see it
				self._trace._textwidget.see( END )

				# disable the text widget so it's read-only
				self._trace._textwidget.config( state='disabled' )

				# Log arduino responses 
				logEntry = ''.join([ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f "), arduinoStr ])
				with open(self._logFileName, 'a') as logFile:
					print >>logFile, logEntry

		# if we're currently executing a long-running arduino operation, adjust 
		# the idle event timer quantum from the anticipated duration, and if
		# the time quantum expires, disable the timer, and reenable the UI
		if( self._timerActive ) :
			self._timer = self._timer - 1
			if( self._timer <= 0 ):
				self.EnableUiControls()
				self._timerActive = False

		# re-arm the idle event timer
		self._root.after( 100, self.Tick )

	def SetTimer( self, duration ):
		if(( self._loaderControl != None ) and ( self._m1Control != None ) and ( self._m2Control != None )):
			self.DisableUiControls()

		# duration is in seconds, idle timer is in 100 millisecond steps
		self._timer = duration 
		self._timerActive = True

	def Send( self, cmd ):
		# Log commands to the arduino 
		logEntry = ''.join([ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f "), cmd ])
		with open(self._logFileName, 'a') as logFile:
			print >>logFile, logEntry

		# enable the trace window for writing
		self._trace._textwidget.config( state='normal' )

		# write the command to the trace window
		self._trace._textwidget.insert( END, '>>>' + cmd + '\n' )

		if( self._debug == False ):
			# write the command to the arduino
			self._conn.write( cmd + '=' )

		# scroll the text widget to the end so you can see it
		self._trace._textwidget.see( END )

		# disable user input to the trace widget so it's read-only
		self._trace._textwidget.config( state='disabled' )

# LoaderControl encapsulates a label frame, five buttons, and a combo box.
# The combo box lets you select one of the profiles defined in the json file, 
# psdProfiles. The Load button sends the selected profile to the arduino. 
# The Go button sends the go command to the arduino, instructing it to execute
# the most recent profile. The reset button issues a reset command to the arduino.
# The status button reads the arduino status output and displays it in the trace
# window.
class LoaderControl( object ):
	# set up the layout of the buttons relative to the loader function label frame
	def __init__( self, root, arduinoCmds, arduinoLink ):
		self._arduinoCmds = arduinoCmds
		self._arduinoLink = arduinoLink
		self._profiles = None

		self._lfrm = LabelFrame( root, text='Load Functions', 
			padx=10, pady=10, borderwidth=0 )
		btnFindNeedle = Button( self._lfrm, text='Find Needle', height=2, width=18, 
			command=lambda: self.onFindNeedleButtonClick( ))
		btnStatus = Button( self._lfrm, text='Status', height=2, width=18, 
			command=lambda: self.onStatusButtonClick( ))

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

		self._cbox = ttk.Combobox( self._lfrm, textvariable=self._box_value, width=13, font=( 'Calibri', 12))
		self._cbox['values'] = profTuples
		self._cbox.current(0)
		self._cbox.state(['readonly'])

		btnLoad = Button( self._lfrm, text='Load', height=2, width=18, command=lambda: self.btnLoad_click( ))
		btnGo = Button( self._lfrm, text='Go', height=2, width=18, command=lambda: self.btnGo_click( ))

		self._lfrm.grid   ( row=0, column=0, sticky='nw' )
		btnFindNeedle.grid( row=0, column=0 )
		btnStatus.grid    ( row=0, column=1 )
		self._cbox.grid   ( row=1, column=0 )
		btnLoad.grid      ( row=1, column=1 )
		btnGo.grid        ( row=2, column=1 )

	def onFindNeedleButtonClick( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["findneedle"] )

	def btnGo_click( self ):
		selectedLabel = self._cbox['values'][self._cbox.current()]

		# find the profile array entry that corresponds to the profile selected in the combo box
		selectedProfile = [ p for p in self._profiles["profile"] if p["label"] == selectedLabel ]

		if( selectedProfile[0]["time"] != None ):
			# get the time it takes to execute the profile from the json file entry
			timerVal = int( selectedProfile[0]["time"] ) * 10
			self._arduinoLink.SetTimer( timerVal )

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

	def onStatusButtonClick( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["status"] )

	def Disable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='disable')

	def Enable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='normal')

class LoginControl( object ):
        def __init__( self, root, loaderControl, m1Control, m2Control, logFileName, barcodeLen ):
		self._logFileName = logFileName

                lfrm = LabelFrame( root, text='Log Control', padx=10, pady=10, borderwidth=0 )

		self._operVar = StringVar()
		
                lfrmOper = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                labelOper = Label( lfrmOper, text="     operator:" )
                self.entryOper = Entry( lfrmOper, textvariable=self._operVar, font=( 'Calibri', 12 ))

		self._accessionVar = StringVar()
		self._accessionVar.trace( 'w', self._HandleAccession )
		self._accessionConfVar = StringVar()
		self._accessionConfVar.trace( 'w', self._HandleAccessionConf )

                #lfrmAcc = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                lfrmAcc = LabelFrame( lfrm, padx=10, pady=8, borderwidth=0 ) 
                labelAccession      = Label( lfrmAcc, text="accession id:" )
                self.entryAccession = Entry( lfrmAcc, width="14", textvariable=self._accessionVar, font=( 'Calibri', 12 ))

                labelAccessionConf      = Label( lfrmAcc, text="     confirm:" )
                self.entryAccessionConf = Entry( lfrmAcc, width="14", textvariable=self._accessionConfVar, font=( 'Calibri', 12 ))

		self._sampleVar = StringVar()
		self._sampleVar.trace( 'w', self._HandleSample )
		self._sampleConfVar = StringVar()
		self._sampleConfVar.trace( 'w', self._HandleSampleConf )

                #lfrmSampleId = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                lfrmSampleId = LabelFrame( lfrm, padx=10, pady=8, borderwidth=0 ) 
                labelSampleId = Label( lfrmSampleId, text="sample id:" )
                self.entrySample = Entry( lfrmSampleId, width="14", textvariable=self._sampleVar, font=( 'Calibri', 12 ))
                labelSampleConf = Label( lfrmSampleId, text="  confirm:" )
                self.entrySampleConf = Entry( lfrmSampleId, width="14", textvariable=self._sampleConfVar, font=( 'Calibri', 12 ))

                lfrmBtn = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                btnSave = Button( lfrmBtn, text="Save", height=2, width=18, 
			command=lambda: self.onSaveButtonClick( loaderControl, m1Control, m2Control ))
		btnEdit = Button( lfrmBtn, text="Edit", height=2, width=18,
			command=lambda: self.onEditButtonClick( loaderControl, m1Control, m2Control ))
		btnClear = Button( lfrmBtn, text="Clear", height=2, width=18, 
			command=lambda: self.onClearButtonClick( loaderControl, m1Control, m2Control ))

                lfrm.grid( row=0, column=1, sticky=NSEW )
                lfrmOper.grid( row=0, column=0, columnspan=2, sticky=W )
                lfrmAcc.grid( row=1, column=0 )
                lfrmSampleId.grid( row=1, column=1 )
                lfrmBtn.grid( row=2, column=0 )

                labelOper.grid( row=0, column=0 )
                self.entryOper.grid( row=0, column=1, columnspan=2 )

                labelAccession.grid( row=1, column=0, sticky=SW )
                self.entryAccession.grid( row=1, column=1 )
                labelAccessionConf.grid( row=2, column=0, sticky=SW )
                self.entryAccessionConf.grid( row=2, column=1 )

                labelSampleId.grid( row=3, column=0, sticky=SW )
                self.entrySample.grid( row=3, column=1 )
                labelSampleConf.grid( row=4, column=0, sticky=SW )
                self.entrySampleConf.grid( row=4, column=1 )

                btnSave.grid ( row=0, column=0 )
                btnEdit.grid ( row=0, column=1 )
                btnClear.grid( row=0, column=2 )

		self._barcodeLen = barcodeLen
		self._arrivalTime = [None] * barcodeLen

                self.entryOper.focus_set()

	def _HandleAccession( self, *dummy ):
		accessionStr = self._accessionVar.get()
		arrivalIndex = len( accessionStr ) - 1

		# see if this is the first character arriving in the entry widget
		if arrivalIndex == 0:
			# this is the first character arriving in the entry widget,
			# so initialize the arrivalTime array
			arrivalTime = [None] * self._barcodeLen

		if arrivalIndex >= 0 and arrivalIndex < self._barcodeLen:
			self._arrivalTime[ arrivalIndex ] = timeit.default_timer()

		if arrivalIndex == self._barcodeLen - 1:
			# see if a scanner was used to enter the accession number
			if (( self._arrivalTime[ self._barcodeLen - 1 ] - self._arrivalTime[ 0 ]) < 0.25 ):
				# looks as though a scanner was used to enter the accession number
				# disable the accession number confirmation entry widget and 
				# transfer focus to the sample id entry widget
				self._accessionConfVar.set( self._accessionVar.get( ))
				self.entrySample.focus_set( )

	def _HandleAccessionConf( self, *dummy ):
		#print 'accession confirmation: ', self._accessionConfVar.get()
		pass

	def _HandleSample( self, *dummy ):
		sampleStr = self._sampleVar.get()
		arrivalIndex = len( sampleStr ) - 1

		# see if this is the first character arriving in the entry widget
		if arrivalIndex == 0:
			# this is the first character arriving in the entry widget,
			# so initialize the arrivalTime array
			arrivalTime = [None] * self._barcodeLen

		if arrivalIndex >= 0 and arrivalIndex < self._barcodeLen:
			self._arrivalTime[ arrivalIndex ] = timeit.default_timer()

		if arrivalIndex == self._barcodeLen - 1:
			# see if a scanner was used to enter the sample ID
			if (( self._arrivalTime[ self._barcodeLen - 1 ] - self._arrivalTime[ 0 ]) < 0.25 ):
				# looks as though a scanner was used to enter the accession number
				# disable the accession number confirmation entry widget and 
				# transfer focus to the sample id entry widget
				self._sampleConfVar.set( self._sampleVar.get( ))
				self.entryOper.focus_set( )

	def _HandleSampleConf( self, *dummy ):
		#print 'sample id confirmation: ', self._sampleConfVar.get()
		pass

	def LogSessionInfo( self, operatorStr, sampleStr, accessionStr ):
		# Log operator name, sample id, and accession id 
		logEntry = ''.join([
			datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
			" operator=", operatorStr, 
			" sample=", sampleStr, 
			" accession=", accessionStr ])

		with open(self._logFileName, 'a') as logFile:
			print >>logFile, logEntry

	def onClearButtonClick( self, loaderControl, m1Control, m2Control ):
		self._arrivalTime = [None] * self._barcodeLen

		self._sampleVar.set("")
		self._sampleConfVar.set("")
		self._accessionVar.set("")
		self._accessionConfVar.set("")
		self._operVar.set("")

                loaderControl.Disable()
		m1Control.Disable()
		m2Control.Disable()

		self.entryOper.configure(state='normal')
		self.entryAccession.configure(state='normal')
		self.entryAccessionConf.configure(state='normal')
		self.entrySample.configure(state='normal')
		self.entrySampleConf.configure(state='normal')

                self.entryOper.focus_set()

	def onEditButtonClick( self, loaderControl, m1Control, m2Control ):
		self._arrivalTime = [None] * self._barcodeLen

                loaderControl.Disable()
		m1Control.Disable()
		m2Control.Disable()

		self.entryOper.configure(state='normal')
		self.entryAccession.configure(state='normal')
		self.entryAccessionConf.configure(state='normal')
		self.entrySample.configure(state='normal')
		self.entrySampleConf.configure(state='normal')

                self.entryOper.focus_set()

	def onSaveButtonClick( self, loaderControl, m1Control, m2Control ):
		operatorStr = self._operVar.get()

		accessionStr = self._accessionVar.get()
		accessionConfStr = self._accessionConfVar.get()

		sampleStr = self._sampleVar.get()
		sampleConfStr = self._sampleConfVar.get()
		
		if(( operatorStr == "" )
		or ( accessionStr == "" ) or ( accessionStr != accessionConfStr )
		or ( sampleStr == "" ) or ( sampleStr != sampleConfStr )):
			loaderControl.Disable()
			m1Control.Disable()
			m2Control.Disable()
			return

		self.LogSessionInfo( operatorStr, sampleStr, accessionStr )

               	loaderControl.Enable()
		m1Control.Enable()
		m2Control.Enable()

		self.entryOper.configure(state='disable')
		self.entryAccession.configure(state='disable')
		self.entryAccessionConf.configure(state='disable')
		self.entrySample.configure(state='disable')
		self.entrySampleConf.configure(state='disable')

	def Disable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='disable')

	def Enable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='normal')

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

		self._lfrm = LabelFrame( root, text=self._frameText, padx=10, pady=10, borderwidth=0 )

		btnJogFwdStart = Button( self._lfrm, text='Jog fwd start', height=2, width=18, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["forward"]["jogstart"] ))

		btnJogFwdStop = Button( self._lfrm, text='Jog fwd stop', height=2, width=18, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["forward"]["jogstop"] ))

		btnJogRvsStart = Button( self._lfrm, text='Jog rvs start', height=2, width=18, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["reverse"]["jogstart"] ))

		btnJogRvsStop = Button( self._lfrm, text='Jog rvs stop', height=2, width=18, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["reverse"]["jogstop"] ))

		self._lfrm.grid( row=self._motorNo, column=0, sticky='nw' )

		btnJogFwdStart.grid( row=0, column=0 )
		btnJogFwdStop.grid ( row=0, column=1 )

		btnJogRvsStart.grid( row=1, column=0 )
		btnJogRvsStop.grid ( row=1, column=1 )

	def Disable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='disable')

	def Enable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='normal')

class TraceControl( object ):
	def __init__( self, root ):
		lfrm = LabelFrame( root, text='Trace', padx=10, pady=10, borderwidth=0 )
		self._textwidget = Text( lfrm, borderwidth=1 )
		self._textwidget.config( state='disabled' )

		sbTrace = Scrollbar( lfrm )
		self._textwidget.config( yscrollcommand=sbTrace.set )
		sbTrace.config( command=self._textwidget.yview )

		btnClear = Button( lfrm, text='Clear', height=2, width=18, command=lambda: self.onClearButtonClick( ))

		lfrm.grid( row=1, column=1, rowspan=3, sticky='nsew' )
		lfrm.grid_rowconfigure( 0, weight=1 )
		lfrm.grid_columnconfigure( 0, weight=1 )

		self._textwidget.grid( row=0, column=0, sticky='nsew' )
		sbTrace.grid( row=0, column=1, sticky='nse' )

		btnClear.grid( row=1, column=0, sticky='sw' )

	def onClearButtonClick( self ):
		self._textwidget.config( state='normal' )
		self._textwidget.delete( '1.0', END )
		self._textwidget.config( state='disabled' )

def BuildUI( tkRoot, arduinoCmds, logFileName, debug ):
	frm = Frame( tkRoot, padx=10, pady=10 )

	arduinoLink = ArduinoLink( frm, arduinoCmds, logFileName, debug )

	loaderControl = LoaderControl( frm, arduinoCmds, arduinoLink )
	loaderControl.Disable()

	m1Control = MotorControl( frm, arduinoCmds, arduinoLink, 1 )
	m1Control.Disable()

	m2Control = MotorControl( frm, arduinoCmds, arduinoLink, 2 )
	m2Control.Disable()

	loginControl = LoginControl( frm, loaderControl, m1Control, m2Control, logFileName, int( arduinoCmds["barcodeLen"] ))
	appControl   = AppControl( frm, arduinoCmds, arduinoLink )

	frm.grid( row=0, column=0, sticky=W )

	arduinoLink.InitializeUiStateControl( loaderControl, m1Control, m2Control )
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

class RunTimeConfig( object ):
	def __init__( self ):
	
		parser = OptionParser()
		parser.add_option( '-l', '--logfile', dest='logfilename', action='store', default='psd.log', help='log file' )
		parser.add_option( '-d', '--debug', dest='debug', action='store_true', default=False, help='debug mode' )
		(options, args) = parser.parse_args()

		self._logfilename = options.logfilename
		self._debug = options.debug

	def LogFileName( self ):
		return self._logfilename

	def Debug( self ):
		return self._debug

config = RunTimeConfig()
root = BuildUI( Tk( ), LoadArduinoCommands(), config.LogFileName(), config.Debug() )
root.mainloop()

