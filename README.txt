
installing the sample loader script:
	ubuntu:
		sudo apt-get install pyserial tkinter tk-devel
	centos:
		sudo yum install pyserial tkinter tk-devel

running the sample loader script:
	./loader.py --debug  # when you just want to work with the UI
	./loader.py          # when you want to actually interact with the arduino
