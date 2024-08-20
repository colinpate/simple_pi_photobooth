import json
import os

class ImagePathDB:
    def __init__(self, db_file_path, old_root=None):
        self._db_file_path = db_file_path
        self._root_folder = os.path.split(db_file_path)[0]
        self._old_root = old_root
        self.db = {}
        self.try_update_from_file()
        
    def add_image(self, image_name, val):
        if isinstance(val, dict):
            self.db[image_name] = {
                postfix: os.path.relpath(path, start=self._root_folder)
                for postfix, path in val.items()
            }
        elif isinstance(val, str):
            self.db[image_name] = os.path.relpath(val, start=self._root_folder)
        
    def get_image_path(self, image_name, postfix=None):
        if not postfix:
            path = self.db[image_name]
        else:
            path = self.db[image_name][postfix]
        if self._old_root:
            path = path.replace(self._old_root, self._root_folder)
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(self._root_folder, path)
        
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
            json.dump(self.db, db_file)
