import kivy
from kivy.app import App
from kivy.uix.image import AsyncImage, Image
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
from kivy.graphics import Color, Rectangle
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
import numpy as np
from selectable_image import SelectableImage
from collections import OrderedDict

if os.path.isfile("print_config_test.yaml"):
    LOCAL_TEST = True
else:
    LOCAL_TEST = False

if not LOCAL_TEST:
    import cups
    Config.set('graphics', 'fullscreen', 'auto')
    Config.set('input', 'mouse', 'None')
    Config.set('graphics', 'rotation', '270')
else:
    Config.set('graphics', 'width', '600')
    Config.set('graphics', 'height', '1024')

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
        #print("Not mounted!")
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


class PrintFormatter:
    def __init__(self, print_format):
        self.print_format = print_format
        if print_format == "4x3":
            self._num_photos = 2
            self._media = "custom_119.21x156.15mm_119.21x156.15mm"
        elif self.print_format == "2x6":
            self._num_photos = 3
            self._media = "custom_119.21x155.45mm_119.21x155.45mm"
            
    def num_photos(self):
        return self._num_photos
        
    def print_options(self):
        options = {
            "media": self._media
        }
        return options

    def format_print(self, image_paths):
        if self.print_format == "4x3":
            images = []
            for image_path in image_paths:
                image = cv2.imread(image_path)
                images.append(image)
            out_image = cv2.vconcat(images)
            preview_image = cv2.resize(out_image, (400, 600))
            preview_path = "preview.png"
            cv2.imwrite(preview_path, preview_image)
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            file_path = "formatted.jpg"
            cv2.imwrite(file_path, out_image)
        elif self.print_format == "2x6":
            image_width = 600
            image_height = int(image_width * 3/4)
            canvas_width = image_width
            canvas_height = image_width * 3
            y_padding = int((image_width - image_height) / 2)
            canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
            y = 0
            for (i, image_path) in enumerate(image_paths):
                image = cv2.imread(image_path)
                resized = cv2.resize(image, (image_width, image_height))
                canvas[y + y_padding : y + y_padding + image_height, :, :] = resized
                y += image_width
            preview_path = "preview.png"
            cv2.imwrite(preview_path, canvas)
            out_image = cv2.hconcat([canvas, canvas])
            out_image = cv2.rotate(out_image, cv2.ROTATE_90_CLOCKWISE)
            file_path = "formatted.jpg"
            cv2.imwrite(file_path, out_image)
        return file_path, preview_path
    
    
Builder.load_string(
'''
<Label>:
    font_size: sp(20)
<ImageGallery>:
    viewclass: 'SelectableImage'
    RecycleGridLayout:
        cols: 2
        default_size: None, 212
        default_size_hint: 1, None
        size_hint_y: None
        spacing: 10
        padding: 10
        height: self.minimum_height
'''
#        multiselect: True
#        touch_multiselect: True
)


class ColoredLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self.update_rect, pos=self.update_rect)
        with self.canvas.before:
            Color(1, 1, 1, 0.5)  # Set the color (R, G, B, A)
            self.rect = Rectangle(size=self.size, pos=self.pos)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
    
    
#class SelectableRecycleGridLayout(FocusBehavior, LayoutSelectionBehavior,
#                                 RecycleGridLayout):
#    ''' Adds selection and focus behavior to the view. '''
        

