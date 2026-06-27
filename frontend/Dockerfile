FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

# Dev server for the MVP; swap to `npm run build && npm start` for production.
CMD ["npm", "run", "dev"]
