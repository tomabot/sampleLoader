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

class AppControl( object ):
	def __init__( self, root, arduinoCmds, arduinoLink ):
		self._arduinoCmds = arduinoCmds
		self._arduinoLink = arduinoLink

		lfrm = LabelFrame( root, padx=10, pady=10, borderwidth=0 )
		btnStop  = Button( lfrm, text='Stop', height=2, width=16, command=lambda: self.onStopButtonClick( ))
		btnExit  = Button( lfrm, text='Exit', height=2, width=16, command=exit )

		lfrm.grid( row=3, column=0, sticky=SW )
		btnExit.grid ( row=0, column=0 )
		btnStop.grid ( row=0, column=1 )

	def onStopButtonClick( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["stop"] )

# ArduinoLink encapsulates the serial port connection and the 
# trace control.
class ArduinoLink( object ):
	def __init__( self, root, arduinoCmds, debug ): 
		self._root = root
		self._debug = debug
		self._conn = None

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
		# see if the arduino has written anything to the serial port
		if( self._debug == False ):
			bytesToRead = self._conn.inWaiting()
			if bytesToRead > 0:
				# enable writing to the textwidget
				self._trace._textwidget.config( state='normal' )

				# write the message received from the arduino to the textwidget
				self._trace._textwidget.insert( END, '<<<' + self._conn.read( bytesToRead ) + '\n' )

				# write a newline to end the message
				#self._trace._textwidget.insert( END, '\n' )

				# scroll the textwidget to the end so you can see it
				self._trace._textwidget.see( END )

				# disable the text widget so it's read-only
				self._trace._textwidget.config( state='disabled' )

		# reset the idle event timer
		self._root.after( 100, self.Tick )

	def Send( self, cmd ):
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
		btnFindNeedle = Button( self._lfrm, text='Find Needle', height=2, width=16, 
			command=lambda: self.onFindNeedleButtonClick( ))
		btnStatus = Button( self._lfrm, text='Status', height=2, width=16, 
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

		self._cbox = ttk.Combobox( self._lfrm, textvariable=self._box_value, width=13 )
		self._cbox['values'] = profTuples
		self._cbox.current(0)
		self._cbox.state(['readonly'])

		btnLoad = Button( self._lfrm, text='Load', height=2, width=16, command=lambda: self.btnLoad_click( ))
		btnGo = Button( self._lfrm, text='Go', height=2, width=16, command=lambda: self.btnGo_click( ))

		self._lfrm.grid   ( row=0, column=0, sticky='nw' )
		btnFindNeedle.grid( row=0, column=0 )
		btnStatus.grid    ( row=0, column=1 )
		self._cbox.grid   ( row=1, column=0 )
		btnLoad.grid      ( row=1, column=1 )
		btnGo.grid        ( row=2, column=1 )

	def onFindNeedleButtonClick( self ):
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

	def onStatusButtonClick( self ):
		self._arduinoLink.Send( self._arduinoCmds["loadcmds"]["status"] )

	def Disable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='disable')

	def Enable( self ):
		for child in self._lfrm.winfo_children():
			child.configure(state='normal')