class ImageGallery(RecycleView):
    def __init__(self, status_label, **kwargs):
        super(ImageGallery, self).__init__(**kwargs)
        #print(vars(self))
        #print(self.layout_manager.clear_selection)
        
        if LOCAL_TEST:
            config = load_config("print_config_test.yaml")
        else:
            config = load_config("print_config.yaml")
        
        #self.thumbnail_path_db = ImagePathDB(config["thumbnail_path_db"])
        self.photo_path_db = ImagePathDB(config["photo_path_db"], old_root="/home/colin/booth_photos" if LOCAL_TEST else None)
        
        self.thumbnail_dir = config["thumbnail_dir"]
        self.photo_dir = config["photo_dir"]
        self.remote_photo_dir = config["remote_photo_dir"]
        self.separate_gray_thumbnails = config["separate_gray_thumbnails"]
        self.print_formatter = PrintFormatter(config["print_format"])
        if "fill_dir" in config.keys():
            self.fill_image_path_db(config["fill_dir"])
        self.status_label = status_label
        
        self.old_num_photos = 0
        self.not_available_popup = None
        self.data = []
        self.print_selections = []
        Clock.schedule_once(self.update_data, 5)

        if not LOCAL_TEST:
            self.setup_printer()

    def setup_printer(self):
        self.conn = cups.Connection()
        printers = self.conn.getPrinters()
        self.printer_name = list(printers.keys())[0]  # Assuming the first printer is your target printer
        
    def clear_selection(self):
        # Update the data model
        for item in self.data:
            item['selected'] = False
        # Refresh the data to ensure the view is updated
        self.refresh_from_data()
        
    def prepare_print(self, instance):
        formatted_path, preview_path = self.print_formatter.format_print(self.print_selections)
        print("Showing preview popup")
        self.show_print_preview_popup(formatted_path, preview_path)
        self.clear_selection()

    def update_status_label(self):
        num_selected = len(self.print_selections)
        need = self.print_formatter.num_photos()
        rem = need - num_selected
        if rem == 0:
            text = "Processing..."
        elif rem == 1:
            text = "Select 1 image"
        else:
            text = f"Select {rem} images"
        self.status_label.text = text
                    
    def add_print_selection(self, image_path):
        if image_path not in self.print_selections:
            self.print_selections.append(image_path)
            self.update_status_label()
            if len(self.print_selections) == self.print_formatter.num_photos():
                Clock.schedule_once(self.prepare_print, 0)
        
    def remove_print_selection(self, image_path):
        if image_path in self.print_selections:
            self.print_selections.remove(image_path)
            self.update_status_label()
            
    def show_print_preview_popup(self, formatted_path, preview_path):
        ''' Show a popup with the expanded image '''
        layout = FloatLayout()
        popup = Popup(title='Print Preview',
                      content=layout,
                      size_hint=(0.8, 0.9))
        image = AsyncImage(source=os.path.abspath(preview_path), allow_stretch=True, size_hint=(1, 0.8), pos_hint={'x': 0, 'y': 0.15})
        image.reload()
        layout.add_widget(image)
        
        # Define the close button
        close_button = Button(text='Cancel', size_hint=(0.3, 0.1),
                              pos_hint={'x': 0.6, 'y': 0})
                              
        close_button.bind(on_release=popup.dismiss)
        layout.add_widget(close_button)
        
        # Define the print button and its callback
        print_button = Button(text='Print!', size_hint=(0.3, 0.1),
                              pos_hint={'x': 0.1, 'y': 0})
        layout.add_widget(print_button)
        
        def on_print(instance):
            popup.dismiss()
            self.print_images(formatted_path)
            
        print_button.bind(on_release=on_print)
            
        popup.open()
        
    def print_images(self, formatted_path):
        print("Printing", formatted_path)
        if not LOCAL_TEST:
            options=self.print_formatter.options()
            self.conn.printFile(self.printer_name, formatted_path, "Photo Print", options)
        
    def fill_image_path_db(self, color_dir):
        color_images = glob(color_dir + "/*.jpg")
        for color_image in color_images:
            filename = os.path.split(color_image)[-1]
            image_name = filename.split("_color")[0]
            paths = {}
            for dirname in ["color", "gray", "original"]:
                postfix = "_" + dirname
                image_filename = filename.replace("_color", postfix)
                image_dir = color_dir.replace("color", "") + dirname
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
            #print("Updating data,", new_num_photos, "photos in database")
            if new_num_photos != self.old_num_photos:
                self.old_num_photos = new_num_photos
                print(new_num_photos - self.old_num_photos, "new photos!")
                photo_names_sorted = sorted(new_photo_names)[::-1]
                new_data = []
                for photo_name in photo_names_sorted:
                    gray_path = self.photo_path_db.get_image_path(photo_name, "_gray")
                    color_path = self.photo_path_db.get_image_path(photo_name, "_color")
                    if self.separate_gray_thumbnails:
                        thumbnail_images = [
                                {"print_source": gray_path, "gray_photo_path": "", "color_photo_path": ""},
                                {"print_source": color_path, "gray_photo_path": "", "color_photo_path": ""}
                            ]
                    else:
                        thumbnail_images = [
                                {
                                    "color_photo_path": self.photo_path_db.get_image_path(photo_name, "_color"),
                                    "gray_photo_path": self.photo_path_db.get_image_path(photo_name, "_gray"),
                                    "print_source": ""
                                }
                            ]
                        
                    for photo_dict in thumbnail_images:
                        if photo_dict["color_photo_path"]:
                            thumb_photo_path = photo_dict["color_photo_path"]
                        else:
                            thumb_photo_path = photo_dict["print_source"]
                        thumbnail_path = self.get_thumbnail(thumb_photo_path)
                        if thumbnail_path is not None:
                            new_entry = {
                                    'source': thumbnail_path,
                                    'selected': False
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
                size_x=300,
                size_y=225
                )
            if not success:
                print("Failed to create thumbnail")
                return None
        #self.thumbnail_path_db.add_image(thumbnail_name, thumbnail_path)
        return thumbnail_path

class ImageGalleryApp(App):
    def build(self):
        root = FloatLayout()
        status_label = ColoredLabel(text='Choose sum photos', size_hint=(1, 0.05), color=[0, 0, 0, 1],
                                 pos_hint={'x': 0, 'bottom': 1})
        gallery = ImageGallery(status_label)
        gallery.scroll_type = ['content', 'bars']
        gallery.bar_width = '50dp'
        print("ImageGallery instance created and configured.")
        root.add_widget(gallery)
        root.add_widget(status_label)
        settings_button = Button(text="...", size_hint=(None, None), size=(25, 25),
                                 pos_hint={'left': 1, 'top': 1})
        root.add_widget(settings_button)
        return root

if __name__ == '__main__':
    ImageGalleryApp().run()
