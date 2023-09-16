from pytesseract import pytesseract
from pytesseract import image_to_string
from PIL import Image
from io import BytesIO
import pypdfium2 as pdfium
import tempfile
from pdf2image import convert_from_bytes
# Set the path for tesseract
pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Change this to the path where tesseract is installed


def convert_pdf_to_images(file_bytes, dpi=300):
    images = convert_from_bytes(file_bytes.getvalue(), dpi=dpi)
    final_images = []

    for index, image in enumerate(images):
        image_byte_array = BytesIO()
        image.save(image_byte_array, format='jpeg', optimize=True)
        image_byte_array = image_byte_array.getvalue()
        final_images.append(dict({index: image_byte_array}))

    return final_images


def extract_text_with_pytesseract(list_dict_final_images):
    
    image_list = [list(data.values())[0] for data in list_dict_final_images]
    image_content = []
    
    for index, image_bytes in enumerate(image_list):
        
        image = Image.open(BytesIO(image_bytes))
        raw_text = str(image_to_string(image))
        image_content.append(raw_text)
    
    return "\n".join(image_content) 
