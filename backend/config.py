import os

# AWS RDS Database Configuration (Environment variables with safe placeholders)
DB_HOST = os.getenv('DB_HOST', 'your-rds-endpoint.amazonaws.com')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', 'admin')
DB_PASS = os.getenv('DB_PASS', 'your-db-password')
DB_NAME = os.getenv('DB_NAME', 'seoul-ht-08-db')

# JWT Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-jwt-secret-key-placeholder')
ALGORITHM = os.getenv('ALGORITHM', 'HS256')
