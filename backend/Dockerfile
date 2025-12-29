FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any (none needed for basic setup yet)


# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
# We use host 0.0.0.0 to be accessible from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
