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
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Rectangle
from kivy.properties import BooleanProperty, StringProperty
from kivy.metrics import dp, sp  # Import dp and sp functions
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.config import Config

from glob import glob
import yaml
import os
import sys
from collections import OrderedDict
import time
import json
from datetime import datetime

from selectable_image import SelectableImage
from print_formatter import PrintFormatter
from booth_sync import BoothSync
from common.common import load_config

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
    
from kivy.core.window import Window
    
    
Builder.load_string(
'''
<Label>:
    font_size: sp(30)
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
        

class ImageGallery(RecycleView):
    def __init__(self, status_label, parent_app, **kwargs):
        super(ImageGallery, self).__init__(**kwargs)
        
        config = parent_app.config_yaml
            
        self.photo_dir = config["photo_dir"]
        self.remote_photo_dir = config["remote_photo_dir"]
        self.status_file_path = config.get("status_file_path", "")
        self.status_update_interval = config.get("status_update_interval", 60)
        
        #if "fill_dir" in config.keys():
        #    self.fill_image_path_db(config["fill_dir"])
        
        self.status_label = status_label
        self.parent_app = parent_app
        self.old_num_thumbnails = 0
        self.status_popup = None
        self.data = []
        self.print_selections = []
        self.separate_gray_thumbnails = True
        
        self.print_formatter = PrintFormatter(**config)
        self.booth_sync = BoothSync(**config, local_test=LOCAL_TEST)
        if not LOCAL_TEST:
            self.setup_printer()
        
        Clock.schedule_once(self.update_data, 0)
        Clock.schedule_once(self.update_status_file, 0)

    def update_status_file(self, dt):
        if self.status_file_path:
            try:
                with open(self.status_file_path, "w") as status_file:
                    timestamp = time.strftime("%y/%m/%d %H:%M:%S")
                    print_level = str(self.get_printer_marker_level())
                    connected = str(self.booth_sync.is_nfs_mounted())
                    status = {
                        "timestamp": timestamp,
                        "print_level": print_level,
                        "connected": connected
                    }
                    json.dump(status, status_file)
                print(f"Wrote {status} to json file")
            except Exception as e:
                print("Failed to write to json file, error ", e)
            Clock.schedule_once(self.update_status_file, self.status_update_interval)

    def setup_printer(self):
        self.conn = cups.Connection()
        printers = self.conn.getPrinters()
        self.printer_name = list(printers.keys())[0]  # Assuming the first printer is your target printer
        
    def get_printer_info(self):
        attrs = self.conn.getPrinterAttributes(self.printer_name)
        return attrs
        
    def get_printer_marker_level(self):
        if not LOCAL_TEST:
            attrs = self.get_printer_info()
            marker_level = attrs.get("marker-levels", [100])[0]
        else:
            marker_level = 39
        return marker_level
        
    def clear_selection(self):
        # Update the data model
        for item in self.data:
            item['selected'] = False
        self.print_selections = []
        # Refresh the data to ensure the view is updated
        self.refresh_from_data()
        
    def prepare_print(self, instance):
        print("Preparing print")
        print_path = "print_image.jpg"
        preview_path = "formatted.png"
        self.print_formatter.format_and_save_print(self.print_selections, print_path, preview_path)
        self.status_popup.dismiss()
        print("Showing preview popup")
        self.show_print_preview_popup(print_path, preview_path)
        self.clear_selection()
        self.update_status_label()

    def update_status_label(self):
        num_selected = len(self.print_selections)
        need = self.print_formatter.num_photos()
        rem = need - num_selected
        if rem == 0:
            text = ""
        elif rem == 1:
            text = "Select 1 more photo"
        else:
            text = f"Select {rem} photos"
        self.status_label.text = text
                    
    def add_print_selection(self, image_path):
        if image_path not in self.print_selections:
            self.print_selections.append(image_path)
            self.update_status_label()
            if len(self.print_selections) == self.print_formatter.num_photos():
                self.show_processing_popup(None)
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
        self.parent_app.popups["print preview"] = popup
        image = AsyncImage(source=os.path.abspath(preview_path), allow_stretch=True, size_hint=(1, 0.8), pos_hint={'x': 0, 'y': 0.15})
        image.reload()
        layout.add_widget(image)
        
        # Define the close button
        close_button = Button(text='Cancel', size_hint=(0.4, 0.1),
                              pos_hint={'x': 0.55, 'y': 0.02})
                              
        close_button.bind(on_release=popup.dismiss)
        layout.add_widget(close_button)
        
        # Define the print button and its callback
        print_button = Button(text='Print!', size_hint=(0.4, 0.1),
                              pos_hint={'x': 0.05, 'y': 0.02})
        layout.add_widget(print_button)
        
        def on_print(instance):
            popup.dismiss()
            self.print_images(formatted_path)
            
        print_button.bind(on_release=on_print)
            
        popup.open()
        
    def print_images(self, formatted_path):
        print("Printing", formatted_path)
        Clock.schedule_once(self.show_printing_popup, 0)
        if not LOCAL_TEST:
            options=self.print_formatter.print_options()
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
    
    def show_processing_popup(self, instance):
        print("Showing processing popup")
        layout = GridLayout(cols=1)
        popup = Popup(title='',
                      content=layout,
                      size_hint=(0.5, 0.3))
                      
        printing_label = Label(text='Processing...', font_size=sp(30))
        layout.add_widget(printing_label)
        
        popup.open()
        
        self.status_popup = popup

    def show_printing_popup(self, instance):
        layout = GridLayout(cols=1)
        popup = Popup(title='',
                      content=layout,
                      size_hint=(0.7, 0.3))
                      
        printing_label = Label(text='Printing!', font_size=sp(30))
        layout.add_widget(printing_label)
        
        print_progress_bar = ProgressBar(max=100)
        layout.add_widget(print_progress_bar)
        glowbot_label = Label(text="", font_size=sp(20))
        layout.add_widget(glowbot_label)
        
        print_time = time.time()
        
        def switch_label_text():
            now = time.time()
            time_elapsed = now - print_time
            text_index = int(time_elapsed / 5) % 2
            label_texts = [
                'Check us out at www.glowbot.co',
                "Please don't grab the photo early"
            ]
            glowbot_label.text = label_texts[text_index]
        
        def update_progress_bar(instance):
            print_progress_bar.value += 4
            switch_label_text()
            if print_progress_bar.value >= 100:
                popup.dismiss()
            else:
                Clock.schedule_once(update_progress_bar, 1)
        
        popup.open()
        
        Clock.schedule_once(update_progress_bar, 1)

    def shutdown(self):
        self.booth_sync.shutdown()
                
    def update_data(self, dt):
        if not self.booth_sync.is_nfs_mounted():
            self.parent_app.add_error_label()
        else:
            self.parent_app.remove_error_label()
        
        if not self.booth_sync.is_syncing():
            thumbnails = self.booth_sync.thumbnails.copy()
            new_num_thumbnails = len(thumbnails)
            if new_num_thumbnails != self.old_num_thumbnails:
                print("New thumbnails found:", new_num_thumbnails - self.old_num_thumbnails, time.time() % 1000)
                self.old_num_thumbnails = new_num_thumbnails

                image_paths = list(thumbnails.keys())
                image_paths_sorted = sorted(image_paths, key=lambda x: os.path.split(x)[-1], reverse=True)
                
                new_data = []
                for image_path in image_paths_sorted:
                    thumbnail_path = thumbnails[image_path]
                    new_entry = {
                            'source': thumbnail_path,
                            'selected': False,
                            "print_source": image_path,
                            "gray_photo_path": "",
                            "color_photo_path": ""
                            }
                    new_data.append(new_entry)
                self.data = new_data
        else:
            print("Not updating data, syncing is occur", time.time() % 1000)
            
        self.booth_sync.update_watchdog()
        Clock.schedule_once(self.update_data, 1)
        
        
class SplashImage(Image):
    def __init__(self, close_self, **kwargs):
        super(SplashImage, self).__init__(**kwargs)
        self.allow_stretch = True
        self.keep_ratio = False
        self.close_self = close_self
        
    def on_touch_down(self, touch):
        Clock.schedule_once(self.close_self, 0)
        return True


class ImageGalleryApp(App):
    def build(self):
        if LOCAL_TEST:
            config = load_config("print_config_test")
        else:
            config = load_config("print_config")
        self.config_yaml = config
    
        root = FloatLayout()
        status_label = ColoredLabel(text='Choose photos', size_hint=(1, 0.05), color=[0, 0, 0, 1],
                                 pos_hint={'x': 0, 'bottom': 1}, font_size=sp(30))
        gallery = ImageGallery(status_label, self)
        gallery.scroll_type = ['content', 'bars']
        gallery.bar_width = '50dp'
        print("ImageGallery instance created and configured.")
        root.add_widget(gallery)
        self.gallery = gallery
        root.add_widget(status_label)
        settings_button = Button(text="...", size_hint=(None, None), size=(35, 35),
                                 pos_hint={'left': 1, 'top': 1})
        settings_button.bind(on_release=self.show_settings_popup)
        root.add_widget(settings_button)
        
        self.error_label = ColoredLabel(text='Not connected to Photo Booth', size_hint=(1, 0.05), color=[0, 0, 0, 1],
                                 pos_hint={'x': 0, 'top': 1}, font_size=sp(30))
        self.has_error_label = False
        
        self.splash_image = SplashImage(source=self.config_yaml["splash_image"],
                                        size_hint=(1, 1),
                                        pos_hint={"left": 1, "top": 1},
                                        close_self=self.remove_splash
                                    )
        self.has_splash = False
        self.last_touched = 0
        self.splash_timeout = self.config_yaml["splash_timeout"]
        
        Window.bind(on_touch_down=self.on_touch_down)
        
        Clock.schedule_once(self.check_last_touch, 1)
        self.popups = {}
        
        return root
        
    def check_last_touch(self, dt):
        now = time.time()
        if (now - self.last_touched) > self.splash_timeout:
            Clock.schedule_once(self.add_splash, 0)
        Clock.schedule_once(self.check_last_touch, 1)
        
    def on_touch_down(self, window, touch):
        # This method will be called for any touch, even in popups
        self.last_touched = time.time()
        return False
        
    def remove_splash(self, dt):
        if self.has_splash:
            self.root.remove_widget(self.splash_image)
            self.has_splash = False
        
    def add_splash(self, dt):
        if not self.has_splash:
            for popup in self.popups.values():
                popup.dismiss()
            self.has_splash = True
            self.root.add_widget(self.splash_image, canvas="after")
        
    def add_error_label(self):
        if not self.has_error_label:
            self.has_error_label = True
            self.root.add_widget(self.error_label, 1) # 1 index so it goes behind settings button
        
    def remove_error_label(self):
        if self.has_error_label:
            self.has_error_label = False
            self.root.remove_widget(self.error_label)
        
    def show_settings_popup(self, instance):
        ''' Show a popup with the expanded image '''
        layout = GridLayout(cols=1)
        popup = Popup(title='Settings',
                      content=layout,
                      size_hint=(0.8, 0.9))
        self.popups["settings"] = popup
                      
        double = GridLayout(cols=2, size_hint=(0.3, 0.1))
        print_level_label = Label(text='', font_size=sp(20))
        double.add_widget(print_level_label)
        print_level = ProgressBar(max=100)
        if LOCAL_TEST:
            marker_level = 69
        else:
            marker_level = self.gallery.get_printer_marker_level()
        print_level.value = marker_level
        print_level_label.text = f"Print Level {marker_level}%"
        double.add_widget(print_level)
        layout.add_widget(double)
         
        close_button = Button(text='Close Settings', size_hint=(0.3, 0.1))
        close_button.bind(on_release=popup.dismiss)
        layout.add_widget(close_button)
                      
        exit_button = Button(text='Exit Kiosk', size_hint=(0.3, 0.1))
        def close(instance):
            self.gallery.shutdown()
            sys.exit(0)
        exit_button.bind(on_release=close)
        layout.add_widget(exit_button)
                      
        shutdown_button = Button(text='Shutdown', size_hint=(0.3, 0.1))
        def shutdown(instance):
            self.gallery.shutdown()
            os.system("sudo shutdown now")
            sys.exit(0)
        shutdown_button.bind(on_release=shutdown)
        layout.add_widget(shutdown_button)
                      
        restart_button = Button(text='Reboot', size_hint=(0.3, 0.1))
        def restart(instance):
            self.gallery.shutdown()
            os.system("sudo reboot")
            sys.exit(0)
        restart_button.bind(on_release=restart)
        layout.add_widget(restart_button)
        
        popup.open()

if __name__ == '__main__':
    ImageGalleryApp().run()
