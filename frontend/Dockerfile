# Development image for the FourierLearn frontend (source is bind-mounted by docker-compose).
FROM node:24.21.0-bookworm-slim

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

COPY package.json package-lock.json .npmrc docker-entrypoint.sh ./
RUN npm ci \
    && sha256sum package-lock.json > node_modules/.package-lock.sha256

COPY . .

EXPOSE 3000
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]
