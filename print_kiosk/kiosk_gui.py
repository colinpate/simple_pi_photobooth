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
        cols: 1
        default_size: None, 400
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
'''
)

class SelectableImage(RecycleDataViewBehavior, AsyncImage):
    ''' Add selection support to the Image '''
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)
    source = StringProperty()
    color_photo_path = StringProperty()
    gray_photo_path = StringProperty()
    touch_start_pos = [0, 0]
    #popup_is_open = False

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        self.parent_gallery = rv
        return super(SelectableImage, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if self.collide_point(*touch.pos) and self.selectable:
            self.touch_start_pos = touch.pos
            
    def on_touch_up(self, touch): 
        if self.collide_point(*touch.pos) and self.selectable:
            distance = ((touch.pos[0] - self.touch_start_pos[0]) ** 2 + 
                        (touch.pos[1] - self.touch_start_pos[1]) ** 2) ** 0.5
            if distance < dp(10):
                self.show_image_popup(self.source)
                
    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            print("selection changed to {0}".format(rv.data[index]))
        else:
            print("selection removed for {0}".format(rv.data[index]))
            
    def show_image_popup(self, source):
        ''' Show a popup with the expanded image '''
        layout = FloatLayout()
        popup = Popup(title='Expanded Image View',
                      content=layout,
                      size_hint=(1, 0.6))
        
        color_source = self.color_photo_path
        gray_source = self.gray_photo_path
        print("Color source:", color_source, "Gray source:", gray_source)
        
        image = AsyncImage(source=color_source, allow_stretch=True, size_hint=(1, 1), pos_hint={'x': 0, 'y': 0.1})
        layout.add_widget(image)
        
        # Define the close button
        close_button = Button(text='Close', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.6, 'y': 0})
                              
        def close_popup(instance):
            popup.dismiss()
                              
        close_button.bind(on_release=close_popup)
        layout.add_widget(close_button)
        
        # Define the toggle button and its callback
        toggle_button = ToggleButton(text='Black & White', size_hint=(0.2, 0.1),
                                     pos_hint={'x': 0.4, 'y': 0})
        layout.add_widget(toggle_button)

        # Default to color
        self.print_source = color_source
        
        def on_toggle(instance):
            print(instance.state)
            if instance.state == 'down':
                instance.text = 'Color'
                image.source = gray_source
                self.print_source = gray_source
            else:
                instance.text = 'Black & White'
                image.source = color_source
                self.print_source = color_source
            print(image.source)
            image.reload()
        
        toggle_button.bind(on_press=on_toggle)
        
        # Define the print button and its callback
        print_button = Button(text='Print', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.3, 'y': 0})
        layout.add_widget(print_button)
        
        def on_print(instance):
            close_popup(instance)
            Clock.schedule_once(self.show_confirm_print_popup, 0)
        
        print_button.bind(on_release=on_print)
        
        popup.open()

    def show_confirm_print_popup(self, instance):
        layout = FloatLayout()
        popup = Popup(title='Confirm print?',
                      content=layout,
                      size_hint=(0.5, 0.3))
                      
        yes_button = Button(text='Yes', size_hint=(0.5, 1),
                              pos_hint={'x': 0, 'y': 0})
            
        def close_popup(instance):
            popup.dismiss()
                              
        def print_image(instance):
            print("Printing", self.print_source)
            close_popup(instance)
            self.print_image()
            Clock.schedule_once(self.show_printing_popup, 0)
                              
        yes_button.bind(on_release=print_image)
        layout.add_widget(yes_button)
                      
        no_button = Button(text='No', size_hint=(0.5, 1),
                              pos_hint={'x': 0.5, 'y': 0})
        no_button.bind(on_release=close_popup)
        layout.add_widget(no_button)
        
        popup.open()

    def show_printing_popup(self, instance):
        layout = FloatLayout()
        popup = Popup(title='Printing!',
            content=layout,
            size_hint=(0.8, 0.8))
        
        Clock.schedule_once(popup.dismiss, 10)
        
        popup.open()
        
    def print_image(self):
        self.parent_gallery.print_image(self.print_source)
        

class ImageGallery(RecycleView):
    def __init__(self, **kwargs):
        super(ImageGallery, self).__init__(**kwargs)
        
        if LOCAL_TEST:
            config = load_config("print_config_test.yaml")
        else:
            config = load_config("print_config.yaml")
        
        self.thumbnail_path_db = ImagePathDB(config["thumbnail_path_db"])
        self.photo_path_db = ImagePathDB(config["photo_path_db"], old_root="/home/colin/booth_photos" if LOCAL_TEST else None)
        self.thumbnail_dir = config["thumbnail_dir"]
        self.photo_dir = config["photo_dir"]
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
        if is_nfs_mounted(self.photo_dir) or LOCAL_TEST:
            if self.not_available_popup is not None:
                self.not_available_popup.dismiss()
                self.not_available_popup = None
            # Check to see if there are any new thumbnails in the Thumbnail DB and add them to self.data if so
            self.photo_path_db.try_update_from_file()
            new_photo_names = list(self.photo_path_db.image_names())
            new_num_photos = len(new_photo_names)
            print("Updating data,", new_num_photos, "photos in database")
            if new_num_photos != len(self.data):
                print(new_num_photos - len(self.data), "new photos!")
                photo_names_sorted = sorted(new_photo_names)[::-1]
                new_data = []
                for photo_name in photo_names_sorted:
                    thumbnail_path = self.get_thumbnail(photo_name)
                    if thumbnail_path is not None:
                        new_data.append({
                                'source': thumbnail_path,
                                'gray_photo_path': self.photo_path_db.get_image_path(photo_name, "_gray"),
                                'color_photo_path': self.photo_path_db.get_image_path(photo_name, "_color"),
                            })
                self.data = new_data
                self.thumbnail_path_db.update_file()
        else:
            if self.not_available_popup is None:
                Clock.schedule_once(self.show_not_available_popup, 0)
        Clock.schedule_once(self.update_data, 2)
            
    def get_thumbnail(self, thumbnail_name):
        # Returns path to thumbnail if it exists, creates it if not
        if self.thumbnail_path_db.image_exists(thumbnail_name):
            return self.thumbnail_path_db.get_image_path(thumbnail_name)
        else:
            thumbnail_path = os.path.join(self.thumbnail_dir, thumbnail_name + ".png")
            if not os.path.isfile(thumbnail_path):
                print("Creating thumbnail for", thumbnail_name)
                success = create_thumbnail(
                    photo_path=self.photo_path_db.get_image_path(thumbnail_name, postfix="_color"),
                    thumbnail_path=thumbnail_path,
                    size_x=520,
                    size_y=390
                    )
                if not success:
                    print("Failed to create thumbnail")
                    return None
            self.thumbnail_path_db.add_image(thumbnail_name, thumbnail_path)
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
