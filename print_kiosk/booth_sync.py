import subprocess
import threading
import time
import os
import glob
import cv2
import json

from common.image_path_db import ImagePathDB

WATCHDOG_TIMEOUT = 10
CHECK_INTERVAL_S = 1
    
def create_thumbnail(photo_path, thumbnail_path, size_x, size_y):
    image = cv2.imread(photo_path)
    if image is not None:
        out = cv2.resize(image, dsize=(size_x, size_y))
        cv2.imwrite(thumbnail_path, out)
        return True
    else:
        return False

class BoothSync:
    def __init__(self, mount_addresses, mount_source, remote_photo_dir, photo_dir, print_postfixes, thumbnail_dir, local_test,  **kwargs):
        self.stop_thread = False
        self._is_nfs_mounted = False
        self.mount_addresses = mount_addresses
        self.mount_source = mount_source
        self.remote_photo_dir = remote_photo_dir
        self.photo_dir = photo_dir
        self.print_postfixes = print_postfixes
        self.local_test = local_test
        self.thumbnail_dir = thumbnail_dir
        self._is_syncing = False
        self.thumbnails = {}
        self.photo_path_db = ImagePathDB(os.path.join(self.photo_dir, "photo_db.json"), old_root="/home/colin/booth_photos" if self.local_test else None)
        self.mount_check_thread = threading.Thread(target=self.check_nfs_mount)
        self.mount_check_thread.start()
        self.update_watchdog()
        
    def update_watchdog(self):
        self.watchdog_updated = time.time()
        if not self.mount_check_thread.is_alive():
            raise ValueError("Mount check thread failed!")
            
    def is_syncing(self):
        return self._is_syncing
        
    def check_nfs_mount(self):
        old_db = {}
        while not self.stop_thread:
            ls_timeout = False
            try:
                # Check if the mount point is available by looking up our Photo DB
                output = subprocess.check_output(['cat', os.path.join(self.remote_photo_dir, "photo_db.json")], timeout=5)
                new_db = json.loads(output.decode())
                if old_db != new_db:
                    print("New db found", time.time() % 1000)
                    old_db = new_db
                self._is_nfs_mounted = True
            except (subprocess.CalledProcessError) as exception:
                print("NFS access failed", exception)
                self._is_nfs_mounted = False
            except (subprocess.TimeoutExpired) as exception:
                print("NFS access timed out")
                self._is_nfs_mounted = False
                ls_timeout = True

            if self.is_nfs_mounted():
                self.photo_path_db.replace_db(new_db)
                self.update_thumbnails()
                
            # Unmount the directory if ls times out, cuz it can get stuck
            if ls_timeout:
                try:
                    subprocess.check_output(['sudo', "umount", "-f", self.remote_photo_dir], timeout=3)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
                    print("Umount failed", exception)

            if not self._is_nfs_mounted:
                for mount_address in self.mount_addresses:
                    try:
                        subprocess.check_output(['sudo', "mount", f"{mount_address}:{self.mount_source}", self.remote_photo_dir], timeout=3)
                        print("Successfully mounted from", mount_address)
                        break
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
                        print("Failed to mount from", mount_address)
                        
            time.sleep(CHECK_INTERVAL_S)
            
            if (time.time() - self.watchdog_updated) > WATCHDOG_TIMEOUT:
                raise ValueError("Booth sync thread watchdog timed out")
            
    def is_nfs_mounted(self):
        return self._is_nfs_mounted
            
    def sync_remote_to_local(self, local_dir, timeout):
        try:
            # Attempt to sync the mounted directory
            subprocess.check_output(['rsync', "-a", self.remote_photo_dir, local_dir], timeout=timeout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
            print("rsync failed", exception)

    def shutdown(self):
        self.stop_thread = True
        self.mount_check_thread.join()

    def get_image_db_paths(self):
        image_paths = []
        for image_name in self.photo_path_db.image_names():
            for postfix in self.print_postfixes:
                image_path = self.photo_path_db.get_image_path(image_name, postfix)
                image_paths.append(image_path)
        return image_paths

    def update_thumbnails(self):
        # Check to see if there are any new photos and if so create the thumbnails
        local_image_paths = self.get_image_db_paths()
        image_path_set = set(local_image_paths)
        
        deleted_image_paths = self.thumbnails.keys() - image_path_set
        for image_path in deleted_image_paths:
            self.thumbnails.pop(image_path)
        
        new_image_paths = image_path_set - self.thumbnails.keys()
        if len(new_image_paths):
            print("New images found without thumbnails:", len(new_image_paths), time.time() % 1000)
            # There are images we haven't made thumbnails for
            for image_path in new_image_paths:
                thumbnail_path = self.get_thumbnail(image_path)
                if thumbnail_path is not None:
                    self.thumbnails[image_path] = thumbnail_path

    def sync_photo_to_local(self, local_image_path):
        raw_image_path = local_image_path.replace(self.photo_dir, "")
        remote_image_path = os.path.join(self.remote_photo_dir, raw_image_path)
        try:
            print("Copying", remote_image_path, "to", local_image_path, time.time() % 1000)
            subprocess.check_output(["cp", remote_image_path, local_image_path], timeout=15)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exception:
            print("Copy failed", exception)
            if os.path.isfile(local_image_path):
                print("Removing partial file")
                os.remove(local_image_path)
            return False

    def get_thumbnail(self, image_path):
        filename = os.path.split(image_path)[1]
        filename = filename.split(".")[0]
        thumbnail_path = os.path.join(self.thumbnail_dir, filename + ".png")
        if not os.path.isfile(thumbnail_path):
            if not os.path.isfile(image_path):
                success = self.sync_photo_to_local(image_path)
                if not success:
                    return None
            success = create_thumbnail(
                photo_path=image_path,
                thumbnail_path=thumbnail_path,
                size_x=300,
                size_y=225
                )
            if not success:
                #print("Failed to create thumbnail for", filename)
                return None
            else:
                print("Successfully created thumbnail for", filename, time.time() % 1000)
        return thumbnail_path
