# elec-490-team-36
To run the digital camera code you need:
- chdkptp.py
- embed_new.py (underscore not -)
- a directory called: Images
- a directory called: Old_Images
- batch file called autostart

All of the above need to be in the chdkptp-r964 folder where chdkptp.exe is stored

To run the code:
- Run the autostart batch file

How it works:
When the camera detects a shutter press it sends a message to the computer.
When the computer detects the message it runs a command that causes the camera to take a photot that only saves to the computer. IT is intially stored in the Images folder.
The program then takes that photo and applies a watermark to it and overwrites the original. 
The program then uploads the modified image onto the camera and then moves it into the Old_Images folder.

