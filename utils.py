import streamlit as st
import boto3
from io import BytesIO
from embedchain import App
import os
import requests
import tempfile
import base64
from openai import OpenAI
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
import stripe


# AWS Credentials from OS environment variables
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
LISTINGS_FOLDER = "listings/"

# Initialize S3 clients
s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

# Initialize the chatbot instance
from dotenv import load_dotenv
load_dotenv()

def is_email_subscribed(email):
    # Initialize the Stripe API with the given key
    stripe.api_key = os.getenv("STRIPE_API_KEY")

    # List customers with the given email address
    customers = stripe.Customer.list(email=email)

    for customer in customers:
        # For each customer, list their subscriptions
        subscriptions = stripe.Subscription.list(customer=customer.id)
        
        # If any active subscription is found, return True
        for subscription in subscriptions:
            if subscription['status'] == 'active':
                return True

    # If no active subscriptions found, return False
    print(f"No active subscriptions found for {email}")
    return False

def save_listing(address):
    """Create a 'folder' for the listing in S3"""
    key = f"{LISTINGS_FOLDER}{address}/"
    s3.put_object(Bucket=BUCKET_NAME, Key=key)

    
def fetch_created_listings():
    """Fetch the list of created addresses from S3"""
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=LISTINGS_FOLDER, Delimiter='/')
    if 'CommonPrefixes' not in response:
        return []
    return [prefix['Prefix'].replace(LISTINGS_FOLDER, '').rstrip('/') for prefix in response['CommonPrefixes']]

def get_tenants_for_address(address):
    """Get the list of tenants who have applied for the given address"""
    prefix = f"{LISTINGS_FOLDER}{address}/"
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix, Delimiter='/')
    if 'CommonPrefixes' not in response:
        return []
    tenants = [tenant['Prefix'].split('/')[-2] for tenant in response['CommonPrefixes']]
    return tenants

def download_file_from_s3(bucket_name, object_name):
    """Download a file from S3 and return it as bytes"""
    try:
        response = s3.get_object(Bucket=bucket_name, Key=object_name)
        return response['Body'].read()
    except s3.exceptions.NoSuchKey:
        return None
    
def download_from_presigned_url(presigned_url):
    """Download a file from a presigned URL and return the path to the temporary file."""
    response = requests.get(presigned_url)
    response.raise_for_status()  # Raise an exception for HTTP errors

    # Create a temporary file and write the content to it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
        tmp_file.write(response.content)
        return tmp_file.name
    
def generate_presigned_url(bucket_name, object_name, expiration=3600):
    """Generate a presigned URL to share an S3 object"""
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': bucket_name, 'Key': object_name},
                                    ExpiresIn=expiration)
    return url

def determine_data_type(file_name):
    """Determine the data type for embedding based on the file extension."""
    file_extension = os.path.splitext(file_name)[1].lower()
    data_type_map = {
        ".pdf": "pdf_file",
        ".docx": "docx",
        ".txt": "text",
        ".png": "image",  # Added as an example. Add other image types as needed.
        ".jpg": "image",
        ".jpeg": "image",
        # Add more file extensions and their corresponding data types as needed
    }
    return data_type_map.get(file_extension, None)


def get_files_for_tenant(address, tenant_name, only_text=False):
    """Get the list of files uploaded by a specific tenant for the given address"""
    prefix = f"{LISTINGS_FOLDER}{address}/{tenant_name}/"
    response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)
    if 'Contents' not in response:
        return []
    if only_text:
        return [file for file in response['Contents'] if file['Key'].endswith('.txt')]
    else:
        return response['Contents']

def get_metadata_for_file(bucket_name, file_key):
    """Get the metadata for a specific file in S3"""
    response = s3.head_object(Bucket=bucket_name, Key=file_key)
    return response['Metadata']

def list_files_for_tenant(address, tenant_name):
    """List all the files uploaded by a specific tenant for the given address"""
    files = get_files_for_tenant(address, tenant_name)
    file_names = [file['Key'] for file in files]
    return file_names, files

def extract_url_from_txt(file_path):
    """Extract the URL from a .txt file"""
    with open(file_path, 'r') as file:
        return file.read().strip()
    
@st.cache_resource
def create_bot(selected_address, selected_tenant):
    # Embed the documents into the bot
    bot = App(system_prompt=f"You are a tenant named {selected_tenant} who is interested in renting the unit at {selected_address}. You are currently being interviewed to determine if you are a good fit for the unit. You will be asked questions about the documents you have uploaded.")
    files = get_files_for_tenant(selected_address, selected_tenant, only_text=True)
    for file in files:
        presigned_url = generate_presigned_url(BUCKET_NAME, file['Key'])
        local_file_path = download_from_presigned_url(presigned_url)
        
        # Fetch metadata for the file
        metadata = get_metadata_for_file(BUCKET_NAME, file['Key'])
        document_type = metadata.get('document_type', '').lower()
        print('hi')
        st.write(document_type)
        st.write(local_file_path)
        # Read the content of the file
        with open(local_file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        name = selected_tenant.replace('_', ' ')  # This should be fetched dynamically
        address = selected_address
        response = client.chat.completions.create(model="gpt-3.5-turbo-16k-0613",
        messages=[
              {'role': 'system', 'content': f'You are very detail oriented property management analyst, who carefully reads all details of an unstructured document and creates a structured document containing all key pieces of information that would be helpful for analyzing the tenant.'},
            {"role": "user", "content": f"Based on the following messy document from {name} with document type {document_type}, provide a summary of the document. Carefully report all key metrics. Do not provide your own commentary. Just summarize very carefully. Only include information that would be important for determining whether the tenant is a good fit for the rental property. Don't include anything about disclaimers or stuff like that. Here is the document: \n ```{file_content}```"}
        ],
        temperature=0.0)
        response_text = response['choices'][0]['message']['content']
        response_text = response_text.replace('*', '\*').replace('_', '\_')
        response_text = response_text.replace('\xa0', ' ')
        response_text = response_text.replace('$', '\$')
        if "youtube url" in document_type:
            st.write(extract_url_from_txt(local_file_path))
            bot.add(extract_url_from_txt(local_file_path))
        else:
            data_type = determine_data_type(file['Key'])
            if data_type:
                try:
                    print(response_text)
                    bot.add(response_text, data_type)  # Pass the file content instead of the path
                except Exception as e:
                    st.warning(f"Error embedding {file['Key']}: {e}")
            else:
                st.warning(f"Unsupported file type for {file['Key']}")
    return bot


def display_pdf(file_data):
    """
    Display a PDF in Streamlit.
    
    Parameters:
    - file_data (bytes): PDF file data.
    """
    # Encode the file data using base64 encoding
    base64_pdf = base64.b64encode(file_data).decode('utf-8')
    
    # Embed the base64 encoded file in HTML iframe
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="800" height="800" type="application/pdf"></iframe>'
    
    # Use st.markdown to render the pdf document in Streamlit
    st.markdown(pdf_display, unsafe_allow_html=True)

def extract_categories_from_files(address, tenant_name):
    """Extract unique document categories from the list of files."""
    files = get_files_for_tenant(address, tenant_name)

    categories = set()
    for file in files:
        metadata = get_metadata_for_file(BUCKET_NAME, file['Key'])
        document_type = metadata.get('document_type', '').lower()
        # Split the file path and get the category (assuming the format is always consistent)
        categories.add(document_type)
    return list(categories)