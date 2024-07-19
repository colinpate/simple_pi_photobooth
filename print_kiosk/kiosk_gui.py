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
from kivy.properties import BooleanProperty, StringProperty
from kivy.metrics import dp  # Import dp function
from kivy.lang import Builder
from kivy.clock import Clock

from kivy.config import Config
Config.set('graphics', 'fullscreen', 'auto')
Config.set('input', 'mouse', 'None')

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
#import cups

from glob import glob
import yaml
import cv2
import os

from common.image_path_db import ImagePathDB

def load_config(config_path):
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config
    
def create_thumbnail(photo_path, thumbnail_path, size_x, size_y):
    image = cv2.imread(photo_path)
    out = cv2.resize(image, dsize=(size_x, size_y))
    cv2.imwrite(thumbnail_path, out)
    
Builder.load_string(
'''
<ImageGallery>:
    viewclass: 'SelectableImage'
    RecycleGridLayout:
        cols: 2
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
    popup_is_open = False

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        self.parent_gallery = rv
        print("Refreshed")
        return super(SelectableImage, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if self.collide_point(*touch.pos) and self.selectable:
            self.touch_start_pos = touch.pos
            #return self.parent.select_with_touch(self.index, touch)
            
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
        if self.popup_is_open:
            return
        self.popup_is_open = True
        ''' Show a popup with the expanded image '''
        layout = FloatLayout()
        popup = Popup(title='Expanded Image View',
                      content=layout,
                      size_hint=(0.8, 0.8))
        
        #image_base = source.split("_thumb")[0]
        #if image_base.endswith("_gray"):
        #    image_base = image_base[:-5]
        #color_source = image_base + ".jpg"
        #gray_source = image_base + "_gray.jpg"
        color_source = self.color_photo_path
        gray_source = self.gray_photo_path
        print("Color source:", color_source, "Gray source:", gray_source)
        
        image = AsyncImage(source=color_source, allow_stretch=True, size_hint=(0.8, 0.8), pos_hint={'x': 0.1, 'y': 0.2})
        layout.add_widget(image)
        
        # Define the close button
        close_button = Button(text='Close', size_hint=(0.1, 0.1),
                              pos_hint={'x': 0.6, 'y': 0})
                              
        def close_popup(instance):
            self.popup_is_open = False
            popup.dismiss()
                              
        close_button.bind(on_release=close_popup)
        layout.add_widget(close_button)
        
        # Define the toggle button and its callback
        toggle_button = ToggleButton(text='Black & White', size_hint=(0.2, 0.1),
                                     pos_hint={'x': 0.4, 'y': 0})
        layout.add_widget(toggle_button)
        
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
        if self.popup_is_open:
            return
        self.popup_is_open = True
        layout = FloatLayout()
        popup = Popup(title='Confirm print?',
                      content=layout,
                      size_hint=(0.5, 0.3))
                      
        yes_button = Button(text='Yes', size_hint=(0.5, 1),
                              pos_hint={'x': 0, 'y': 0})
            
        def close_popup(instance):
            self.popup_is_open = False
            popup.dismiss()
                              
        def print_image(instance):
            print("Printing", self.print_source)
            close_popup(instance)
                              
        yes_button.bind(on_release=print_image)
        layout.add_widget(yes_button)
                      
        no_button = Button(text='No', size_hint=(0.5, 1),
                              pos_hint={'x': 0.5, 'y': 0})
        no_button.bind(on_release=close_popup)
        layout.add_widget(no_button)
        
        popup.open()
        
    def print_image(self):
        prit()
        

class ImageGallery(RecycleView):
    def __init__(self, **kwargs):
        super(ImageGallery, self).__init__(**kwargs)
        
        config = load_config("print_config.yaml")
        
        self.thumbnail_path_db = ImagePathDB(config["thumbnail_path_db"])
        self.photo_path_db = ImagePathDB(config["photo_path_db"])
        self.thumbnail_dir = config["thumbnail_dir"]
        self.data = []
        #self.fill_image_path_db("../party_photos/becca_party_4_13_24/booth_photos/color/")
        Clock.schedule_once(self.update_data, 5)
        
        #self.image_dir = "../../party_photos/becca_party_4_13_24/booth_photos/color/"
        #self.image_dir = "../../party_photos/Mead_5th_Grade/"
        #self.image_paths = glob(self.image_dir + "*.png")
        #self.data = [{'source': i} for i in self.image_paths]  # Replace with your image paths
        #print(self.data)
        
    def on_touch_down(self, touch):
        if touch.device == 'mouse':
            print("Denied")
            return False
        return super(ImageGallery, self).on_touch_down(touch)
        
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
                
    def update_data(self, dt):
        # Check to see if there are any new thumbnails in the Thumbnail DB and add them to self.data if so
        self.photo_path_db.try_update_from_file()
        new_photo_names = list(self.photo_path_db.image_names())
        new_num_photos = len(new_photo_names)
        print("Updating data,", new_num_photos, "photos in database")
        if new_num_photos > len(self.data):
            print(new_num_photos - len(self.data), "new photos!")
            photo_names_sorted = sorted(new_photo_names)
            self.data = [
                    {
                        'source': self.get_thumbnail(i),
                        'gray_photo_path': self.photo_path_db.get_image_path(i, "_gray"),
                        'color_photo_path': self.photo_path_db.get_image_path(i, "_color"),
                    }
                for i in photo_names_sorted]
        Clock.schedule_once(self.update_data, 5)
            
    def get_thumbnail(self, thumbnail_name):
        # Returns path to thumbnail if it exists, creates it if not
        if self.thumbnail_path_db.image_exists(thumbnail_name):
            return self.thumbnail_path_db.get_image_path(thumbnail_name)
        else:
            thumbnail_path = os.path.join(self.thumbnail_dir, thumbnail_name + ".png")
            if not os.path.isfile(thumbnail_path):
                print("Creating thumbnail for", thumbnail_name)
                create_thumbnail(
                    photo_path=self.photo_path_db.get_image_path(thumbnail_name, postfix="_color"),
                    thumbnail_path=thumbnail_path,
                    size_x=400,
                    size_y=300
                    )
            self.thumbnail_path_db.add_image(thumbnail_name, thumbnail_path)
            return thumbnail_path

class ImageGalleryApp(App):
    def build(self):
        gallery = ImageGallery()
        gallery.scroll_type = ['content', 'bars']
        gallery.bar_width = '30dp'
        print("ImageGallery instance created and configured.")
        return gallery

if __name__ == '__main__':
    ImageGalleryApp().run()
