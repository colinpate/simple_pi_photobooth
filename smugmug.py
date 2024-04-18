import requests
import json
from rauth import OAuth1Session
from pprint import pprint
import random
from photo_service import PhotoService

BASE_URL = "https://api.smugmug.com/api/v2"
UPLOAD_URL = "https://upload.smugmug.com/api/v2"

            
def load_creds(creds_file):
    with open(creds_file, "r") as file_obj:
        creds = json.load(file_obj)
    return creds
        
        
class SmugMug(PhotoService):
    def __init__(self):
        creds = load_creds("/home/colin/smugmug.json")
        token = creds["token"]
        key = creds["key"]
        secret = creds["secret"]
        token_secret = creds["token_secret"]

        self.session = OAuth1Session(
                key,
                secret,
                token,
                token_secret)
        self.session.get(
            BASE_URL + '/api/v2!authuser',
            headers={'Accept': 'application/json'}).text

        user_name = creds["user_name"]
        self.root_node = self.get_user_node(user_name)
        self.album_uri = None
            
    def upload_photo(self, photo_path, photo_name):
        uri = self._upload_photo(photo_path)
        return uri["Image"]["URL"]
            
    def create_album(self, album_name):
        # Create an album
        self.album_uri = self.create_album_under_node(self.root_node, album_name)

    def get_user_node(self, user_name):
        url = f"https://api.smugmug.com/api/v2/user/{user_name}"
        print(url)
        headers = {
            "Accept": "application/json"
        }

        # Fetch user information
        response = self.session.get(url, headers=headers)
        if response.status_code == 200:
            user_info = response.json()
            root_node_id = user_info['Response']['User']['Uris']['Node']['Uri'].split('/')[-1]
            print("Root Node ID:", root_node_id)
            return root_node_id
        else:
            print("Failed to retrieve user 3 information. Status code:", response.status_code, "Response:", response.text)
            return None

    def get_root_node_id(self, access_token):
        url = "https://api.smugmug.com/api/v2!authuser"
        headers = {
            "Accept": "application/json"
        }

        # Fetch user information
        response = self.session.get(url, headers=headers)
        if response.status_code == 200:
            user_info = response.json()
            root_node_id = user_info['Response']['User']['Uris']['Node']['Uri'].split('/')[-1]
            print("Root Node ID:", root_node_id)
            return root_node_id
        else:
            print("Failed to retrieve user information. Status code:", response.status_code, "Response:", response.text)
            return None

    def create_album_under_node(self, node_id, album_name):
        safe_album_name = album_name.replace(":", "")
        safe_album_name = safe_album_name.replace("/", "")
        safe_album_name = safe_album_name.replace(" ", "")
        safe_album_name = safe_album_name[0].upper() + safe_album_name[1:].lower()
        url = f"https://api.smugmug.com/api/v2/node/{node_id}!children"
        print(url)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "Type": "Album",
            "Name": album_name,
            "UrlName": safe_album_name,  # Creating a URL-friendly name
            "Privacy": "Unlisted"  # or another privacy setting as required
        }
        response = self.session.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            print("Album created successfully:")
            return response.json()['Response']['Node']['Uris']["Album"]["Uri"]
        else:
            print("Failed to create album. Status code:", response.status_code, "Response:", response.text)
            return None

    def _upload_photo(self, photo_path):
        """
        Upload a photo to a specified SmugMug album.

        Args:
        photo_path (str): The file path to the photo you want to upload.

        Returns:
        dict: The response from the server after the upload attempt.
        """
        # Extract the album key from the album URI
        album_key = self.album_uri.split("/")[-1]

        # Define the endpoint
        url = f"https://upload.smugmug.com/{album_key}"

        # Prepare headers
        headers = {
            "X-Smug-AlbumUri": self.album_uri,
            "X-Smug-Version": "v2",
            "X-Smug-ResponseType": "JSON"
        }

        # Read the image file in binary mode
        with open(photo_path, 'rb') as file:
            files = {'file': file.read()}
            # Send the POST request
            response = self.session.post(url, headers=headers, files=files)

        # Check if the upload was successful
        if response.status_code == 200:
            print("Upload successful.")
            return response.json()
        else:
            print(f"Failed to upload photo. Status code: {response.status_code}")
            return response.json()
        

def main():
    service = SmugMug()
    album_name = f"Test Album {random.randint(0, 12000)}"
    service.create_album(album_name)
    
    file_path = "../party_photos/becca_party_4_13_24/booth_photos/color/240412_213501_color.jpg"
    
    # Upload a photo to the album
    photo_url = service.upload_photo(file_path, "foo")
    print(photo_url)

if __name__ == "__main__":
    main()