class LoginControl( object ):
        def __init__( self, root, loaderControl, m1Control, m2Control, barcodeLen ):
                lfrm = LabelFrame( root, text='Log Control', padx=10, pady=10, borderwidth=0 )

		self._operVar = StringVar()
		
                lfrmOper = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                labelOper = Label( lfrmOper, text="     operator:" )
                self.entryOper = Entry( lfrmOper, textvariable=self._operVar, font=( 'Calibri', 14 ))

		self._accessionVar = StringVar()
		self._accessionVar.trace( 'w', self._HandleAccession )
		self._accessionConfVar = StringVar()
		self._accessionConfVar.trace( 'w', self._HandleAccessionConf )

                #lfrmAcc = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                lfrmAcc = LabelFrame( lfrm, padx=10, pady=8, borderwidth=0 ) 
                labelAccession      = Label( lfrmAcc, text="accession id:" )
                self.entryAccession = Entry( lfrmAcc, width="14", textvariable=self._accessionVar, font=( 'Calibri', 14 ))

                labelAccessionConf      = Label( lfrmAcc, text="     confirm:" )
                self.entryAccessionConf = Entry( lfrmAcc, width="14", textvariable=self._accessionConfVar, font=( 'Calibri', 14 ))

		self._sampleVar = StringVar()
		self._sampleVar.trace( 'w', self._HandleSample )
		self._sampleConfVar = StringVar()
		self._sampleConfVar.trace( 'w', self._HandleSampleConf )

                #lfrmSampleId = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                lfrmSampleId = LabelFrame( lfrm, padx=10, pady=8, borderwidth=0 ) 
                labelSampleId = Label( lfrmSampleId, text="sample id:" )
                self.entrySample = Entry( lfrmSampleId, width="14", textvariable=self._sampleVar, font=( 'Calibri', 14 ))
                labelSampleConf = Label( lfrmSampleId, text="  confirm:" )
                self.entrySampleConf = Entry( lfrmSampleId, width="14", textvariable=self._sampleConfVar, font=( 'Calibri', 14 ))

                lfrmBtn = LabelFrame( lfrm, padx=10, pady=10, borderwidth=0 ) 
                btnOK = Button( lfrmBtn, text="OK", height=2, width=16, 
			command=lambda: self.onOkButtonClick( loaderControl, m1Control, m2Control ))
		btnClr = Button( lfrmBtn, text="Clear", height=2, width=16, 
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

                btnOK.grid ( row=0, column=0 )
                btnClr.grid( row=0, column=1 )

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

	def onOkButtonClick( self, loaderControl, m1Control, m2Control ):
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

	def LogSessionInfo( self, operatorStr, sampleStr, accessionStr ):
		####################################################
		#
		# this is where the operator name, sample
		# id, and accession id should be logged
		#
		####################################################
		pass

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

                self.entryOper.focus_set()

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

		btnJogFwdStart = Button( self._lfrm, text='Jog fwd start', height=2, width=16, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["forward"]["jogstart"] ))

		btnJogFwdStop = Button( self._lfrm, text='Jog fwd stop', height=2, width=16, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["forward"]["jogstop"] ))

		btnJogRvsStart = Button( self._lfrm, text='Jog rvs start', height=2, width=16, 
			command=lambda: self._arduinoLink.Send( self._arduinoCmds[self._motorName]["reverse"]["jogstart"] ))

		btnJogRvsStop = Button( self._lfrm, text='Jog rvs stop', height=2, width=16, 
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

		btnClear = Button( lfrm, text='Clear', height=2, width=16, command=lambda: self.onClearButtonClick( ))

		lfrm.grid( row=1, column=1, rowspan=3, sticky='nsew' )
		lfrm.grid_rowconfigure( 0, weight=1 )
		lfrm.grid_columnconfigure( 0, weight=1 )

		self._textwidget.grid( row=0, column=0, sticky='nsw' )
		sbTrace.grid( row=0, column=1, sticky='nse' )

		btnClear.grid( row=1, column=0, sticky='sw' )

	def onClearButtonClick( self ):
		self._textwidget.config( state='normal' )
		self._textwidget.delete( '1.0', END )
		self._textwidget.config( state='disabled' )

def BuildUI( tkRoot, arduinoCmds, debug ):
	frm = Frame( tkRoot, padx=10, pady=10 )

	arduinoLink = ArduinoLink( frm, arduinoCmds, debug )

	loaderControl = LoaderControl( frm, arduinoCmds, arduinoLink )
	loaderControl.Disable()

	m1Control = MotorControl( frm, arduinoCmds, arduinoLink, 1 )
	m1Control.Disable()

	m2Control = MotorControl( frm, arduinoCmds, arduinoLink, 2 )
	m2Control.Disable()

	loginControl = LoginControl( frm, loaderControl, m1Control, m2Control, int( arduinoCmds["barcodeLen"] ))
	appControl   = AppControl( frm, arduinoCmds, arduinoLink )

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

