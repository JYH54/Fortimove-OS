# Nginx를 사용한 간단한 정적 파일 서빙
FROM nginx:alpine

# HTML 파일 복사
COPY index.html /usr/share/nginx/html/index.html

# Nginx 설정 (CORS 허용)
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
