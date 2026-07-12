from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
JWT_SECRET = os.getenv('JWT_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TWILIO_XML_URL = os.getenv('TWILIO_XML_URL')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
NEO4J_AUTH = os.getenv('NEO4J_AUTH')
NEO4J_URI = os.getenv('NEO4J_URI')