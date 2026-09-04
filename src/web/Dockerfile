# Собирается из каталога фронтенда: docker build -f src/web/Dockerfile src/web
#
# Два этапа: node собирает статику, nginx её отдаёт. Node в финальный образ не едет —
# в рантайме фронт это набор файлов, а не процесс сборки.
FROM node:22-alpine AS builder

WORKDIR /build
# Зависимости отдельным слоем: правка исходников не роняет кэш npm ci.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Тот же адрес, что и на сервере: фронт ходит в API относительным путём, а nginx
# рядом проксирует /api/ в контейнер api. Origin один — CORS не нужен.
# Значение вшивается в бандл на этапе сборки, менять его в рантайме нельзя.
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5173
