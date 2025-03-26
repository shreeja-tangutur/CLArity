import boto3
import os

# Fetch S3 settings from environment
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

# Initialize S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME,
)

# Define test file name
file_name = "s3_test_file.txt"
test_content = "This is a test file uploaded to S3."

# Write the file locally
with open(file_name, "w") as file:
    file.write(test_content)

# Upload file to S3
try:
    s3.upload_file(file_name, AWS_STORAGE_BUCKET_NAME, file_name)
    print(f"✅ File uploaded successfully to S3: {file_name}")
except Exception as e:
    print(f"❌ Upload failed: {e}")

# Remove the local test file
os.remove(file_name)
