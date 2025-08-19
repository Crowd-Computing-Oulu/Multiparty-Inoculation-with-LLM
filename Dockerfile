# Use official Python slim image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app files
COPY . /app

# Expose port 5000 for Flask
EXPOSE 3001

# Run the app with Flask’s built-in server
CMD ["python", "app.py"]


