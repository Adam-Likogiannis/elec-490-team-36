import pyautogui
import keyboard
import time
import pyperclip
from pathlib import Path
import modify_image
import embed_new

fill_console = True
#cli_coordinate = [1001, 1090]
#last_line_coordinate = [634, 1015, 1049, 1015]#994

# FOR ADAM
# This is the cooridnate on the screen where the mouse needs to be to
# click the command line interface
cli_coordinate = [18, 1400]
# This is the cooridnate on the screen where the mouse needs to be to
# click the most recent output in the terminal.
# Both of these cooridantes were taken when the program is full screened. Done for consitency.
last_line_coordinate = [20, 1338]

device_details = ""
upload_file_name = "IMG_0559"
temp_directory = "./Images"
old_images_directory = "./Old_Images"
upload_location = "A/DCIM/149___01"
message = "HI"
uploading = False
model = "Canon PowerShot A800"
cameraTime = ""
turn_RED = False

# full screens chdkptp and sets the camera to record mode.
def activate_camera_code():
    pyautogui.click(1001, 1090)
    time.sleep(1)
    pyautogui.hotkey("win", "up")
    pyautogui.typewrite("rec")
    time.sleep(0.1)
    pyautogui.press('enter')
    time.sleep(3)
    
    
# fill the console to push ouputs to the bottom of the screen
def fill_the_console():
    global fill_console
    
    if fill_console == True:
        activate_camera_code()
        
        pyautogui.typewrite("help")
        #time.sleep(0.1)
        pyautogui.press('enter')
        time.sleep(0.1)
        pyautogui.typewrite("help")
        #time.sleep(0.1)
        pyautogui.press('enter')
        fill_console = False
        time.sleep(0.1)

# this is the command that gets messages from the camera
def run_getm():
    pyautogui.typewrite("getm")
    #time.sleep(0.1)
    pyautogui.press('enter')
    #time.sleep(0.5)
    time.sleep(0.1)

# runs the watermark code. The step, key, and quailty values were the defualt values
# in the original code
def watermark_image(message, inputpath, outputpath):
    step = 30
    key = ""
    quality = 100
    embed_new.apply_watermark_to_camera_image(message, step, key, inputpath, outputpath, quality)

# decodes the input image. 
def decode_image(inputpath):
    step = 30
    key = ""
    message = embed_new.decode_image(inputpath, step, key) 
    print_message = 'lua print("Image Saved: ' + message + '")'
    #print(print_message)
    #time.sleep(0.1)
    #pyautogui.click(cli_coordinate[0], cli_coordinate[1])
    #pyautogui.typewrite(message)
    #pyautogui.press('enter')

def get_edited_image(cameraTime):
    for p in Path(temp_directory).rglob('*'):
        if p.is_file():
            file_name = p.name
            print(file_name)
            if turn_RED == True:
                t = temp_directory + "/" + file_name
                modify_image.adjust_red_channel(t, 0.1, file_name)
            else:
                message = "Canon PowerShot A800 - " + p.name + " - " + cameraTime
                inputpath = temp_directory + "/" + file_name
                outputpath = inputpath
                #watermark_image(message, inputpath, "./temp/" + file_name)

                watermark_image(message, inputpath, outputpath)
            
            upload_image(file_name)
            
            sp = temp_directory + "/" + file_name
            source_path = Path(sp)
            dp = old_images_directory + "/" + file_name
            destination_path = Path(dp)
            source_path.rename(destination_path)
            

def run_remoteshoot():
    global time
    time.sleep(0.1)
    pyautogui.click(cli_coordinate[0], cli_coordinate[1])
    #time.sleep(0.1)
    pyautogui.typewrite("killscript")
    #time.sleep(0.1)
    pyautogui.press('enter')
    
    

    time.sleep(0.1)
    pyautogui.typewrite("clock")
    pyautogui.press('enter')
    
    time.sleep(0.1)
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
    pyautogui.hotkey("ctrlleft", "end")
    time.sleep(0.3)

    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1], clicks=3,interval=0.1,button="left")

   # pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
   # pyautogui.moveTo(last_line_coordinate[0], last_line_coordinate[1], 0)
   # pyautogui.dragRel(400, 0, 0.1)


    pyautogui.hotkey("ctrlleft", "c")
    cameraTime = pyperclip.paste()
    print(cameraTime)

    time.sleep(0.1)
    pyautogui.click(cli_coordinate[0], cli_coordinate[1])
    pyautogui.typewrite("rs Images/ -jpg")
    pyautogui.press('enter')


    time.sleep(6)

    
    print("uploading")
    get_edited_image(cameraTime)
    

# get result of getm from bottom line of the console
def get_getm_output():
    
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
    #time.sleep(0.1)
    pyautogui.hotkey("ctrlleft", "end")
    time.sleep(0.3)
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1], clicks=3,interval=0.1,button="left")

    """
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
    time.sleep(0.1)
    pyautogui.moveTo(last_line_coordinate[0], last_line_coordinate[1], 0)
    #time.sleep(0.1)
    pyautogui.dragRel(400, 0, 0.1)
    #time.sleep(0.1)
"""
    pyautogui.hotkey("ctrlleft", "c")
    time.sleep(0.1)
    
    output = pyperclip.paste()
    if message in output:
        run_remoteshoot()
    

def upload_image(file_name):
    global uploading
    
    global upload_location
    upload_command = "upload Images/" + file_name + " " + upload_location
    
    #upload Images/IMG_0592 A/DCIM/149___01
    pyautogui.click(cli_coordinate[0], cli_coordinate[1])
    #time.sleep(0.1)
    pyautogui.typewrite(upload_command)
    #time.sleep(0.1)
    pyautogui.press('enter')
    time.sleep(1)
    uploading = False


def get_message_from_camera():
    # click on command line
    print("A")
    #time.sleep(3)
    pyautogui.click(cli_coordinate[0], cli_coordinate[1])
    time.sleep(0.1)

    fill_the_console()

    run_getm()

    get_getm_output()
    


def main():
    #decode_image("./Old_Images/IMG_0611.jpg")
    #return

    global uploading
    while True:

        if keyboard.is_pressed('esc'):
            print("Quitting")
            break

        current_pos = pyautogui.position() 
        print(f"Current position: X={current_pos.x}, Y={current_pos.y}")
        if uploading == False:
            get_message_from_camera()
                

if __name__ == "__main__":
    main()
