FROM node:22-slim

ENV NODE_ENV=development
WORKDIR /app

COPY apps/web/package.json /app/package.json
RUN npm install

COPY apps/web /app

RUN chown -R node:node /app
USER node

EXPOSE 3000
CMD ["npm", "run", "dev"]
