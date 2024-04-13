from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, build_from_document
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os
import requests

def build_service_from_document(credentials):
    url = 'https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
    response = requests.get(url)
    doc = response.json()
    service = build_from_document(doc, credentials=credentials)
    return service

def authenticate_google_photos():
    """Authenticate to Google API and handle token refresh logic."""
    creds = None
    # Path to your 'token.json' file which stores user's access and refresh tokens
    token_file = 'token.json'
    # Path to your 'credentials.json' file downloaded from the Google Developer Console
    credentials_file = 'g_photos_creds.json'
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            scopes = ['https://www.googleapis.com/auth/photoslibrary',
                      'https://www.googleapis.com/auth/photoslibrary.sharing']
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes=scopes)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    return build_service_from_document(credentials=creds), creds

def create_shared_album(service, album_title):
    """Create a shared Google Photos album and return the album ID and shareable URL."""
    create_album_body = {
        'album': {'title': album_title}
    }
    album_result = service.albums().create(body=create_album_body).execute()
    album_id = album_result['id']
    
    share_album_body = {
        'sharedAlbumOptions': {
            'isCollaborative': False,
            'isCommentable': False
        }
    }
    share_result = service.albums().share(albumId=album_id, body=share_album_body).execute()
    shareable_link = share_result['shareInfo']['shareableUrl']
    return album_id, shareable_link

def upload_media(creds, file_path):
    """Upload media to Google Photos and return the upload token."""
    headers = {
        'Authorization': 'Bearer ' + creds.token,
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
        
def get_media_item(service, media_item_id):
    """Retrieve a media item by ID and return its URL."""
    response = service.mediaItems().get(mediaItemId=media_item_id).execute()
    return response.get('productUrl')
    
def upload_photo(service, creds, album_id, photo_file_path):
    """Upload a photo to a specified Google Photos album and get its URL."""
    file_metadata = {
        'newMediaItems': [{
            'simpleMediaItem': {
                'uploadToken': upload_media(creds, photo_file_path)
            }
        }]
    }
    if album_id is not None:
        file_metadata['albumId'] = album_id

    batch_response = service.mediaItems().batchCreate(body=file_metadata).execute()
    media_item_id = batch_response['newMediaItemResults'][0]['mediaItem']['id']
    photo_url = get_media_item(service, media_item_id)
    return photo_url

def main():
    service, creds = authenticate_google_photos()
    album_title = 'My Raspberry Pi Album 3'
    album_id, shareable_link = create_shared_album(service, album_title)
    print(f"Album created. Shareable link: {shareable_link}")
    
    photo_path = '../party_photos/booth_photos/color/24_03_02_22_25_15.jpg'  # Update this with the path to your photo
    url = upload_photo(service, creds, album_id, photo_path)
    print(url)
    print("Photo uploaded successfully to the album.")

if __name__ == '__main__':
    main()

