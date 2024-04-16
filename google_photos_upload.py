from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, build_from_document
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import requests
from datetime import datetime
from photo_service import PhotoService


def build_service_from_document(credentials):
    url = 'https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
    response = requests.get(url)
    doc = response.json()
    service = build_from_document(doc, credentials=credentials)
    return service
        
        
class GooglePhotos(PhotoService):
    def __init__(self):
        self.service, self.creds = self.authenticate_google_photos()
        album_title = self.get_album_title()
        self.album_id, self.album_link = self.create_shared_album(album_title)
        print(f"Album '{album_title}' created. Shareable link: {self.album_link}")
        
    def upload_photo(self, photo_path, photo_name):
        url = self._upload_photo(self.album_id, photo_path)
        print("Photo uploaded successfully to the album.", url)
        return self.album_link
        
    def authenticate_google_photos(self):
        """Authenticate to Google API and handle token refresh logic."""
        creds = None
        # Path to your 'token.json' file which stores user's access and refresh tokens
        token_file = '/home/colin/token.json'
        # Path to your 'credentials.json' file downloaded from the Google Developer Console
        credentials_file = '/home/colin/g_photos_creds.json'
        
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                scopes = ['https://www.googleapis.com/auth/photoslibrary',
                          'https://www.googleapis.com/auth/photoslibrary.sharing']
                          
                flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes=scopes)
                creds = flow.run_local_server(port=0, open_browser=False)
            # Save the credentials for the next run
            with open(token_file, 'w') as token:
                token.write(creds.to_json())

        return build_service_from_document(credentials=creds), creds

    def create_shared_album(self, album_title):
        """Create a shared Google Photos album and return the album ID and shareable URL."""
        create_album_body = {
            'album': {'title': album_title}
        }
        album_result = self.service.albums().create(body=create_album_body).execute()
        album_id = album_result['id']
        
        share_album_body = {
            'sharedAlbumOptions': {
                'isCollaborative': False,
                'isCommentable': False
            }
        }
        share_result = self.service.albums().share(albumId=album_id, body=share_album_body).execute()
        shareable_link = share_result['shareInfo']['shareableUrl']
        return album_id, shareable_link

    def upload_media(self, file_path):
        """Upload media to Google Photos and return the upload token."""
        headers = {
            'Authorization': 'Bearer ' + self.creds.token,
            'Content-Type': 'application/octet-stream',
            'X-Goog-Upload-Content-Type': 'image/jpeg',  # Adjust based on your file type
            'X-Goog-Upload-Protocol': 'raw',
        }

        img_data = open(file_path, 'rb').read()
        response = requests.post('https://photoslibrary.googleapis.com/v1/uploads', headers=headers, data=img_data)
        if response.status_code == 200:
            return response.text  # This is the upload token needed for the next step
        else:
            raise Exception("Failed to upload photo: {}".format(response.text))
            
    def get_media_item(self, media_item_id):
        """Retrieve a media item by ID and return its URL."""
        response = self.service.mediaItems().get(mediaItemId=media_item_id).execute()
        return response.get('productUrl')
        
    def _upload_photo(self, album_id, photo_file_path):
        """Upload a photo to a specified Google Photos album and get its URL."""
        file_metadata = {
            'newMediaItems': [{
                'simpleMediaItem': {
                    'uploadToken': self.upload_media(photo_file_path)
                }
            }]
        }
        if album_id is not None:
            file_metadata['albumId'] = album_id

        batch_response = self.service.mediaItems().batchCreate(body=file_metadata).execute()
        media_item_id = batch_response['newMediaItemResults'][0]['mediaItem']['id']
        photo_url = self.get_media_item(media_item_id)
        return photo_url

    def get_album_title(self):
        formatted_datetime = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        album_title = 'Glowbot ' + formatted_datetime
        return album_title

def main():
    gp = GooglePhotos()
    url = gp.upload_photo("../party_photos/becca_party_4_13_24/booth_photos/color/240412_213501_color.jpg")
    print(url)

if __name__ == '__main__':
    main()

