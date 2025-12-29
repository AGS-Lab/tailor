FROM node:22-alpine


WORKDIR /app

# Install dependencies based on package lock
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Start in development mode for the baseline
CMD ["npm", "run", "dev"]
