import cups

def send_to_printer(image_path):
    conn = cups.Connection()
    printers = conn.getPrinters()
    printer_name = list(printers.keys())[0]  # Assuming the first printer is your target printer
        
    # Print options dictionary
    options = {
#        'media': 'Photo4x6',       # Set the paper size, e.g., 4x6 inches
#        'fit-to-page': 'True',     # Fit the image to the page size
#        'cut': 'True'              # Enable automatic cutting if supported
    }

    # Sending the print job with options
    conn.printFile(printer_name, image_path, "Photo Print", options)

send_to_printer("/home/colin/Pictures/me_bella.jpg")
