import kivy
from kivy.app import App
from kivy.uix.image import AsyncImage
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.recyclegridlayout import RecycleGridLayout
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import BooleanProperty, StringProperty
from kivy.metrics import dp  # Import dp function
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.config import Config

from glob import glob
import yaml
import cv2
import os
import subprocess
from selectable_image import SelectableImage

if os.path.isfile("print_config_test.yaml"):
    LOCAL_TEST = True
else:
    LOCAL_TEST = False

if not LOCAL_TEST:
    import cups
    Config.set('graphics', 'fullscreen', 'auto')
    Config.set('input', 'mouse', 'None')
    Config.set('graphics', 'rotation', '270')

from common.image_path_db import ImagePathDB

def is_nfs_mounted(mount_point):
    if os.path.ismount(mount_point):
        try:
            # Check if the mount point is available by listing its contents
            subprocess.check_output(['ls', mount_point], timeout=5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
            print(exception)
            return False
    else:
        print("Not mounted!")
        return False

def load_config(config_path):
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config
    
def create_thumbnail(photo_path, thumbnail_path, size_x, size_y):
    image = cv2.imread(photo_path)
    if image is not None:
        out = cv2.resize(image, dsize=(size_x, size_y))
        cv2.imwrite(thumbnail_path, out)
        return True
    else:
        return False

def rotate_image(image_path):
    image = cv2.imread(image_path)
    image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    file_path = "rotated.jpg"
    cv2.imwrite(file_path, image)
    return file_path
    
Builder.load_string(
'''
<ImageGallery>:
    viewclass: 'SelectableImage'
    RecycleGridLayout:
        cols: 2
        default_size: None, 300
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
'''
)
        

class ImageGallery(RecycleView):
    def __init__(self, **kwargs):
        super(ImageGallery, self).__init__(**kwargs)
        
        if LOCAL_TEST:
            config = load_config("print_config_test.yaml")
        else:
            config = load_config("print_config.yaml")
        
        #self.thumbnail_path_db = ImagePathDB(config["thumbnail_path_db"])
        self.photo_path_db = ImagePathDB(config["photo_path_db"], old_root="/home/colin/booth_photos" if LOCAL_TEST else None)
        self.thumbnail_dir = config["thumbnail_dir"]
        self.photo_dir = config["photo_dir"]
        self.remote_photo_dir = config["remote_photo_dir"]
        self.separate_gray_thumbnails = False
        
        self.old_num_photos = 0
        self.not_available_popup = None
        self.data = []
        Clock.schedule_once(self.update_data, 5)

        if not LOCAL_TEST:
            self.setup_printer()

    def setup_printer(self):
        self.conn = cups.Connection()
        printers = self.conn.getPrinters()
        self.printer_name = list(printers.keys())[0]  # Assuming the first printer is your target printer

    def print_image(self, image_path):
        rotated_path = rotate_image(image_path)
        options={}
        self.conn.printFile(self.printer_name, rotated_path, "Photo Print", options)
        
    def fill_image_path_db(self, color_dir):
        color_images = glob(color_dir + "/*.jpg")
        for color_image in color_images:
            filename = os.path.split(color_image)[-1]
            image_name = filename.split("_color")[0]
            paths = {}
            for dirname in ["color", "gray", "original"]:
                postfix = "_" + dirname
                image_filename = filename.replace("_color", postfix)
                image_dir = color_dir[:-6] + dirname
                image_path = os.path.join(image_dir, image_filename)
                paths[postfix] = image_path
            print(image_name, paths)
            self.photo_path_db.add_image(image_name, paths)

    def show_not_available_popup(self, instance):
        layout = FloatLayout()
        popup = Popup(title='Error',
                      content=layout,
                      size_hint=(0.5, 0.3))
        
        popup.open()
        
        self.not_available_popup = popup
                
    def update_data(self, dt):
        if is_nfs_mounted(self.remote_photo_dir) or LOCAL_TEST:
            if self.not_available_popup is not None:
                self.not_available_popup.dismiss()
                self.not_available_popup = None
            if not LOCAL_TEST:
                print("Syncing remote to local")
                print(os.system(f"rsync -a {self.remote_photo_dir} {self.photo_dir}"))
            # Check to see if there are any new thumbnails in the Thumbnail DB and add them to self.data if so
            self.photo_path_db.try_update_from_file()
            new_photo_names = list(self.photo_path_db.image_names())
            new_num_photos = len(new_photo_names)
            print("Updating data,", new_num_photos, "photos in database")
            if new_num_photos != self.old_num_photos:
                self.old_num_photos = new_num_photos
                print(new_num_photos - self.old_num_photos, "new photos!")
                photo_names_sorted = sorted(new_photo_names)[::-1]
                new_data = []
                for photo_name in photo_names_sorted:
                    if self.separate_gray_thumbnails:
                        thumbnail_images = [
                                {"gray_photo_path": self.photo_path_db.get_image_path(photo_name, "_gray"), "color_photo_path": ""},
                                {"color_photo_path": self.photo_path_db.get_image_path(photo_name, "_color"), "gray_photo_path": ""}
                            ]
                    else:
                        thumbnail_images = [
                                {
                                    "color_photo_path": self.photo_path_db.get_image_path(photo_name, "_color"),
                                    "gray_photo_path": self.photo_path_db.get_image_path(photo_name, "_gray")
                                }
                            ]
                        
                    for photo_dict in thumbnail_images:
                        if photo_dict["color_photo_path"]:
                            thumb_photo_path = photo_dict["color_photo_path"]
                        else:
                            thumb_photo_path = photo_dict["gray_photo_path"]
                        thumbnail_path = self.get_thumbnail(thumb_photo_path)
                        if thumbnail_path is not None:
                            new_entry = {
                                    'source': thumbnail_path,
                                }
                            new_entry.update(photo_dict)
                            new_data.append(new_entry)
                            
                self.data = new_data
                #self.thumbnail_path_db.update_file()
        else:
            if self.not_available_popup is None:
                Clock.schedule_once(self.show_not_available_popup, 0)
        Clock.schedule_once(self.update_data, 2)
            
    def get_thumbnail(self, image_path):
        # Returns path to thumbnail if it exists, creates it if not
        #if self.thumbnail_path_db.image_exists(image_path):
        #    return self.thumbnail_path_db.get_image_path(image_path)
        #else:
        filename = os.path.split(image_path)[1]
        filename = filename.split(".")[0]
        thumbnail_path = os.path.join(self.thumbnail_dir, filename + ".png")
        if not os.path.isfile(thumbnail_path):
            print("Creating thumbnail for", filename)
            success = create_thumbnail(
                photo_path=image_path,
                thumbnail_path=thumbnail_path,
                size_x=520,
                size_y=390
                )
            if not success:
                print("Failed to create thumbnail")
                return None
        #self.thumbnail_path_db.add_image(thumbnail_name, thumbnail_path)
        return thumbnail_path

class ImageGalleryApp(App):
    def build(self):
        root = FloatLayout()
        gallery = ImageGallery()
        gallery.scroll_type = ['content', 'bars']
        gallery.bar_width = '50dp'
        print("ImageGallery instance created and configured.")
        root.add_widget(gallery)
        settings_button = Button(text='Settings', size_hint=(None, None), size=(100, 50),
                                 pos_hint={'right': 1, 'top': 1})
        root.add_widget(settings_button)
        return root

if __name__ == '__main__':
    ImageGalleryApp().run()
