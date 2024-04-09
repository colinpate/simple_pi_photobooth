import json
import os

class ImagePathDB:
    def __init__(self, db_file_path):
        self._db_file_path = db_file_path
        self.db = {}
        self.try_update_from_file()
        
    def add_image(self, image_name, val):
        self.db[image_name] = val
        
    def get_image_path(self, image_name, postfix=None):
        if not postfix:
            return self.db[image_name]
        else:
            return self.db[image_name][postfix]
        
    def image_exists(self, image_name):
        return image_name in self.db.keys()
        
    def image_names(self):
        return self.db.keys()
        
    def try_update_from_file(self):
        try:
            with open(self._db_file_path, "r") as db_file:
                new_db = json.load(db_file)
            self.db.update(new_db)
            return True
        except:
            return False
            
    def update_file(self):
        with open(self._db_file_path, "w") as db_file:
            db_file.dump(self.db)
