import pyautogui
import keyboard
import time
import pyperclip
from pathlib import Path

fill_console = True
cli_coordinate = [1001, 1090]
last_line_coordinate = [634, 1010, 1049, 1010]#994
device_details = ""
upload_file_name = "IMG_0559"
temp_directory = "./Images"
old_images_directory = "./Old_Images"
upload_location = "A/DCIM/149___01"
message = "HI"
uploading = False
model = "Canon PowerShot A800"
cameraTime = ""

def activate_camera_code():
    pyautogui.typewrite("rec")
    time.sleep(0.1)
    pyautogui.press('enter')
    time.sleep(3)

    #pyautogui.typewrite("lua dofile(\"A/CHDK/SCRIPTS/SavePhoto.lua\")")
    #time.sleep(0.1)
    #pyautogui.press('enter')
    #time.sleep(0.1)
    
# fill the console to push ouputs to the bottom of the screen
def fill_the_console():
    global fill_console
    
    if fill_console == True:
        activate_camera_code()
        
        pyautogui.typewrite("help")
        time.sleep(0.1)
        pyautogui.press('enter')
        fill_console = False
        time.sleep(0.1)

def run_getm():
    pyautogui.typewrite("getm")
    #time.sleep(0.1)
    pyautogui.press('enter')
    #time.sleep(0.5)
    time.sleep(0.1)

def get_edited_image():
    for p in Path(temp_directory).rglob('*'):
        if p.is_file():
            file_name = p.name
            print(file_name)
            
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
    time.sleep(0.1)
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
    pyautogui.moveTo(last_line_coordinate[0], last_line_coordinate[1], 0)
    pyautogui.dragRel(400, 0, 0.1)
    pyautogui.hotkey("ctrlleft", "c")
    cameraTime = pyperclip.paste()
    print(cameraTime)

    time.sleep(0.1)
    pyautogui.click(cli_coordinate[0], cli_coordinate[1])
    pyautogui.typewrite("rs Images/ -jpg")
    pyautogui.press('enter')
    
    time.sleep(6)
    print("uploading")
    get_edited_image()
    

# get result of getm from bottom line of the console
def get_getm_output():
    
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
    #time.sleep(0.1)
    pyautogui.hotkey("ctrlleft", "end")
    time.sleep(0.1)
    pyautogui.click(last_line_coordinate[0], last_line_coordinate[1])
    #time.sleep(0.1)
    pyautogui.moveTo(last_line_coordinate[0], last_line_coordinate[1], 0)
    #time.sleep(0.1)
    pyautogui.dragRel(400, 0, 0.1)
    #time.sleep(0.1)
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

    global uploading
    while True:

        if keyboard.is_pressed('q'):
            print("Quitting")
            break
        #if keyboard.is_pressed("u") and uploading == False:
        #    uploading = True
        #    upload_image()
            
            

        current_pos = pyautogui.position() 
        print(f"Current position: X={current_pos.x}, Y={current_pos.y}")
        if uploading == False:
            get_message_from_camera()
                

if __name__ == "__main__":
    main()



"""
Need to speed up getting command from command line stuff
Need to change it to save photo in Images directory in the folder
Need it to read from that fodler, get the new image, and call a function
Function just prints something and waits 1 second
Need it to upload iamge to camera
Then move the image into old images directory
then start checking again
"""
