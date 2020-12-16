#!/bin/sh -e

# This script is intended to be the entrypoint for Dockerfile.dash.

export HEROKU_INTERNAL_PORT="${PORT:-80}"
echo "Will bind to port: $HEROKU_INTERNAL_PORT"

if [ "$HEROKU_INTERNAL_PORT" != "4500" ]; then
    API_PORT="4500"
else
    API_PORT="4501"
fi

export PORT="$API_PORT"

cat >/etc/nginx/conf.d/default.conf <<EOF
server {
    listen       $HEROKU_INTERNAL_PORT;
    server_name  localhost;

    #charset koi8-r;
    #access_log  /var/log/nginx/host.access.log  main;

    location /api {
        proxy_pass  http://localhost:$API_PORT/api;
    }

    location / {
        root   /usr/share/nginx/html;
        try_files \$uri /index.html;
    }

    #error_page  404              /404.html;

    # redirect server error pages to the static page /50x.html
    #
    error_page   500 502 503 504  /50x.html;
    location = /50x.html {
        root   /usr/share/nginx/html;
    }
}

EOF


cat >/etc/nginx/nginx.conf <<EOF
user  nginx;
worker_processes  1;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;


events {
    worker_connections  1024;
}


http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;

    sendfile        on;
    #tcp_nopush     on;

    keepalive_timeout  65;

    #gzip  on;

    include /etc/nginx/conf.d/*.conf;
}

EOF

cat /etc/nginx/conf.d/default.conf

/usr/bin/supervisord
# nginx -g 'daemon off;'
